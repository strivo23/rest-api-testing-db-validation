"""Tests for the global error contract and database failure handling."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import get_db
from app.main import app


def _broken_db_session():
    """A session bound to an engine that cannot open its database file."""
    engine = create_engine("sqlite+pysqlite:////definitely-missing-dir/db.sqlite")
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def test_database_failure_returns_safe_500_response(valid_issue_payload):
    """A database outage must not leak SQL statements, stack traces or credentials."""
    app.dependency_overrides[get_db] = _broken_db_session
    try:
        with TestClient(app, raise_server_exceptions=False) as local_client:
            response = local_client.post("/issues", json=valid_issue_payload)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["type"] == "database_error"
    assert body["error"]["message"]

    lowered = response.text.lower()
    for leaked in ("traceback", "sqlalchemy", "select ", "insert into", "password"):
        assert leaked not in lowered, f"response leaked internal detail: {leaked!r}"


def test_unknown_route_returns_consistent_404(client):
    response = client.get("/no-such-endpoint")

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["type"] == "http_error"
    assert body["error"]["message"]


def test_method_not_allowed_returns_consistent_405(client):
    response = client.put("/issues")

    assert response.status_code == 405
    assert response.json()["error"]["type"] == "http_error"
