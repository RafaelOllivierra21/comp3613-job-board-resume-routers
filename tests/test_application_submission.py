import pytest
from sqlmodel import select

from app.models.application import Application
from app.models.listing import Listing
from app.models.user import User
from app.utilities.security import encrypt_password


def create_user(
    test_session,
    *,
    username: str,
    email: str,
    role: str,
    programme: str | None = None,
) -> User:
    user = User(
        username=username,
        email=email,
        password=encrypt_password("test-password"),
        role=role,
        programme=programme,
        resume_text="Test resume",
    )
    test_session.add(user)
    test_session.commit()
    test_session.refresh(user)
    return user


def create_listing(test_session, employer, **overrides) -> Listing:
    values = {
        "employer_id": employer.id,
        "title": "Test Software Role",
        "company": "Test Company",
        "description": "Test listing",
        "apply_mode": "collect",
        "external_url": None,
        "deadline": "2099-12-31",
        "status": "published",
    }
    values.update(overrides)
    listing = Listing(**values)
    test_session.add(listing)
    test_session.commit()
    test_session.refresh(listing)
    return listing


def test_non_dcit_graduate_is_refused(test_client, test_session, authenticate):
    employer = create_user(
        test_session,
        username="employer",
        email="employer@example.com",
        role="employer",
    )
    graduate = create_user(
        test_session,
        username="other-graduate",
        email="other-graduate@example.com",
        role="graduate",
        programme="OTHER",
    )
    listing = create_listing(test_session, employer)

    authenticate(graduate)

    response = test_client.post(
        "/api/graduates/applications",
        json={
            "listing_id": listing.id,
            "cover_letter": "Test cover letter",
            "resume_text": "Test resume",
        },
    )

    assert response.status_code == 403
    applications = test_session.exec(select(Application)).all()
    assert applications == []


def test_unpublished_listing_cannot_receive_application(
    test_client, test_session, authenticate
):
    employer = create_user(
        test_session,
        username="employer",
        email="employer@example.com",
        role="employer",
    )
    graduate = create_user(
        test_session,
        username="graduate",
        email="graduate@example.com",
        role="graduate",
        programme="DCIT",
    )
    listing = create_listing(test_session, employer, status="pending")

    authenticate(graduate)

    response = test_client.post(
        "/api/graduates/applications",
        json={
            "listing_id": listing.id,
            "cover_letter": "Test cover letter",
            "resume_text": "Test resume",
        },
    )

    assert response.status_code == 400
    applications = test_session.exec(select(Application)).all()
    assert applications == []


def test_expired_listing_cannot_receive_application(
    test_client, test_session, authenticate
):
    employer = create_user(
        test_session,
        username="employer",
        email="employer@example.com",
        role="employer",
    )
    graduate = create_user(
        test_session,
        username="graduate",
        email="graduate@example.com",
        role="graduate",
        programme="DCIT",
    )
    listing = create_listing(
        test_session,
        employer,
        deadline="2020-01-01",
    )

    authenticate(graduate)

    response = test_client.post(
        "/api/graduates/applications",
        json={
            "listing_id": listing.id,
            "cover_letter": "Test cover letter",
            "resume_text": "Test resume",
        },
    )

    assert response.status_code == 400
    applications = test_session.exec(select(Application)).all()
    assert applications == []


def test_external_listing_does_not_create_application(
    test_client, test_session, authenticate
):
    employer = create_user(
        test_session,
        username="employer",
        email="employer@example.com",
        role="employer",
    )
    graduate = create_user(
        test_session,
        username="graduate",
        email="graduate@example.com",
        role="graduate",
        programme="DCIT",
    )
    listing = create_listing(
        test_session,
        employer,
        apply_mode="external",
        external_url="https://example.com/apply",
    )
    
    authenticate(graduate)

    response = test_client.post(
        "/api/graduates/applications",
        json={
            "listing_id": listing.id,
            "cover_letter": "Test cover letter",
            "resume_text": "Test resume",
        },
    )

    assert response.status_code == 400
    applications = test_session.exec(select(Application)).all()
    assert applications == []


def test_on_platform_application_starts_submitted(
    test_client, test_session, authenticate
):
    employer = create_user(
        test_session,
        username="employer",
        email="employer@example.com",
        role="employer",
    )
    graduate = create_user(
        test_session,
        username="graduate",
        email="graduate@example.com",
        role="graduate",
        programme="DCIT",
    )
    listing = create_listing(test_session, employer)

    authenticate(graduate)

    response = test_client.post(
        "/api/graduates/applications",
        json={
            "listing_id": listing.id,
            "cover_letter": "Test cover letter",
            "resume_text": "Test resume",
        },
    )

    assert response.status_code == 200
    applications = test_session.exec(select(Application)).all()
    assert len(applications) == 1
    assert applications[0].state_name == "submitted"



def test_spoofed_actor_id_is_refused(
    test_client, test_session, authenticate
):
    employer = create_user(
        test_session,
        username="employer",
        email="employer@example.com",
        role="employer",
    )
    graduate = create_user(
        test_session,
        username="graduate",
        email="graduate@example.com",
        role="graduate",
        programme="DCIT",
    )
    spoofed_actor = create_user(
        test_session,
        username="spoofed-graduate",
        email="spoofed@example.com",
        role="graduate",
        programme="DCIT",
    )
    listing = create_listing(test_session, employer)

    authenticate(graduate)

    response = test_client.post(
        "/api/graduates/applications",
        json={
            "actor_id": spoofed_actor.id,
            "listing_id": listing.id,
            "cover_letter": "Test cover letter",
            "resume_text": "Test resume",
        },
    )

    assert response.status_code == 200

    applications = test_session.exec(select(Application)).all()

    assert len(applications) == 1
    assert applications[0].graduate_id == graduate.id
    assert applications[0].graduate_id != spoofed_actor.id
