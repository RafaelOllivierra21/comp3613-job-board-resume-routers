"""Unit tests for the application State classes (no database)."""

import pytest

from app.services.states import STATES, InvalidTransition, state_for

ACTIONS = ("mark_reviewed", "shortlist", "reject", "hire")

# (from_state, action) -> to_state. Every pair not listed must be refused.
LEGAL = {
    ("submitted", "mark_reviewed"): "reviewed",
    ("reviewed", "shortlist"): "shortlisted",
    ("shortlisted", "reject"): "rejected",
    ("shortlisted", "hire"): "hired",
}

ILLEGAL = [
    (state, action)
    for state in STATES
    for action in ACTIONS
    if (state, action) not in LEGAL
]


class StubApp:
    """Stands in for Application: the states only touch state_name."""

    def __init__(self, state_name: str) -> None:
        self.state_name = state_name


@pytest.mark.parametrize(("start", "action"), list(LEGAL))
def test_legal_transition_sets_next_state(start, action):
    app = StubApp(start)
    getattr(state_for(start), action)(app)
    assert app.state_name == LEGAL[(start, action)]


@pytest.mark.parametrize(("start", "action"), ILLEGAL)
def test_illegal_transition_raises_and_leaves_state(start, action):
    app = StubApp(start)
    with pytest.raises(InvalidTransition) as exc:
        getattr(state_for(start), action)(app)
    assert app.state_name == start
    assert exc.value.state == start
    assert exc.value.action == action


def test_matrix_has_twenty_cases():
    assert len(LEGAL) + len(ILLEGAL) == 20


@pytest.mark.parametrize("name", list(STATES))
def test_get_state_name_matches_registry_key(name):
    assert state_for(name).get_state_name() == name


def test_state_for_unknown_name_raises_value_error():
    with pytest.raises(ValueError):
        state_for("reopened")
