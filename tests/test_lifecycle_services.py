"""Service-level tests for application lifecycle persistence, AC 11, and #19 listing fixes."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

import app.services.applications as applications_svc
import app.services.board_auth as board_auth_svc
import app.services.listings as listings_svc
from app.models.application import Application
from app.models.listing import Listing
from app.models.notification import Notification
from app.models.subscription import Subscription
from app.models.user import User


@pytest.fixture
def db_engine(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    monkeypatch.setattr("app.database.engine", engine)
    monkeypatch.setattr(applications_svc, "engine", engine)
    monkeypatch.setattr(listings_svc, "engine", engine)
    if hasattr(board_auth_svc, "engine"):
        monkeypatch.setattr(board_auth_svc, "engine", engine)

    yield engine
    SQLModel.metadata.drop_all(engine)


@pytest.fixture
def seed_data(db_engine):
    today = datetime.now(timezone.utc).date()
    tomorrow = (today + timedelta(days=1)).isoformat()
    yesterday = (today - timedelta(days=1)).isoformat()
    with Session(db_engine) as session:
        admin = User(
            username="admin1",
            email="admin@example.com",
            password="hashed_password",
            role="admin",
        )
        employer = User(
            username="emp1",
            email="emp1@example.com",
            password="hashed_password",
            role="employer",
        )
        other_employer = User(
            username="emp2",
            email="emp2@example.com",
            password="hashed_password",
            role="employer",
        )
        dcit_grad = User(
            username="grad_dcit",
            email="dcit@example.com",
            password="hashed_password",
            role="graduate",
            programme="DCIT",
            resume_text="BSc Computer Science CV",
        )
        non_dcit_grad = User(
            username="grad_other",
            email="other@example.com",
            password="hashed_password",
            role="graduate",
            programme="ENGINEERING",
            resume_text="Engineering CV",
        )
        session.add_all([admin, employer, other_employer, dcit_grad, non_dcit_grad])
        session.commit()
        for u in (admin, employer, other_employer, dcit_grad, non_dcit_grad):
            session.refresh(u)

        open_listing = Listing(
            employer_id=employer.id,
            title="Junior Backend Developer",
            company="TechCorp",
            description="Python & FastAPI role",
            apply_mode="collect",
            deadline=tomorrow,
            status="published",
        )
        pending_listing = Listing(
            employer_id=employer.id,
            title="Pending Role",
            company="TechCorp",
            description="Awaiting approval",
            apply_mode="collect",
            deadline=tomorrow,
            status="pending",
        )
        expired_listing = Listing(
            employer_id=employer.id,
            title="Expired Role",
            company="TechCorp",
            description="Past deadline",
            apply_mode="collect",
            deadline=yesterday,
            status="published",
        )
        session.add_all([open_listing, pending_listing, expired_listing])
        session.commit()
        for l in (open_listing, pending_listing, expired_listing):
            session.refresh(l)

        return {
            "admin_id": admin.id,
            "employer_id": employer.id,
            "other_employer_id": other_employer.id,
            "dcit_grad_id": dcit_grad.id,
            "non_dcit_grad_id": non_dcit_grad.id,
            "open_listing_id": open_listing.id,
            "pending_listing_id": pending_listing.id,
            "expired_listing_id": expired_listing.id,
        }


def test_valid_transitions_save_state_to_database(db_engine, seed_data):
    """Valid transitions update and save state_name in the database."""
    applied = applications_svc.apply(
        graduate_id=seed_data["dcit_grad_id"],
        listing_id=seed_data["open_listing_id"],
        cover_letter="Excited to apply.",
    )
    assert applied["ok"] is True
    app_id = applied["application_id"]
    assert applied["status"] == "submitted"

    for action, expected_state in [
        ("mark_reviewed", "reviewed"),
        ("shortlist", "shortlisted"),
        ("hire", "hired"),
    ]:
        res = applications_svc.transition_application(
            actor_id=seed_data["employer_id"],
            application_id=app_id,
            action=action,
        )
        assert res["ok"] is True
        assert res["application"]["status"] == expected_state

        with Session(db_engine) as session:
            db_row = session.get(Application, app_id)
            assert db_row is not None
            assert db_row.state_name == expected_state


def test_refused_transition_leaves_database_unchanged(db_engine, seed_data):
    """Illegal and unknown actions leave state_name unchanged in the database."""
    applied = applications_svc.apply(
        graduate_id=seed_data["dcit_grad_id"],
        listing_id=seed_data["open_listing_id"],
        cover_letter="Excited to apply.",
    )
    app_id = applied["application_id"]

    res = applications_svc.transition_application(
        actor_id=seed_data["employer_id"],
        application_id=app_id,
        action="hire",
    )
    assert res["ok"] is False
    assert res["status_code"] == 409

    with Session(db_engine) as session:
        assert session.get(Application, app_id).state_name == "submitted"

    bad_action = applications_svc.transition_application(
        actor_id=seed_data["employer_id"],
        application_id=app_id,
        action="reopen",
    )
    assert bad_action["ok"] is False

    with Session(db_engine) as session:
        assert session.get(Application, app_id).state_name == "submitted"


def test_final_states_refuse_all_actions_in_db(db_engine, seed_data):
    """Rejected and hired applications refuse all further actions in the database."""
    applied = applications_svc.apply(
        graduate_id=seed_data["dcit_grad_id"],
        listing_id=seed_data["open_listing_id"],
        cover_letter="Ready to contribute.",
    )
    app_id = applied["application_id"]

    applications_svc.transition_application(
        seed_data["employer_id"], app_id, "mark_reviewed"
    )
    applications_svc.transition_application(
        seed_data["employer_id"], app_id, "shortlist"
    )
    rej = applications_svc.transition_application(
        seed_data["employer_id"], app_id, "reject"
    )
    assert rej["ok"] is True

    for action in ("mark_reviewed", "shortlist", "reject", "hire"):
        blocked = applications_svc.transition_application(
            seed_data["employer_id"], app_id, action
        )
        assert blocked["ok"] is False
        assert blocked["status_code"] == 409

        with Session(db_engine) as session:
            assert session.get(Application, app_id).state_name == "rejected"


def test_ac11_graduate_and_employer_views_match_across_lifecycle(seed_data):
    """Graduate and employer views return the exact same status (AC 11)."""
    applied = applications_svc.apply(
        graduate_id=seed_data["dcit_grad_id"],
        listing_id=seed_data["open_listing_id"],
        cover_letter="AC 11 test cover letter.",
    )
    app_id = applied["application_id"]

    for action in (None, "mark_reviewed", "shortlist", "hire"):
        if action is not None:
            applications_svc.transition_application(
                seed_data["employer_id"], app_id, action
            )

        grad_list = applications_svc.my_applications(seed_data["dcit_grad_id"])
        emp_res = applications_svc.listing_applicants(
            seed_data["employer_id"], seed_data["open_listing_id"]
        )
        assert emp_res["ok"] is True

        grad_app = next(a for a in grad_list if a["id"] == app_id)
        emp_app = next(a for a in emp_res["applicants"] if a["id"] == app_id)

        assert grad_app["status"] == emp_app["status"]
        assert grad_app["state_name"] == emp_app["state_name"]


def test_submit_listing_starts_as_pending(db_engine, seed_data):
    """Submitted listings start in pending status."""
    tomorrow = (datetime.now(timezone.utc).date() + timedelta(days=5)).isoformat()
    res = listings_svc.submit_listing(
        employer_id=seed_data["employer_id"],
        title="Cloud Engineer",
        company="CloudWorks",
        description="AWS & Docker",
        apply_mode="collect",
        deadline=tomorrow,
    )
    assert res["ok"] is True
    assert res["status"] == "pending"

    with Session(db_engine) as session:
        saved = session.get(Listing, res["listing_id"])
        assert saved is not None
        assert saved.status == "pending"


def test_list_jobs_for_graduates_returns_only_published_and_unexpired(seed_data):
    """Graduate job listing view returns only published, unexpired jobs."""
    visible = listings_svc.list_jobs_for_graduates()
    visible_ids = {job["id"] for job in visible}

    assert seed_data["open_listing_id"] in visible_ids
    assert seed_data["pending_listing_id"] not in visible_ids
    assert seed_data["expired_listing_id"] not in visible_ids


def test_subscribe_enforces_dcit_eligibility(db_engine, seed_data):
    """Only eligible DCIT graduates can subscribe to job alerts."""
    ineligible = listings_svc.subscribe(seed_data["non_dcit_grad_id"])
    assert ineligible["ok"] is False
    assert ineligible["status_code"] == 403

    eligible = listings_svc.subscribe(seed_data["dcit_grad_id"])
    assert eligible["ok"] is True

    with Session(db_engine) as session:
        subs = session.exec(select(Subscription)).all()
        assert len(subs) == 1
        assert subs[0].graduate_id == seed_data["dcit_grad_id"]


def test_publish_listing_notifies_subscribers(db_engine, seed_data):
    """Publishing a pending listing creates notifications for subscribers."""
    listings_svc.subscribe(seed_data["dcit_grad_id"])

    pub = listings_svc.publish_listing(
        admin_id=seed_data["admin_id"],
        listing_id=seed_data["pending_listing_id"],
    )
    assert pub["ok"] is True
    assert pub["notified"] is True
    assert pub["count"] == 1

    with Session(db_engine) as session:
        listing = session.get(Listing, seed_data["pending_listing_id"])
        assert listing.status == "published"

        notes = session.exec(
            select(Notification).where(
                Notification.user_id == seed_data["dcit_grad_id"]
            )
        ).all()
        assert len(notes) == 1
        assert "Pending Role" in notes[0].message
