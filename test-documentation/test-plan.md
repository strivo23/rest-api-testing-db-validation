# Test Plan - REST API Testing & Database Validation Platform

| Field | Value |
| --- | --- |
| Project | REST API Testing & Database Validation Platform (defect tracker API) |
| Version under test | 1.0.0 |
| Prepared by | QA Engineer (portfolio project) |
| Status | Active |
| Last updated | 2026-10-23 |

## 1. Introduction

This plan describes the testing approach for the defect-tracking REST API built with
Python 3.11+, FastAPI, SQLAlchemy 2.x and PostgreSQL. The purpose is to verify that
every documented endpoint behaves as specified, that invalid input is rejected, that
data written through the API is stored correctly in the database, and that the
application fails safely when the database is unavailable.

## 2. Objectives

1. Verify every endpoint (`/health`, `/issues`, `/issues/{id}`, `/issues/stats`) against its specification.
2. Verify input validation rules: required fields, enum values, title length 3-200, description length, unknown fields, wrong data types.
3. Verify HTTP semantics: status codes 200, 201, 204, 404, 422, 500/503 and response content types.
4. Verify data persistence and data consistency between the API response and the database row (field by field, through SQL).
5. Verify query features: filtering by severity/status/category/environment, text search, sorting, pagination and page boundaries.
6. Verify aggregated statistics accuracy before and after create/update/delete operations.
7. Verify database constraints (CHECK, NOT NULL) reject invalid data even when the API layer is bypassed.
8. Verify safe error handling: no stack traces, SQL statements or credentials are exposed.
9. Provide evidence for release decisions through a repeatable, automated regression suite.

## 3. Scope

### In scope

- REST API endpoints, request validation and response contracts.
- Business rules for severity, status, category, environment and title length.
- PostgreSQL persistence, constraints, indexes and UTC timestamps.
- Error handling at application level (validation, not found, database failure).
- API-level regression suite (pytest), API contract suite (Postman), SQL validation queries.
- Lightweight dashboard as a manual UI smoke check (optional component).

### Out of scope

- Authentication, authorisation and multi-user access control (not implemented in v1.0).
- Load, stress and endurance testing.
- Penetration testing and any security certification.
- Browser compatibility of the optional dashboard beyond current Chrome/Edge/Firefox.
- Data migration from other defect trackers.
- Mobile client testing.

## 4. Test environment

| Component | Value |
| --- | --- |
| Operating system | Windows 11 (tested), also runnable on Linux/macOS |
| Runtime | Python 3.12 (project requires 3.11+) |
| Framework | FastAPI + Uvicorn |
| ORM | SQLAlchemy 2.x |
| Application database | PostgreSQL 15/16 (local instance) |
| Unit/API test database | SQLite in-memory (isolated, per test) |
| Integration test database | PostgreSQL database whose name ends with `_test` |
| API test tool | Postman (collection `postman/REST_API_Testing.postman_collection.json`) or Newman |
| Automation | pytest + FastAPI TestClient, coverage via pytest-cov |
| SQL client | psql / pgAdmin / DBeaver |
| Base URL | http://127.0.0.1:8000 |

Test data is synthetic. No real customer, personal or production data is used.

## 5. Test strategy / approach

| Level | Technique | Tooling | Coverage of this project |
| --- | --- | --- | --- |
| Unit | White-box, function level | pytest | CRUD helpers, pagination maths, UTC timestamp normalisation |
| API / functional | Black-box, specification based | pytest + TestClient | Every endpoint, happy paths |
| Negative | Error guessing, equivalence partitioning | pytest + TestClient | Invalid enums, missing fields, bad types, unknown ids |
| Boundary value | Min/max/min-1/max+1 | pytest + TestClient | Title 2/3/200/201 characters, description 2001, page 0, page_size 101 |
| Integration | API + database round trip | pytest + TestClient + SQL | Create/read/update/delete verified with raw SQL |
| Data consistency | SQL assertions | SQL scripts + raw queries | Stored values, duplicates, invalid values, counts |
| Contract | Scripted assertions in Postman | Postman / Newman | Status codes, content type, field presence, error contract |
| Regression | Full automated suite | pytest | Re-run after every change |
| Exploratory / UI smoke | Manual | Browser | Dashboard create/update/delete/filter |

Test design principles applied: deterministic and independent tests, one behaviour per
test case, fresh isolated database state per test, no dependence on hardcoded record ids.

## 6. Entry criteria

- Application source code complete for the release under test and the server starts without errors.
- Database schema initialised (`python -m app.db_init` or `sql/schema.sql`).
- `requirements.txt` installed in a virtual environment.
- Test data prepared (synthetic payloads used by the suites).
- Postman collection and pytest suite available.

## 7. Exit criteria

- 100% of the automated pytest suite executed with no failures and no errors.
- Line coverage of the `app` package reported by `pytest --cov=app` (documented value in the test execution report).
- All Postman requests executed against a running instance with all test scripts passing.
- No open defect with severity Critical/High that blocks a documented core flow.
- SQL validation queries executed against PostgreSQL showing zero rows for the "invalid data" checks.
- Test execution report and database validation report completed with real results.

## 8. Assumptions

1. PostgreSQL is installed and reachable locally; the tester creates the databases and credentials.
2. Timestamps are handled and stored in UTC by both the application and the database.
3. Enum values are case sensitive exactly as documented (for example `High`, not `high`).
4. Only the fields listed in the requirements are part of the API contract.
5. The optional dashboard is not a required deliverable for acceptance.
6. Manual steps requiring PostgreSQL cannot be executed by a tool without a running instance; those results are marked as pending until executed by the tester.

## 9. Risks and mitigations

| # | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| 1 | PostgreSQL is not installed on the tester machine | Integration and SQL validation cannot be executed | Unit/API suite runs on isolated SQLite; PostgreSQL integration tests are skipped automatically and clearly reported as skipped |
| 2 | Unit tests accidentally target a real database | Data loss in a developer database | Tests always override the database dependency with an in-memory SQLite session; integration tests refuse to run unless the database name ends with `_test` |
| 3 | Enum values drift between schema, database and API | Inconsistent data | Enumerations are defined once in `app/models.py` and reused by Pydantic schemas, CHECK constraints and SQL scripts |
| 4 | Timestamp timezone inconsistencies | Incorrect audit trail | Timestamps are generated in UTC, stored in `TIMESTAMPTZ` and normalised to UTC on serialisation |
| 5 | Error responses leak internal details | Information disclosure | Global exception handlers return a fixed JSON contract and log details server side only; asserted by tests |
| 6 | Tests depend on execution order or hardcoded ids | Flaky results | Fresh database per test; ids are captured from responses in Postman and generated in pytest |
| 7 | Unbounded page size causes heavy queries | Performance degradation | `page_size` is capped at 100 with validation returning 422 |

## 10. Defect management

- Defects found during execution are recorded with `test-documentation/defect-report-template.md`.
- Severity and priority are assigned per the template definitions.
- No hypothetical defect is reported as real. Any sample entry is explicitly labelled **illustrative**.

## 11. Deliverables

| Deliverable | Path |
| --- | --- |
| Automated test suite | `tests/` |
| Postman collection | `postman/REST_API_Testing.postman_collection.json` |
| Database schema script | `sql/schema.sql` |
| Database validation queries | `sql/validation_queries.sql` |
| Test plan (this document) | `test-documentation/test-plan.md` |
| Test cases | `test-documentation/test-cases.csv` |
| Defect report template | `test-documentation/defect-report-template.md` |
| Database validation workflow | `test-documentation/database-validation.md` |
| Test execution report | `test-documentation/test-execution-report.md` |
