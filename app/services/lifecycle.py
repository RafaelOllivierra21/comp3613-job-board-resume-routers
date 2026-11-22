"""Application lifecycle: thin entry point to the State pattern.

The rules for each status live in app/services/states.py. This module
only checks that the action name is known and passes it to the
Application, which delegates to its current state.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.application import Application

ACTIONS = ("mark_reviewed", "shortlist", "reject", "hire")


def apply_action(app: "Application", action: str) -> None:
    """Apply an action to an Application through its State object.

    Raises:
        ValueError: action is not in ACTIONS.
        InvalidTransition: the current state refuses the action.
    """
    if action not in ACTIONS:
        raise ValueError(f"unknown action {action!r}; expected one of {ACTIONS}")
    getattr(app, action)()
