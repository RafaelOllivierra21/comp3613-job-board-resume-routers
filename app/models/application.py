from typing import Optional

from sqlmodel import Field, SQLModel

from app.services.states import ApplicationState, state_for


class Application(SQLModel, table=True):
    """Context in the State pattern.

    Only state_name is stored. The state object is rebuilt from it on
    demand, and each action is passed to that state.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    listing_id: int = Field(index=True)
    graduate_id: int = Field(index=True)
    cover_letter: str
    resume_text: str
    # Single source of truth. Replaces the old status string and boolean flag columns.
    state_name: str = Field(default="submitted", index=True)

    def state(self) -> ApplicationState:
        return state_for(self.state_name)

    def mark_reviewed(self) -> None:
        self.state().mark_reviewed(self)

    def shortlist(self) -> None:
        self.state().shortlist(self)

    def reject(self) -> None:
        self.state().reject(self)

    def hire(self) -> None:
        self.state().hire(self)
