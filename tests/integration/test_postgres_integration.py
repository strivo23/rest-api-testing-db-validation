"""PostgreSQL integration tests.

These tests exercise the *real* PostgreSQL driver, server side defaults and
CHECK constraints.  They are skipped unless ``TEST_DATABASE_URL`` points at a
dedicated test database, for example::

    set TEST_DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/defect_tracker_test
    pytest tests/integration -v -m integration

The suite refuses to run against a database whose name does not end with
``_test`` so that a development database can never be wiped by accident.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app import models  # noqa: F401
from app.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL_TEST")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is not configured"
    ),
]


@pytest.fixture(scope="module")
def pg_engine():
    assert TEST_DATABASE_URL is not None
    if not TEST_DATABASE_URL.rsplit("/", 1)[-1].split("?")[0].endswith("_test"):
        pytest.skip("Refusing to run integration tests against a non *_test database")

    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    try:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        yield engine
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def pg_session(pg_engine):
    session = sessionmaker(bind=pg_engine, expire_on_commit=False)()
    session.execute(text("TRUNCATE TABLE issues RESTART IDENTITY"))
    session.commit()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def pg_client(pg_session):
    def override_get_db():
        yield pg_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_postgres_health_check_reports_dialect(pg_client):
    body = pg_client.get("/health").json()

    assert body["status"] == "ok"
    assert body["dialect"] == "postgresql"


def test_created_issue_is_stored_with_utc_timestamps(pg_client, pg_session):
    payload = {
        "title": "Postgres integration defect",
        "description": "Stored and verified through raw SQL.",
        "severity": "Critical",
        "status": "Open",
        "category": "API",
        "environment": "Backend API",
    }

    created = pg_client.post("/issues", json=payload).json()

    row = pg_session.execute(
        text("SELECT title, severity, status, created_at FROM issues WHERE id = :id"),
        {"id": created["id"]},
    ).one()

    assert row.title == payload["title"]
    assert row.severity == "Critical"
    assert row.created_at.tzinfo is not None
    assert row.created_at.utcoffset().total_seconds() == 0


def test_postgres_check_constraint_rejects_invalid_severity(pg_session):
    with pytest.raises(IntegrityError):
        pg_session.execute(
            text(
                "INSERT INTO issues (title, severity, status, category, environment)"
                " VALUES ('Postgres constraint check', 'Blocker', 'Open', 'API', 'Web')"
            )
        )
        pg_session.commit()
    pg_session.rollback()


def test_postgres_updated_at_changes_after_patch(pg_client):
    created = pg_client.post(
        "/issues",
        json={
            "title": "Timestamp verification defect",
            "severity": "Low",
            "status": "Open",
            "category": "UI",
            "environment": "Web",
        },
    ).json()

    updated = pg_client.patch(f"/issues/{created['id']}", json={"status": "In Progress"}).json()

    assert updated["status"] == "In Progress"
    assert updated["created_at"] == created["created_at"]
    assert updated["updated_at"] > created["updated_at"]


def test_postgres_delete_then_select_returns_no_rows(pg_client, pg_session):
    created = pg_client.post(
        "/issues",
        json={
            "title": "Deletion verification defect",
            "severity": "Medium",
            "status": "Open",
            "category": "Performance",
            "environment": "Linux",
        },
    ).json()

    pg_client.delete(f"/issues/{created['id']}")

    count = pg_session.execute(
        text("SELECT COUNT(*) FROM issues WHERE id = :id"), {"id": created["id"]}
    ).scalar_one()

    assert count == 0
    assert pg_client.get(f"/issues/{created['id']}").status_code == 404
