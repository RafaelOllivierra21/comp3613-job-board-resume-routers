import pytest
from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

import app.models
import app.database as database
import app.seed as seed_module
from app.main import app
from app.services import applications, board_auth, listings
from app.routers import server_config

from fastapi.testclient import TestClient

@pytest.fixture
def test_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.fixture
def test_client(test_session, monkeypatch):
    test_engine = test_session.get_bind()

    monkeypatch.setattr(database, "engine", test_engine)
    monkeypatch.setattr(applications, "engine", test_engine)
    monkeypatch.setattr(listings, "engine", test_engine)
    monkeypatch.setattr(board_auth, "engine", test_engine)
    monkeypatch.setattr(seed_module, "engine", test_engine)
    monkeypatch.setattr(server_config, "engine", test_engine)
    monkeypatch.setattr(seed_module, "seed", lambda reset=False: None)

    with TestClient(app) as client:
        yield client

@pytest.fixture
def authenticate(test_client):
    def _authenticate(user, password="test-password"):
        response = test_client.post(
            "/api/auth/login",
            json={
                "email": user.email,
                "password": password,
            },
        )
        assert response.status_code == 200, response.text
        return response

    return _authenticate