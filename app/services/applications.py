"""Application create / read / status transitions via lifecycle tracker."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlmodel import Session, select

from app.database import engine
from app.models.application import Application
from app.models.listing import Listing
from app.services.board_auth import get_user
from app.services.lifecycle import ACTIONS, apply_action
from app.services.listings import ELIGIBLE_PROGRAMMES
from app.services.states import InvalidTransition


def apply(
    graduate_id: int,
    listing_id: int,
    cover_letter: str,
    resume_text: str | None = None,
) -> dict[str, Any]:
    user = get_user(graduate_id)
    if not user or user["role"] != "graduate":
        return {"ok": False, "error": "graduates only", "status_code": 403}
    if user.get("programme") not in ELIGIBLE_PROGRAMMES:
        return {
            "ok": False,
            "error": "only eligible programme graduates can apply",
            "status_code": 403,
        }

    resume = resume_text or user.get("resume_text") or ""
    if not cover_letter.strip() or not resume.strip():
        return {"ok": False, "error": "cover letter and resume are required"}

    with Session(engine) as session:
        listing = session.get(Listing, listing_id)
        if listing is None:
            return {"ok": False, "error": "listing not found", "status_code": 404}
        if listing.status != "published":
            return {"ok": False, "error": "listing is not open for applications"}
        if listing.deadline < date.today().isoformat():
            return {"ok": False, "error": "listing deadline has passed"}
        if listing.apply_mode == "external":
            return {
                "ok": False,
                "error": f"apply on the employer's site at {listing.external_url}",
            }

        application = Application(
            listing_id=listing_id,
            graduate_id=graduate_id,
            cover_letter=cover_letter,
            resume_text=resume,
        )
        session.add(application)
        session.commit()
        session.refresh(application)
        return {
            "ok": True,
            "application_id": application.id,
            "status": application.state_name,
        }


def my_applications(graduate_id: int) -> list[dict[str, Any]]:
    """Graduate view. Reads state_name, the same field the employer view reads."""
    with Session(engine) as session:
        rows = session.exec(
            select(Application)
            .where(Application.graduate_id == graduate_id)
            .order_by(Application.id)
        ).all()
        return [row.model_dump() for row in rows]


def verify_listing_owner(actor: dict[str, Any], listing: Listing) -> bool:
    """True only if the actor is the employer who owns the listing."""
    return actor["role"] == "employer" and listing.employer_id == actor["id"]


def listing_applicants(viewer_id: int, listing_id: int) -> dict[str, Any]:
    """Employer view. Only the listing's employer, or an admin for export."""
    viewer = get_user(viewer_id)
    if not viewer:
        return {"ok": False, "error": "unknown user", "status_code": 403}
    with Session(engine) as session:
        listing = session.get(Listing, listing_id)
        if listing is None:
            return {"ok": False, "error": "listing not found", "status_code": 404}
        if viewer["role"] != "admin" and not verify_listing_owner(viewer, listing):
            return {"ok": False, "error": "forbidden", "status_code": 403}
        rows = session.exec(
            select(Application)
            .where(Application.listing_id == listing_id)
            .order_by(Application.id)
        ).all()
        return {"ok": True, "applicants": [r.model_dump() for r in rows]}


def export_applicants(admin_id: int, listing_id: int) -> dict[str, Any]:
    admin = get_user(admin_id)
    if not admin or admin["role"] != "admin":
        return {"ok": False, "error": "admin only"}
    result = listing_applicants(admin_id, listing_id)
    if not result.get("ok"):
        return result
    return {"ok": True, "format": "json", "package": result["applicants"]}


def transition_application(
    actor_id: int, application_id: int, action: str
) -> dict[str, Any]:
    """Change an application's status through its State object.

    Only the employer who owns the listing may do this. Admins, other
    employers and graduates get 403.
    """
    actor = get_user(actor_id)
    if not actor:
        return {"ok": False, "error": "unknown user", "status_code": 403}
    if actor["role"] != "employer":
        return {"ok": False, "error": "only the listing's employer", "status_code": 403}
    if action not in ACTIONS:
        return {"ok": False, "error": f"action must be one of {ACTIONS}"}

    with Session(engine) as session:
        row = session.get(Application, application_id)
        if row is None:
            return {"ok": False, "error": "application not found", "status_code": 404}
        listing = session.get(Listing, row.listing_id)
        if listing is None or not verify_listing_owner(actor, listing):
            return {"ok": False, "error": "only the listing's employer", "status_code": 403}

        try:
            apply_action(row, action)
        except InvalidTransition as exc:
            return {"ok": False, "error": str(exc), "status_code": 409}
        session.add(row)
        session.commit()
        session.refresh(row)
        return {"ok": True, "application": row.model_dump(), "changed": True}
