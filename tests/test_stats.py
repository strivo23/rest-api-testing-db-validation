"""Statistics endpoint tests."""

from __future__ import annotations


def test_stats_on_empty_database_returns_zeroed_buckets(client):
    response = client.get("/issues/stats")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0
    assert body["by_status"] == {"Open": 0, "In Progress": 0, "Closed": 0}
    assert body["by_severity"] == {"Low": 0, "Medium": 0, "High": 0, "Critical": 0}


def test_stats_counts_grouped_by_status_and_severity(client, valid_issue_payload):
    client.post("/issues", json={**valid_issue_payload, "severity": "Critical", "status": "Open"})
    client.post("/issues", json={**valid_issue_payload, "severity": "Critical", "status": "Open"})
    client.post("/issues", json={**valid_issue_payload, "severity": "Low", "status": "Closed"})
    client.post(
        "/issues", json={**valid_issue_payload, "severity": "High", "status": "In Progress"}
    )

    body = client.get("/issues/stats").json()

    assert body["total"] == 4
    assert body["by_status"] == {"Open": 2, "In Progress": 1, "Closed": 1}
    assert body["by_severity"] == {"Low": 1, "Medium": 0, "High": 1, "Critical": 2}
    assert sum(body["by_status"].values()) == body["total"]
    assert sum(body["by_severity"].values()) == body["total"]


def test_stats_reflects_status_update(client, create_issue):
    client.patch(f"/issues/{create_issue['id']}", json={"status": "Closed"})

    body = client.get("/issues/stats").json()

    assert body["by_status"]["Open"] == 0
    assert body["by_status"]["Closed"] == 1


def test_stats_reflects_deletion(client, create_issue):
    client.delete(f"/issues/{create_issue['id']}")

    body = client.get("/issues/stats").json()

    assert body["total"] == 0
    assert body["by_severity"]["High"] == 0


def test_stats_route_is_not_shadowed_by_issue_id_route(client):
    """``/issues/stats`` must resolve to the stats endpoint, not to ``/issues/{id}``."""
    response = client.get("/issues/stats")

    assert response.status_code == 200
    assert set(response.json()) == {"total", "by_status", "by_severity"}
