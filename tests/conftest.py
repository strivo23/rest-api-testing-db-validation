"""Shared pytest fixtures.

Tests run against a throw-away in-memory SQLite database that is created for
every test function and dropped afterwards.  A developer's PostgreSQL database
is never touched by the unit/API suite.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401  (register the ORM models)
from app.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = "sqlite+pysqlite:///:memory:"


@pytest.fixture()
def db_engine():
    """A fresh in-memory SQLite engine per test."""
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # one shared connection -> the schema survives
    )
    Base.metadata.create_all(bind=engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def db_session(db_engine):
    """SQLAlchemy session bound to the test engine."""
    testing_session_local = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)
    session: Session = testing_session_local()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session) -> TestClient:
    """FastAPI test client whose ``get_db`` dependency points at the test database."""

    def override_get_db():
        yield db_session

    # Safety net: the API must talk to the throw-away SQLite session, never to
    # the developer's configured database.
    assert db_session.get_bind().dialect.name == "sqlite"

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def valid_issue_payload() -> dict:
    """A fully valid defect creation payload."""
    return {
        "title": "Login button unresponsive on Android 13",
        "description": "Tapping the Log in button does not submit the form.",
        "severity": "High",
        "status": "Open",
        "category": "Functional",
        "environment": "Android",
    }


@pytest.fixture()
def create_issue(client, valid_issue_payload) -> dict:
    """Create one defect through the API and return the response payload."""
    response = client.post("/issues", json=valid_issue_payload)
    assert response.status_code == 201, response.text
    return response.json()


