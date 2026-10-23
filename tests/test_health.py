"""Health check tests (functional + database connectivity)."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import get_db
from app.main import app


def test_health_returns_ok_when_database_is_reachable(client):
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "connected"
    assert body["dialect"] == "sqlite"
    assert body["version"]


def test_root_endpoint_exposes_discovery_links(client):
    response = client.get("/")

    assert response.status_code == 200
    body = response.json()
    assert body["docs"] == "/docs"
    assert body["health"] == "/health"


def test_openapi_schema_contains_all_documented_endpoints(client):
    schema = client.get("/openapi.json").json()
    paths = schema["paths"]

    for path in ("/health", "/issues", "/issues/{issue_id}", "/issues/stats"):
        assert path in paths, f"{path} missing from the OpenAPI schema"
    assert "post" in paths["/issues"]
    assert "patch" in paths["/issues/{issue_id}"]
    assert "delete" in paths["/issues/{issue_id}"]


def test_health_returns_503_when_database_is_unavailable():
    """Database failure handling: the endpoint degrades gracefully, no stack trace."""

    def broken_db():
        engine = create_engine("sqlite+pysqlite:////definitely-missing-dir/db.sqlite")
        session = sessionmaker(bind=engine)()
        try:
            yield session
        finally:
            session.close()
            engine.dispose()

    app.dependency_overrides[get_db] = broken_db
    try:
        from fastapi.testclient import TestClient

        with TestClient(app, raise_server_exceptions=False) as local_client:
            response = local_client.get("/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["database"] == "unavailable"
    # No internal details leak into the response.
    assert "traceback" not in response.text.lower()
