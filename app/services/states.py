"""State pattern for the application lifecycle.

Each status is its own class. A state carries out only its legal
transitions; every other action raises InvalidTransition. Only the
state's name is stored on the Application row (state_name).

Legal transitions:
    submitted   --mark_reviewed--> reviewed
    reviewed    --shortlist-->     shortlisted
    shortlisted --reject-->        rejected
    shortlisted --hire-->          hired
Rejected and Hired are final and refuse every action.
"""

from __future__ import annotations

from abc import ABC
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.application import Application


class InvalidTransition(Exception):
    """Raised when an action is not legal from the current state."""

    def __init__(self, state: str, action: str) -> None:
        super().__init__(f"cannot {action} an application in state {state!r}")
        self.state = state
        self.action = action


class ApplicationState(ABC):
    """Base state. Every action is refused unless a subclass allows it."""

    name: str = ""

    def mark_reviewed(self, app: "Application") -> None:
        raise InvalidTransition(self.name, "mark_reviewed")

    def shortlist(self, app: "Application") -> None:
        raise InvalidTransition(self.name, "shortlist")

    def reject(self, app: "Application") -> None:
        raise InvalidTransition(self.name, "reject")

    def hire(self, app: "Application") -> None:
        raise InvalidTransition(self.name, "hire")

    def get_state_name(self) -> str:
        return self.name


class SubmittedState(ApplicationState):
    name = "submitted"

    def mark_reviewed(self, app: "Application") -> None:
        app.state_name = "reviewed"


class ReviewedState(ApplicationState):
    name = "reviewed"

    def shortlist(self, app: "Application") -> None:
        app.state_name = "shortlisted"


class ShortlistedState(ApplicationState):
    name = "shortlisted"

    def reject(self, app: "Application") -> None:
        app.state_name = "rejected"

    def hire(self, app: "Application") -> None:
        app.state_name = "hired"


class RejectedState(ApplicationState):
    """Final. Inherits refusals for every action."""

    name = "rejected"


class HiredState(ApplicationState):
    """Final. Inherits refusals for every action."""

    name = "hired"


STATES: dict[str, ApplicationState] = {
    s.name: s()
    for s in (SubmittedState, ReviewedState, ShortlistedState, RejectedState, HiredState)
}


def state_for(name: str) -> ApplicationState:
    """Return the state object for a stored state_name."""
    try:
        return STATES[name]
    except KeyError:
        raise ValueError(f"unknown application state {name!r}") from None
