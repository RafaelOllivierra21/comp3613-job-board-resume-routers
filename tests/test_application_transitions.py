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


def create_owned_application(test_session):
    owner = create_user(
        test_session,
        username="owner-employer",
        email="owner-employer@example.com",
        role="employer",
    )
    other = create_user(
        test_session,
        username="other-employer",
        email="other-employer@example.com",
        role="employer",
    )
    administrator = create_user(
        test_session,
        username="administrator",
        email="administrator@example.com",
        role="admin",
    )
    graduate = create_user(
        test_session,
        username="dcit-graduate",
        email="dcit-graduate@example.com",
        role="graduate",
        programme="DCIT",
    )

    listing = Listing(
        employer_id=owner.id,
        title="Software Developer",
        company="Test Company",
        description="Test listing",
        apply_mode="collect",
        deadline="2099-12-31",
        status="published",
    )
    test_session.add(listing)
    test_session.commit()
    test_session.refresh(listing)

    application = Application(
        listing_id=listing.id,
        graduate_id=graduate.id,
        cover_letter="Test cover letter",
        resume_text="Test resume",
        state_name="submitted",
    )
    
    test_session.add(application)
    test_session.commit()
    test_session.refresh(application)

    return owner, other, administrator, graduate, listing, application


def test_listing_owner_can_transition_application(
    test_client, test_session, authenticate
):
    owner, _, _, _, _, application = create_owned_application(test_session)

    authenticate(owner)
    response = test_client.post(
        f"/api/applications/{application.id}/transition",
        json={"action": "mark_reviewed"},
    )

    assert response.status_code == 200
    assert response.json()["changed"] is True

    test_session.expire_all()
    updated = test_session.get(Application, application.id)
    assert updated is not None
    assert updated.state_name == "reviewed"



def test_another_employer_receives_403(
    test_client, test_session, authenticate
):
    _, other, _, _, _, application = create_owned_application(test_session)

    authenticate(other)

    response = test_client.post(
        f"/api/applications/{application.id}/transition",
        json={"action": "mark_reviewed"},
    )

    assert response.status_code == 403
    updated = test_session.get(Application, application.id)
    assert updated is not None
    assert updated.state_name == "submitted"

def test_administrator_receives_403(
    test_client, test_session, authenticate
):
    _, _, administrator, _, _, application = create_owned_application(test_session)

    authenticate(administrator)

    response = test_client.post(
        f"/api/applications/{application.id}/transition",
        json={"action": "mark_reviewed"},
    )

    assert response.status_code == 403
    updated = test_session.get(Application, application.id)
    assert updated is not None
    assert updated.state_name == "submitted"

def test_graduate_receives_403(
    test_client, test_session, authenticate
):
    _, _, _, graduate, _, application = create_owned_application(test_session)

    authenticate(graduate)

    response = test_client.post(
        f"/api/applications/{application.id}/transition",
        json={"action": "mark_reviewed"},
    )

    assert response.status_code == 403
    updated = test_session.get(Application, application.id)
    assert updated is not None
    assert updated.state_name == "submitted"


def test_illegal_transition_is_rejected(
    test_client, test_session, authenticate
):
    owner, _, _, _, _, application = create_owned_application(test_session)

    authenticate(owner)

    response = test_client.post(
        f"/api/applications/{application.id}/transition",
        json={"action": "shortlist"},
    )

    assert response.status_code == 409
    updated = test_session.get(Application, application.id)
    assert updated is not None
    assert updated.state_name == "submitted"
