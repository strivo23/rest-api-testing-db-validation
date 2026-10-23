"""Functional, negative, boundary and data-consistency tests for /issues."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app import models

# ---------------------------------------------------------------------------
# POST /issues - creation
# ---------------------------------------------------------------------------


def test_create_issue_returns_201_with_generated_id(client, valid_issue_payload):
    response = client.post("/issues", json=valid_issue_payload)

    assert response.status_code == 201
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()
    assert isinstance(body["id"], int)
    assert body["title"] == valid_issue_payload["title"]
    assert body["severity"] == "High"
    assert body["status"] == "Open"
    assert body["category"] == "Functional"
    assert body["environment"] == "Android"
    assert body["created_at"] == body["updated_at"]
    assert body["created_at"].endswith("+00:00") or body["created_at"].endswith("Z")


@pytest.mark.parametrize("severity", ["Low", "Medium", "High", "Critical"])
def test_create_issue_with_every_supported_severity(client, valid_issue_payload, severity):
    payload = {**valid_issue_payload, "severity": severity}

    response = client.post("/issues", json=payload)

    assert response.status_code == 201
    assert response.json()["severity"] == severity


@pytest.mark.parametrize(
    "status_value", ["Open", "In Progress", "Closed"]
)
def test_create_issue_with_every_supported_status(client, valid_issue_payload, status_value):
    payload = {**valid_issue_payload, "status": status_value}

    response = client.post("/issues", json=payload)

    assert response.status_code == 201
    assert response.json()["status"] == status_value


@pytest.mark.parametrize("category", ["Functional", "UI", "API", "Performance", "Security"])
def test_create_issue_with_every_supported_category(client, valid_issue_payload, category):
    response = client.post("/issues", json={**valid_issue_payload, "category": category})

    assert response.status_code == 201
    assert response.json()["category"] == category


@pytest.mark.parametrize("environment", ["Web", "Android", "iOS", "Linux", "Backend API"])
def test_create_issue_with_every_supported_environment(client, valid_issue_payload, environment):
    response = client.post("/issues", json={**valid_issue_payload, "environment": environment})

    assert response.status_code == 201
    assert response.json()["environment"] == environment


def test_create_issue_without_description_is_allowed(client, valid_issue_payload):
    payload = {key: value for key, value in valid_issue_payload.items() if key != "description"}

    response = client.post("/issues", json=payload)

    assert response.status_code == 201
    assert response.json()["description"] is None


def test_create_issue_persists_the_row_in_the_database(client, db_session, valid_issue_payload):
    issue_id = client.post("/issues", json=valid_issue_payload).json()["id"]

    stored = db_session.execute(
        text("SELECT title, severity, status, category, environment FROM issues WHERE id = :id"),
        {"id": issue_id},
    ).one()

    assert stored.title == valid_issue_payload["title"]
    assert stored.severity == "High"
    assert stored.status == "Open"
    assert stored.category == "Functional"
    assert stored.environment == "Android"


# ---------------------------------------------------------------------------
# POST /issues - validation (negative + boundary)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "missing_field", ["title", "severity", "status", "category", "environment"]
)
def test_create_issue_with_missing_required_field_returns_422(
    client, valid_issue_payload, missing_field
):
    payload = {key: value for key, value in valid_issue_payload.items() if key != missing_field}

    response = client.post("/issues", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["type"] == "validation_error"
    assert any(item["field"] == missing_field for item in body["error"]["details"])


@pytest.mark.parametrize("invalid_severity", ["low", "Blocker", "Unknown", ""])
def test_create_issue_with_invalid_severity_returns_422(client, valid_issue_payload, invalid_severity):
    response = client.post("/issues", json={**valid_issue_payload, "severity": invalid_severity})

    assert response.status_code == 422
    assert response.json()["error"]["type"] == "validation_error"


@pytest.mark.parametrize("invalid_status", ["open", "Reopened", "Done"])
def test_create_issue_with_invalid_status_returns_422(client, valid_issue_payload, invalid_status):
    response = client.post("/issues", json={**valid_issue_payload, "status": invalid_status})

    assert response.status_code == 422


@pytest.mark.parametrize("invalid_category", ["Backend", "functional", "Hardware"])
def test_create_issue_with_invalid_category_returns_422(client, valid_issue_payload, invalid_category):
    response = client.post("/issues", json={**valid_issue_payload, "category": invalid_category})

    assert response.status_code == 422


@pytest.mark.parametrize("short_title", ["", "a", "ab", "  a", "  "])
def test_create_issue_with_title_shorter_than_three_characters_returns_422(
    client, valid_issue_payload, short_title
):
    response = client.post("/issues", json={**valid_issue_payload, "title": short_title})

    assert response.status_code == 422
    assert response.json()["error"]["type"] == "validation_error"


def test_create_issue_with_minimum_title_length_is_accepted(client, valid_issue_payload):
    response = client.post("/issues", json={**valid_issue_payload, "title": "abc"})

    assert response.status_code == 201
    assert response.json()["title"] == "abc"


def test_create_issue_with_maximum_title_length_is_accepted(client, valid_issue_payload):
    title = "T" * 200

    response = client.post("/issues", json={**valid_issue_payload, "title": title})

    assert response.status_code == 201
    assert response.json()["title"] == title


def test_create_issue_with_title_over_maximum_length_returns_422(client, valid_issue_payload):
    response = client.post("/issues", json={**valid_issue_payload, "title": "T" * 201})

    assert response.status_code == 422


def test_create_issue_description_over_maximum_length_returns_422(client, valid_issue_payload):
    response = client.post("/issues", json={**valid_issue_payload, "description": "D" * 2001})

    assert response.status_code == 422


def test_create_issue_with_wrong_type_returns_422(client, valid_issue_payload):
    response = client.post("/issues", json={**valid_issue_payload, "title": 12345})

    assert response.status_code == 422


def test_title_is_trimmed_before_storage(client, valid_issue_payload):
    response = client.post("/issues", json={**valid_issue_payload, "title": "   Padded title   "})

    assert response.status_code == 201
    assert response.json()["title"] == "Padded title"


# ---------------------------------------------------------------------------
# GET /issues/{id}
# ---------------------------------------------------------------------------


def test_get_issue_by_id(client, create_issue):
    response = client.get(f"/issues/{create_issue['id']}")

    assert response.status_code == 200
    assert response.json() == create_issue


@pytest.mark.parametrize("issue_id", [9999, 123456])
def test_get_nonexistent_issue_returns_404(client, issue_id):
    response = client.get(f"/issues/{issue_id}")

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["type"] == "not_found"
    assert str(issue_id) in body["error"]["message"]


def test_get_issue_with_non_integer_id_returns_422(client):
    response = client.get("/issues/not-a-number")

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /issues - list, filter, sort, paginate
# ---------------------------------------------------------------------------


def test_list_issues_on_empty_database_returns_empty_page(client):
    response = client.get("/issues")

    assert response.status_code == 200
    body = response.json()
    assert body == {"total": 0, "page": 1, "page_size": 20, "pages": 0, "items": []}


def test_list_issues_returns_all_records_and_metadata(client, valid_issue_payload):
    for index in range(3):
        client.post("/issues", json={**valid_issue_payload, "title": f"Defect number {index}"})

    response = client.get("/issues")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert len(body["items"]) == 3
    assert body["pages"] == 1


def test_list_issues_pagination_splits_records_across_pages(client, valid_issue_payload):
    for index in range(5):
        client.post("/issues", json={**valid_issue_payload, "title": f"Paged defect {index}"})

    first_page = client.get("/issues?page=1&page_size=2").json()
    second_page = client.get("/issues?page=2&page_size=2").json()
    last_page = client.get("/issues?page=3&page_size=2").json()

    assert first_page["total"] == 5
    assert first_page["pages"] == 3
    assert len(first_page["items"]) == 2
    assert len(second_page["items"]) == 2
    assert len(last_page["items"]) == 1
    # No record is repeated across pages.
    ids = {item["id"] for item in first_page["items"] + second_page["items"] + last_page["items"]}
    assert len(ids) == 5


def test_list_issues_sorting_by_id_ascending_and_descending(client, valid_issue_payload):
    for index in range(3):
        client.post("/issues", json={**valid_issue_payload, "title": f"Sorted defect {index}"})

    ascending = client.get("/issues?sort_by=id&order=asc").json()["items"]
    descending = client.get("/issues?sort_by=id&order=desc").json()["items"]

    assert [item["id"] for item in ascending] == sorted(item["id"] for item in ascending)
    assert [item["id"] for item in descending] == sorted(
        (item["id"] for item in descending), reverse=True
    )


def test_list_issues_sorted_by_title_ascending(client, valid_issue_payload):
    for title in ("Zulu crash", "Alpha crash", "Mike crash"):
        client.post("/issues", json={**valid_issue_payload, "title": title})

    items = client.get("/issues?sort_by=title&order=asc").json()["items"]

    assert [item["title"] for item in items] == ["Alpha crash", "Mike crash", "Zulu crash"]


def test_list_issues_filter_by_severity_and_status(client, valid_issue_payload):
    client.post("/issues", json={**valid_issue_payload, "severity": "High", "status": "Open"})
    client.post("/issues", json={**valid_issue_payload, "severity": "Low", "status": "Open"})
    client.post("/issues", json={**valid_issue_payload, "severity": "High", "status": "Closed"})

    high_open = client.get("/issues?severity=High&status=Open").json()
    low = client.get("/issues?severity=Low").json()
    closed = client.get("/issues?status=Closed").json()

    assert high_open["total"] == 1
    assert high_open["items"][0]["severity"] == "High"
    assert high_open["items"][0]["status"] == "Open"
    assert low["total"] == 1
    assert closed["total"] == 1


def test_list_issues_filter_by_category_and_environment(client, valid_issue_payload):
    client.post("/issues", json={**valid_issue_payload, "category": "API", "environment": "Backend API"})
    client.post("/issues", json={**valid_issue_payload, "category": "UI", "environment": "Web"})

    api_only = client.get("/issues?category=API").json()
    backend = client.get("/issues?environment=Backend%20API").json()

    assert api_only["total"] == 1
    assert api_only["items"][0]["category"] == "API"
    assert backend["total"] == 1
    assert backend["items"][0]["environment"] == "Backend API"


def test_list_issues_text_search_matches_title_case_insensitively(client, valid_issue_payload):
    client.post("/issues", json={**valid_issue_payload, "title": "Payment gateway timeout"})
    client.post("/issues", json={**valid_issue_payload, "title": "Profile picture upload"})

    response = client.get("/issues?search=PAYMENT")

    assert response.json()["total"] == 1
    assert "Payment" in response.json()["items"][0]["title"]


def test_list_issues_filter_with_no_match_returns_empty_page(client, valid_issue_payload):
    client.post("/issues", json=valid_issue_payload)

    body = client.get("/issues?severity=Critical").json()

    assert body["total"] == 0
    assert body["items"] == []


@pytest.mark.parametrize(
    "query",
    [
        "severity=Blocker",
        "status=Reopened",
        "category=Hardware",
        "environment=Calculator",
        "page=0",
        "page_size=0",
        "page_size=101",
        "sort_by=nonexistent",
        "order=sideways",
    ],
)
def test_list_issues_with_invalid_query_parameters_returns_422(client, query):
    response = client.get(f"/issues?{query}")

    assert response.status_code == 422
    assert response.json()["error"]["type"] == "validation_error"


# ---------------------------------------------------------------------------
# PATCH /issues/{id}
# ---------------------------------------------------------------------------


def test_patch_issue_status_only(client, create_issue):
    response = client.patch(f"/issues/{create_issue['id']}", json={"status": "In Progress"})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "In Progress"
    # Untouched fields keep their previous values.
    assert body["title"] == create_issue["title"]
    assert body["severity"] == create_issue["severity"]
    assert body["created_at"] == create_issue["created_at"]


def test_patch_issue_updates_the_updated_at_timestamp(client, create_issue):
    response = client.patch(f"/issues/{create_issue['id']}", json={"severity": "Critical"})

    assert response.status_code == 200
    assert response.json()["updated_at"] > create_issue["updated_at"]
    assert response.json()["created_at"] == create_issue["created_at"]


def test_patch_issue_can_update_multiple_fields(client, create_issue):
    payload = {"title": "Renamed defect", "status": "Closed", "category": "Security"}

    response = client.patch(f"/issues/{create_issue['id']}", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Renamed defect"
    assert body["status"] == "Closed"
    assert body["category"] == "Security"


def test_patch_issue_persists_change_to_the_database(client, db_session, create_issue):
    client.patch(f"/issues/{create_issue['id']}", json={"status": "Closed"})

    stored_status = db_session.execute(
        text("SELECT status FROM issues WHERE id = :id"), {"id": create_issue["id"]}
    ).scalar_one()

    assert stored_status == "Closed"


@pytest.mark.parametrize(
    "payload",
    [
        {"severity": "Blocker"},
        {"status": "Reopened"},
        {"category": "Hardware"},
        {"environment": "Calculator"},
        {"title": "ab"},
    ],
)
def test_patch_issue_with_invalid_data_returns_422(client, create_issue, payload):
    response = client.patch(f"/issues/{create_issue['id']}", json=payload)

    assert response.status_code == 422


def test_patch_issue_with_empty_body_returns_422(client, create_issue):
    response = client.patch(f"/issues/{create_issue['id']}", json={})

    assert response.status_code == 422


def test_patch_nonexistent_issue_returns_404(client):
    response = client.patch("/issues/98765", json={"status": "Closed"})

    assert response.status_code == 404


def test_failed_patch_does_not_change_the_record(client, create_issue):
    response = client.patch(f"/issues/{create_issue['id']}", json={"severity": "Blocker"})
    unchanged = client.get(f"/issues/{create_issue['id']}").json()

    assert response.status_code == 422
    assert unchanged == create_issue


# ---------------------------------------------------------------------------
# DELETE /issues/{id}
# ---------------------------------------------------------------------------


def test_delete_issue_returns_204_with_empty_body(client, create_issue):
    response = client.delete(f"/issues/{create_issue['id']}")

    assert response.status_code == 204
    assert response.content == b""


def test_retrieve_deleted_issue_returns_404(client, create_issue):
    client.delete(f"/issues/{create_issue['id']}")

    response = client.get(f"/issues/{create_issue['id']}")

    assert response.status_code == 404
    assert response.json()["error"]["type"] == "not_found"


def test_delete_removes_the_row_from_the_database(client, db_session, create_issue):
    client.delete(f"/issues/{create_issue['id']}")

    remaining = db_session.execute(
        text("SELECT COUNT(*) FROM issues WHERE id = :id"), {"id": create_issue["id"]}
    ).scalar_one()

    assert remaining == 0


def test_delete_same_issue_twice_returns_404(client, create_issue):
    first = client.delete(f"/issues/{create_issue['id']}")
    second = client.delete(f"/issues/{create_issue['id']}")

    assert first.status_code == 204
    assert second.status_code == 404


def test_delete_nonexistent_issue_returns_404(client):
    response = client.delete("/issues/424242")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Database constraint / data-consistency tests (SQL level)
# ---------------------------------------------------------------------------


def test_database_constraint_rejects_invalid_severity(db_session):
    """The CHECK constraint protects the data even when the API is bypassed."""

    with pytest.raises(IntegrityError):
        db_session.execute(
            text(
                "INSERT INTO issues (title, severity, status, category, environment, created_at, updated_at)"
                " VALUES ('Constraint check', 'Blocker', 'Open', 'API', 'Web', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            )
        )
        db_session.commit()
    db_session.rollback()


def test_database_constraint_rejects_short_title(db_session):
    with pytest.raises(IntegrityError):
        db_session.execute(
            text(
                "INSERT INTO issues (title, severity, status, category, environment, created_at, updated_at)"
                " VALUES ('ab', 'Low', 'Open', 'API', 'Web', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            )
        )
        db_session.commit()
    db_session.rollback()


def test_database_constraint_rejects_null_required_column(db_session):
    with pytest.raises(IntegrityError):
        db_session.execute(
            text(
                "INSERT INTO issues (title, severity, status, category, environment, created_at, updated_at)"
                " VALUES (NULL, 'Low', 'Open', 'API', 'Web', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            )
        )
        db_session.commit()
    db_session.rollback()


def test_expected_indexes_exist(db_session):
    """Frequently filtered columns must be indexed."""
    index_names = {
        row[0]
        for row in db_session.execute(
            text("SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = 'issues'")
        )
    }

    for expected in (
        "ix_issues_severity",
        "ix_issues_status",
        "ix_issues_category",
        "ix_issues_environment",
        "ix_issues_created_at",
        "ix_issues_status_severity",
    ):
        assert expected in index_names, f"missing index {expected}"


def test_model_never_stores_invalid_enum_values(client, valid_issue_payload, db_session):
    """A rejected request must not leave partial data behind."""
    client.post("/issues", json={**valid_issue_payload, "severity": "Blocker"})

    count = db_session.execute(text("SELECT COUNT(*) FROM issues")).scalar_one()

    assert count == 0


def test_issue_model_repr_is_descriptive(db_session, create_issue):
    issue = db_session.get(models.Issue, create_issue["id"])

    assert "Issue id=" in repr(issue)
