# REST API Testing & Database Validation Platform

A production-style **defect-tracking REST API** built with **Python, FastAPI, SQLAlchemy 2.x and PostgreSQL**, shipped together with the complete QA toolchain around it: an importable **Postman API test collection**, an **automated pytest suite with coverage**, **SQL validation scripts**, and full **test documentation** (test plan, 84 test cases, defect report template, database validation workflow, test execution report).

The project was built to demonstrate practical software-testing skills: API functional and negative testing, boundary-value analysis, database validation through SQL rather than trusting API responses, data-consistency checks, integration testing and automated regression testing.

<!-- Badges are static and reflect the properties recorded in
     test-documentation/test-execution-report.md (last local run: 2026-10-23).
     The "tests" and "coverage" shields are snapshots of that run, not a live CI status. -->
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.161-009688)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.x-red)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-14%2B-336791)
![Pydantic](https://img.shields.io/badge/Pydantic-v2-e92063)
![Tests](https://img.shields.io/badge/tests-103%20passed-brightgreen)
![Coverage](https://img.shields.io/badge/coverage-91%25-yellowgreen)
![License](https://img.shields.io/badge/license-not%20specified-lightgrey)

---

## Table of contents

1. [Overview and problem statement](#1-overview-and-problem-statement)
2. [Key features](#2-key-features)
3. [Technology stack](#3-technology-stack)
4. [Architecture](#4-architecture)
5. [API request lifecycle (worked example)](#5-api-request-lifecycle-worked-example)
6. [API endpoints](#6-api-endpoints)
7. [Project structure](#7-project-structure)
8. [Prerequisites](#8-prerequisites)
9. [Installation and setup (Windows)](#9-installation-and-setup-windows)
10. [PostgreSQL configuration and database initialisation](#10-postgresql-configuration-and-database-initialisation)
11. [Environment variables](#11-environment-variables)
12. [Starting the application](#12-starting-the-application)
13. [API usage examples](#13-api-usage-examples)
14. [Postman collection](#14-postman-collection)
15. [Automated tests and coverage](#15-automated-tests-and-coverage)
16. [Testing strategy](#16-testing-strategy)
17. [Test results](#17-test-results)
18. [SQL database validation](#18-sql-database-validation)
19. [Security notes](#19-security-notes)
20. [Limitations and future enhancements](#20-limitations-and-future-enhancements)
21. [Portfolio summary and GitHub topics](#21-portfolio-summary-and-github-topics)
22. [License](#22-license)

---

## 1. Overview and problem statement

**Problem.** Testers need a realistic system under test on which they can demonstrate the full QA workflow: deriving test cases from a written specification, exercising an HTTP API, then verifying with **SQL** that the database actually stored what the API claimed - and proving that invalid input is rejected at more than one layer. A defect tracker is the natural domain, because it is exactly the kind of tool a QA engineer uses daily.

**What this project is.** A REST API that stores and manages software defect records. Testers can file a defect, search and filter defects, change workflow status, delete them, and read aggregated statistics. Every write is validated **twice**: by Pydantic at the API boundary and by `CHECK` constraints in the database.

**Objectives**

1. Provide a documented API under test with clear contracts and predictable error responses.
2. Prove data correctness at the **database** level, not only from API responses.
3. Demonstrate a layered test approach: functional, negative, boundary-value, data-consistency, integration and regression testing.
4. Provide reusable API test assets: a Postman collection with assertions and variable chaining, plus SQL validation scripts.
5. Show safe engineering practice: environment-based configuration, no hardcoded credentials, no internal details leaked in error responses, and fully isolated automated tests.

**Intended users:** QA/test engineers, backend developers and reviewers who want to run the suite and the collection and inspect the real results.

## 2. Key features

- Full CRUD for defect records, including **partial updates** via `PATCH`.
- Filtering by `severity`, `status`, `category`, `environment` and free-text `search`.
- Sorting on 8 columns in both directions, with a deterministic `id` tie-breaker so pagination never repeats or skips a row.
- Pagination with a hard cap (`page_size <= 100`) and page metadata.
- Aggregated statistics grouped by status and severity, always including **zero buckets**.
- Consistent JSON error contract for `404`, `405`, `422`, `500` (and `503` on `/health`).
- Health endpoint reporting live database connectivity.
- UTC timestamps everywhere (`created_at`, `updated_at`), stored as `timestamptz` in PostgreSQL.
- Database-level `CHECK` constraints and **six indexes** on the hot filter columns.
- Isolated automated test setup: a fresh in-memory SQLite database per test; a separate opt-in PostgreSQL integration suite.
- Optional zero-build HTML/CSS/JS dashboard at `/dashboard/`.

## 3. Technology stack

| Technology | Version | Purpose in this project |
| --- | --- | --- |
| **Python** | 3.11+ (verified on 3.12.9) | Implementation language for the API, tests and tooling |
| **FastAPI** | 0.161.1 | Web framework: routing, dependency injection, request parsing, automatic OpenAPI generation |
| **Starlette** | 1.9.0 | ASGI toolkit underlying FastAPI (routing + `TestClient`) |
| **Uvicorn** | 0.54.0 | ASGI server used to run the application |
| **PostgreSQL** | 14+ | Target database: `timestamptz`, `CHECK` constraints, indexes |
| **psycopg2-binary** | 2.9.13 | PostgreSQL driver used by SQLAlchemy (`postgresql+psycopg2://`) |
| **SQLAlchemy** | 2.1.6 | ORM + SQL toolkit: typed `Mapped` models, sessions, parameterised queries |
| **Pydantic** | 2.14.1 | Request validation and response serialisation (enums, length rules, custom validators) |
| **pydantic-settings** | 2.16.1 | Loads configuration from environment variables / `.env` into a typed settings object |
| **python-dotenv** | 1.x | Enables reading the local `.env` file (used through pydantic-settings) |
| **pytest** | 9.1.1 | Automated test framework |
| **pytest-cov** | 7.1.0 | Coverage measurement and reporting |
| **httpx** | 0.28.1 | HTTP client underneath FastAPI's `TestClient` |
| **Postman / Newman** | desktop app / Node.js CLI | API test collection authoring and headless execution |
| **SQL** | PostgreSQL dialect (SQLite for tests) | Manual database validation: constraints, aggregates, consistency checks |
| **Git** | - | Version control |
| **Markdown + OpenAPI/Swagger** | - | Documentation: this README, test docs, and auto-generated `/docs` |
| **HTML/CSS/JS** | - | Optional dashboard served at `/dashboard/` (no build step) |
| **venv + pip** | - | Virtual environment and dependency management |

## 4. Architecture

Layered design - the routing layer contains no SQL, and the data-access layer raises no HTTP errors.

```mermaid
flowchart TB
    subgraph Clients["Clients / test tools"]
        PM["Postman collection"]
        PT["pytest + FastAPI TestClient"]
        BR["Browser dashboard /dashboard/"]
    end

    subgraph App["FastAPI application (app/main.py)"]
        MW["CORSMiddleware + lifespan<br/>exception handlers (app/errors.py)"]
        subgraph Routers["Routes (app/routes/)"]
            R1["health.py - GET /health"]
            R2["stats.py - GET /issues/stats"]
            R3["issues.py - POST/GET/PATCH/DELETE /issues"]
        end
        SCH["Pydantic schemas (app/schemas.py)<br/>IssueCreate / IssueUpdate / IssueRead"]
        CRUD["CRUD + business logic (app/crud.py)<br/>filters, sort, pagination, aggregates"]
        ORM["SQLAlchemy models (app/models.py)<br/>Issue, CHECK constraints, indexes"]
        DB["Engine + session (app/database.py)<br/>get_db() dependency, SessionLocal"]
        CFG["Settings (app/config.py)<br/>DATABASE_URL from .env"]
    end

    PG[("PostgreSQL - issues table<br/>CHECK constraints + 6 indexes")]
    SQL["SQL scripts: sql/schema.sql,<br/>sql/validation_queries.sql"]

    PM --> MW
    PT --> MW
    BR --> MW
    MW --> R1
    MW --> R2
    MW --> R3
    R1 --> DB
    R2 --> CRUD
    R3 --> SCH
    R3 --> CRUD
    CRUD --> ORM
    ORM --> DB
    DB --> PG
    CFG -.-> DB
    SQL -.->|manual validation| PG
```

The `stats` router is registered **before** the `issues` router so that `/issues/stats` is not captured by `/issues/{issue_id}`; a dedicated test asserts this ordering.

## 5. API request lifecycle (worked example)

Trace of `POST /issues`:

1. **Uvicorn** accepts the HTTP request and passes it to the FastAPI application.
2. Middleware and the registered **exception handlers** (`app/errors.py`) wrap the call.
3. The **issues router** matches `POST /issues` and receives a database session through `Depends(get_db)`.
4. **Pydantic** validates the body against `IssueCreate`: required fields, enum membership, title length 3-200, description length, whitespace trimming.
5. On failure, the `RequestValidationError` handler returns **422** with `error.type = "validation_error"` and a field-level `details` list.
6. `crud.create_issue()` inserts the row through SQLAlchemy (parameterised SQL, committed transaction).
7. The database **`CHECK` constraints** act as the second line of defence; a violation surfaces as a safe **500 `database_error`** with no SQL text in the response.
8. The row is serialised with `IssueRead` (timestamps normalised to UTC) and returned as **201**.

## 6. API endpoints

Base URL: `http://127.0.0.1:8000`

| Method | Path | Success | Purpose |
| --- | --- | --- | --- |
| GET | `/health` | 200 / 503 | API status and database connectivity |
| POST | `/issues` | 201 | Create a defect |
| GET | `/issues` | 200 | List defects (filter, sort, paginate) |
| GET | `/issues/{id}` | 200 | Retrieve a single defect |
| PATCH | `/issues/{id}` | 200 | Partially update a defect |
| DELETE | `/issues/{id}` | 204 | Delete a defect |
| GET | `/issues/stats` | 200 | Counts grouped by status and severity |
| GET | `/` | 200 | Root discovery document (not in the OpenAPI schema) |

### Defect fields

| Field | Type | Rules |
| --- | --- | --- |
| `id` | integer | generated, read-only |
| `title` | string | required, 3-200 characters after trimming |
| `description` | string or null | optional, max 2000 characters |
| `severity` | enum | `Low`, `Medium`, `High`, `Critical` |
| `status` | enum | `Open`, `In Progress`, `Closed` |
| `category` | enum | `Functional`, `UI`, `API`, `Performance`, `Security` |
| `environment` | enum | `Web`, `Android`, `iOS`, `Linux`, `Backend API` |
| `created_at` | datetime | UTC, set on creation |
| `updated_at` | datetime | UTC, refreshed on every update |

### Query parameters of `GET /issues`

| Parameter | Type | Default | Notes |
| --- | --- | --- | --- |
| `severity` | enum | - | exact match |
| `status` | enum | - | exact match |
| `category` | enum | - | exact match |
| `environment` | enum | - | exact match |
| `search` | string | - | case-insensitive match in title or description |
| `page` | integer >= 1 | 1 | page number |
| `page_size` | integer 1-100 | 20 | records per page (values > 100 are rejected with 422) |
| `sort_by` | enum | `created_at` | `id`, `title`, `severity`, `status`, `category`, `environment`, `created_at`, `updated_at` |
| `order` | `asc` / `desc` | `desc` | sort direction |

### Error contract

Every failing request returns the same shape - never a stack trace, SQL statement or credential:

```json
{
  "error": {
    "type": "validation_error",
    "message": "Request validation failed",
    "details": [
      { "field": "severity", "message": "Input should be 'Low', 'Medium', 'High' or 'Critical'", "type": "enum" }
    ]
  }
}
```

| Status | `error.type` | When |
| --- | --- | --- |
| 404 | `not_found` / `http_error` | unknown id, or unknown route |
| 405 | `http_error` | method not allowed |
| 422 | `validation_error` | invalid body or query parameters |
| 500 | `database_error` | database failure while processing |
| 500 | `internal_error` | unexpected error (fallback handler) |
| 503 | - | `/health` when the database is unreachable |

## 7. Project structure

```text
rest-api-testing-db-validation/
├── app/
│   ├── __init__.py             # package marker, __version__ = "1.0.0"
│   ├── main.py                 # FastAPI app, lifespan, CORS, router registration, static mount
│   ├── config.py               # settings from environment variables (.env)
│   ├── database.py             # engine, session factory, Base, get_db dependency
│   ├── models.py               # SQLAlchemy models, enums, CHECK constraints, indexes
│   ├── schemas.py              # Pydantic request/response schemas and validators
│   ├── crud.py                 # data access and business logic
│   ├── errors.py               # APIError + global exception handlers (error contract)
│   ├── db_init.py              # schema initialisation CLI (python -m app.db_init)
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── health.py           # GET /health
│   │   ├── issues.py           # /issues CRUD
│   │   └── stats.py            # GET /issues/stats
│   └── static/                 # optional dashboard (index.html, styles.css, app.js)
├── tests/
│   ├── conftest.py             # isolated in-memory SQLite fixtures + TestClient
│   ├── test_health.py          # 4 tests
│   ├── test_issues.py          # 91 tests
│   ├── test_stats.py           # 5 tests
│   ├── test_errors.py          # 3 tests
│   └── integration/
│       └── test_postgres_integration.py   # 5 tests (opt-in, skipped by default)
├── postman/
│   └── REST_API_Testing.postman_collection.json   # 16 requests / 6 folders
├── sql/
│   ├── schema.sql              # PostgreSQL DDL, constraints, indexes, updated_at trigger
│   └── validation_queries.sql  # 17 read-only validation queries
├── test-documentation/
│   ├── test-plan.md
│   ├── test-cases.csv          # 84 cases
│   ├── defect-report-template.md
│   ├── database-validation.md
│   └── test-execution-report.md
├── .github/workflows/tests.yml # CI: runs pytest + coverage on push / PR
├── .env.example                # placeholder configuration only
├── .gitignore
├── CONTRIBUTING.md
├── PROJECT_TECHNICAL_REPORT.md # detailed technical report
├── pytest.ini
├── requirements.txt
└── README.md
```

## 8. Prerequisites

| Requirement | Notes |
| --- | --- |
| Python 3.11 or newer | check with `python --version` |
| pip | shipped with Python |
| PostgreSQL 14+ | required to run against the real database |
| Postman desktop, or Node.js + Newman | only to run the Postman collection |
| Git | optional, for version control |

**Supported environments:** Windows 10/11 (primary, PowerShell) and Linux/macOS. The automated unit/API suite needs **no database server** - it uses in-memory SQLite. PostgreSQL is only required for the application database and the opt-in integration tests.

## 9. Installation and setup (Windows)

```powershell
cd "c:\Users\Chandrakanth Reddy Y\Desktop\rest-api-testing-db-validation"

# 1. Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# If script execution is blocked by policy, either run:
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass ; .\.venv\Scripts\Activate.ps1
# or simply call the interpreter directly, for example: .\.venv\Scripts\python.exe -m pytest

# 2. Install dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt

# 3. Create your local environment file from the template
copy .env.example .env
# then edit .env and set DATABASE_URL (see section 11)
```

## 10. PostgreSQL configuration and database initialisation

### 10.1 Install PostgreSQL locally

1. Download the installer from <https://www.postgresql.org/download/windows/> (EDB installer).
2. Run it, keep the default port `5432` and set a password for the `postgres` superuser.
3. Add the PostgreSQL `bin` folder to `PATH` (for example `C:\Program Files\PostgreSQL\16\bin`) so `psql` works.
4. Verify: `psql --version`

### 10.2 Create the databases

```powershell
psql -U postgres
```

```sql
CREATE DATABASE defect_tracker WITH ENCODING 'UTF8';
CREATE DATABASE defect_tracker_test WITH ENCODING 'UTF8';   -- used by the integration tests
\l
\q
```

| Database | Used by | Purpose |
| --- | --- | --- |
| `defect_tracker` | the application | real defect data |
| `defect_tracker_test` | `tests/integration` | a separate test database |

The integration suite **refuses to run** unless the database name ends with `_test`, so development data cannot be wiped by accident. The unit/API suite never uses PostgreSQL at all.

### 10.3 Initialise the schema (pick one)

**Option A - SQLAlchemy metadata (recommended; creates indexes and constraints too):**

```powershell
python -m app.db_init
# INFO Creating tables on postgresql+psycopg2://postgres:***@localhost:5432/defect_tracker
# INFO Tables available: issues
```

**Option B - raw SQL script (also installs a trigger that maintains `updated_at` for manual updates):**

```powershell
psql -U postgres -d defect_tracker -f sql/schema.sql
```

Verify the structure:

```powershell
psql -U postgres -d defect_tracker -c "\d issues"
```

## 11. Environment variables

Copy `.env.example` to `.env` and fill in real local values. `.env` is git-ignored; only placeholders live in the repository.

| Variable | Default | Description |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql+psycopg2://postgres:<your_password>@localhost:5432/defect_tracker` | SQLAlchemy connection string |
| `DB_ECHO` | `false` | `true` logs every SQL statement |
| `DB_POOL_SIZE` | `5` | Connection pool size (PostgreSQL only) |
| `DB_MAX_OVERFLOW` | `10` | Extra connections allowed beyond the pool |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins |
| `AUTO_CREATE_TABLES` | `false` | Create missing tables on start-up |
| `TEST_DATABASE_URL` | empty | PostgreSQL test database for the integration suite |

Example `.env`:

```env
DATABASE_URL=postgresql+psycopg2://postgres:your_password@localhost:5432/defect_tracker
DB_ECHO=false
AUTO_CREATE_TABLES=false
TEST_DATABASE_URL=postgresql+psycopg2://postgres:your_password@localhost:5432/defect_tracker_test
```

> **Quick look without PostgreSQL:** set `DATABASE_URL=sqlite:///./local.db` and `AUTO_CREATE_TABLES=true`. This is also how the live verification in section 17 was performed.

## 12. Starting the application

```powershell
# Development (auto-reload)
uvicorn app.main:app --reload

# Explicit host and port
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

| URL | Purpose |
| --- | --- |
| <http://127.0.0.1:8000/> | discovery document with links |
| <http://127.0.0.1:8000/health> | health check |
| <http://127.0.0.1:8000/docs> | **Swagger UI** |
| <http://127.0.0.1:8000/redoc> | **ReDoc** |
| <http://127.0.0.1:8000/openapi.json> | raw OpenAPI schema |
| <http://127.0.0.1:8000/dashboard/> | optional HTML dashboard |

If PostgreSQL is not running you will receive `503` from `/health` and `500 database_error`
from `/issues` - that is the designed safe-failure behaviour, not a crash.

## 13. API usage examples

Responses below were captured from the running application (structure is real; ids and timestamps differ per run).

**Create a defect**

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/issues -Method Post -ContentType 'application/json' -Body '{
  "title": "Login button unresponsive on Android 13",
  "description": "Tapping the Log in button does not submit the form.",
  "severity": "High",
  "status": "Open",
  "category": "Functional",
  "environment": "Android"
}'
```

```json
{
  "id": 1,
  "title": "Login button unresponsive on Android 13",
  "description": "Tapping the Log in button does not submit the form.",
  "severity": "High",
  "status": "Open",
  "category": "Functional",
  "environment": "Android",
  "created_at": "2026-10-23T04:25:30.666261Z",
  "updated_at": "2026-10-23T04:25:30.666261Z"
}
```

**Validation failure** (422)

```json
{
  "error": {
    "type": "validation_error",
    "message": "Request validation failed",
    "details": [
      { "field": "severity", "message": "Input should be 'Low', 'Medium', 'High' or 'Critical'", "type": "enum" },
      { "field": "title", "message": "String should have at least 3 characters", "type": "string_too_short" }
    ]
  }
}
```

**List, filter, sort, paginate**

```http
GET /issues?severity=Critical&status=Open&page=1&page_size=20&sort_by=id&order=desc
```

```json
{
  "total": 1,
  "page": 1,
  "page_size": 20,
  "pages": 1,
  "items": [
    {
      "id": 4,
      "title": "Severity sweep - Critical defect example",
      "description": "Created by the Postman severity sweep.",
      "severity": "Critical",
      "status": "Open",
      "category": "API",
      "environment": "Backend API",
      "created_at": "2026-10-23T05:02:11.128004Z",
      "updated_at": "2026-10-23T05:02:11.128004Z"
    }
  ]
}
```

**Partial update**

```http
PATCH /issues/1
{"status": "In Progress"}
```

```json
{
  "id": 1,
  "title": "Login button unresponsive on Android 13",
  "severity": "High",
  "status": "In Progress",
  "created_at": "2026-10-23T04:25:30.666261Z",
  "updated_at": "2026-10-23T04:25:30.711037Z"
}
```

**Statistics**

```http
GET /issues/stats
```

```json
{
  "total": 1,
  "by_status": { "Open": 0, "In Progress": 1, "Closed": 0 },
  "by_severity": { "Low": 0, "Medium": 0, "High": 1, "Critical": 0 }
}
```

**Delete and verify**

```text
DELETE /issues/1   ->  204 No Content (empty body)
GET    /issues/1   ->  404 Not Found
{ "error": { "type": "not_found", "message": "Issue with id 1 was not found" } }
```

## 14. Postman collection

**File:** [`postman/REST_API_Testing.postman_collection.json`](postman/REST_API_Testing.postman_collection.json)
**Collection name:** *REST API Testing & Database Validation*
**Schema:** Postman Collection v2.1.0
**Collection variable:** `baseUrl` = `http://127.0.0.1:8000`

### Import and run

1. Start the API: `uvicorn app.main:app`.
2. In Postman: **Collections** > **Import** > select the file above.
3. Open the collection, go to the **Variables** tab, confirm `baseUrl` points at your running server.
4. Run the whole collection with **Run** (Collection Runner) in the default order, or send requests individually.
   Order matters for the Update/Delete requests because the id created by request 02 is reused; requests 08 and 12 create their own defect when `issueId` is empty, so they also work standalone.
5. Review the **Test Results** tab: 16 requests with assertions on status codes, content types, response fields, validation errors and behaviour.

### Run with Newman (headless)

```powershell
npm install -g newman
newman run postman/REST_API_Testing.postman_collection.json
```

Chaining uses collection variables (`issueId`, `severityIssueIds`, `deletedIssueId`) - **no request depends on a hardcoded database id**.

Coverage of the 16 requests:

| # | Request | Asserts |
| --- | --- | --- |
| 01 | Health check | 200, JSON content type, `status=ok`, database connected |
| 02 | Create a valid defect | 201, generated id, echoed fields, UTC timestamps; captures `issueId` |
| 03 | Create a defect with every supported severity | one defect per severity; ids stored in `severityIssueIds` |
| 04 | Create with missing required fields | 422, all required fields listed, no internals leaked |
| 05 | Create with an invalid severity | 422, severity reported |
| 06 | Create with a title shorter than 3 characters | 422, title reported |
| 07 | Retrieve all defects | 200, pagination metadata, item schema, ISO-8601 UTC timestamps |
| 08 | Retrieve a defect by ID | 200, id match, value domains |
| 09 | Retrieve a nonexistent defect | 404, `error.type=not_found` |
| 10 | Update a defect status | 200, status updated, other fields intact, follow-up GET proves persistence |
| 11 | Update with invalid data | 422, follow-up GET proves the record is unchanged |
| 12 | Delete a defect | 204, empty body, id remembered as `deletedIssueId` |
| 13 | Retrieve a deleted defect | 404, `not_found` |
| 14 | Filter by severity and status | 200, every item matches; negative filter returns total 0 |
| 15 | Pagination and sorting | page metadata, page size respected, descending ids, non-overlapping page 2, `page_size=1000` -> 422 |
| 16 | Retrieve defect statistics | all buckets present; status and severity sums equal the total |

## 15. Automated tests and coverage

### Commands

```powershell
pytest -v                                             # full suite, verbose
pytest -q                                             # quiet
pytest tests/test_issues.py -v                        # one file
pytest -k "validation" -v                             # by keyword
pytest --cov=app --cov-report=term-missing            # coverage in the terminal
pytest --cov=app --cov-report=html                    # HTML report in htmlcov/index.html
pytest tests/integration -v -m integration            # PostgreSQL integration tests (opt-in)
```

### Test layout

| Path | Focus | Tests |
| --- | --- | --- |
| `tests/conftest.py` | fixtures: in-memory SQLite engine per test, session, `TestClient` with dependency override, payload factories | - |
| [`tests/test_health.py`](tests/test_health.py) | health, root, OpenAPI schema, degraded database | 4 |
| [`tests/test_issues.py`](tests/test_issues.py) | CRUD, validation, boundaries, filters, sorting, pagination, SQL constraints, indexes | 91 |
| [`tests/test_stats.py`](tests/test_stats.py) | statistics accuracy and consistency after update/delete | 5 |
| [`tests/test_errors.py`](tests/test_errors.py) | global error contract, database failure, 404/405 | 3 |
| [`tests/integration/test_postgres_integration.py`](tests/integration/test_postgres_integration.py) | real PostgreSQL behaviour (skipped unless `TEST_DATABASE_URL` is set) | 5 |
| **Total collected** | | **108** |

### Isolation guarantees

- Every test gets a **fresh in-memory SQLite database** which is dropped afterwards.
- The API dependency is overridden, and the fixture **asserts** the API is bound to SQLite - tests cannot touch a real database.
- The integration suite refuses to run unless the database name ends with `_test`.

A GitHub Actions workflow ([`.github/workflows/tests.yml`](.github/workflows/tests.yml)) runs the suite and coverage on every push and pull request. It needs no secrets and no external services, because the unit/API suite uses SQLite.

## 16. Testing strategy

| Test type | What it verifies | Where it lives |
| --- | --- | --- |
| **Positive / functional** | valid create, read, update, delete; correct status codes and response bodies | `tests/test_issues.py`, Postman requests 02, 03, 07, 08, 10, 12 |
| **Negative** | missing required fields, invalid enum values, wrong types, unknown routes, method-not-allowed | `tests/test_issues.py`, `tests/test_errors.py`, Postman 04, 05, 09, 11 |
| **Boundary value** | title length 2/3/200/201; description 2001; `page=0`; `page_size=0/100/101/1000` | `tests/test_issues.py`, Postman 06, 15 |
| **Validation** | all four enums, case sensitivity, whitespace trimming, empty PATCH body | `tests/test_issues.py`, Postman 05, 06, 11 |
| **CRUD / API contract** | request/response schema, content types, error contract shape | Postman assertions across all 16 requests |
| **Database consistency** | rows actually stored/updated/deleted (verified with SQL, not the API); constraint enforcement; index existence | `tests/test_issues.py`, `tests/integration/`, `sql/validation_queries.sql` |
| **Integration** | real PostgreSQL: `timestamptz`, native `CHECK` violations, `updated_at` after PATCH | `tests/integration/test_postgres_integration.py` (opt-in) |
| **Regression** | deterministic re-runnable suite covering the whole API surface | the full pytest suite |

The guiding principle: **API testing alone is not sufficient.** A `201` response only proves the API *said* it stored the data; the SQL checks prove the row exists with the correct values.

## 17. Test results

**Execution date:** 2026-10-23 · **Environment:** Windows 11, PowerShell 5.1, Python 3.12.9 in `.venv`

| Item | Value |
| --- | --- |
| FastAPI / Starlette / Uvicorn | 0.161.1 / 1.9.0 / 0.54.0 |
| SQLAlchemy / Pydantic / psycopg2-binary | 2.1.6 / 2.14.1 / 2.9.13 |
| pytest / pytest-cov | 9.1.1 / 7.1.0 |
| Application database | PostgreSQL 14+ (required); not installed in the recording environment |
| Database used for the recorded run | in-memory SQLite (pytest) and a throwaway SQLite file (live server check) |

### Automated suite

```powershell
.\.venv\Scripts\python.exe -m pytest --cov=app --cov-report=term-missing -q
```

```text
103 passed, 5 skipped, 1 warning in 2.96s

Name                     Stmts   Miss  Cover   Missing
------------------------------------------------------
app\__init__.py              1      0   100%
app\config.py               22      0   100%
app\crud.py                 61      1    98%   99
app\database.py             27      8    70%   31, 45-52
app\db_init.py              15     15     0%   11-34
app\errors.py               40      2    95%   101-102
app\main.py                 33      3    91%   33-35
app\models.py               48      0   100%
app\routes\__init__.py       2      0   100%
app\routes\health.py        18      0   100%
app\routes\issues.py        34      0   100%
app\routes\stats.py          9      0   100%
app\schemas.py             102      8    92%   45, 68, 71, 77-80, 110
------------------------------------------------------
TOTAL                      412     37    91%
```

| Metric | Value |
| --- | --- |
| Tests collected / executed | 108 / 103 |
| Passed | **103** |
| Failed | **0** |
| Skipped | 5 (PostgreSQL integration tests - `TEST_DATABASE_URL` not configured) |
| Warnings | 1 (upstream Starlette deprecation notice about the `httpx` TestClient shim; not project code) |
| Coverage of `app/` | **91%** (37 statements uncovered, each explained in the execution report) |

Uncovered lines are all intentional: the `db_init` CLI wrapper, the PostgreSQL pool branch, the optional `AUTO_CREATE_TABLES` startup branch, defensive schema branches, and the deliberately hard-to-trigger generic exception handler.

### Postman collection (recorded with Newman against the live server)

| Metric | Value |
| --- | --- |
| Requests executed / failed | 21 / **0** |
| Assertions executed / failed | 69 / **0** |
| Test scripts executed / failed | 16 / **0** |
| Pre-request scripts executed / failed | 19 / **0** |
| Run duration | ~1.39 s |

### Live server verification

`GET /health` -> `200 {"status":"ok","database":"connected","dialect":"sqlite","version":"1.0.0"}`; `POST /issues` -> `201` with a generated id; `PATCH /issues/1` -> `200` with a newer `updated_at`; `GET /issues/stats` -> correct buckets; `DELETE /issues/1` -> `204` empty body; `GET /issues/1` afterwards -> `404 not_found`; `GET /docs`, `/redoc`, `/openapi.json` and `/dashboard/` all -> `200`.

### Not executed here

| Item | Status | Command to complete it |
| --- | --- | --- |
| 5 PostgreSQL integration tests | **Skipped / pending** - no PostgreSQL server available | set `TEST_DATABASE_URL` to a `*_test` database, then `pytest tests/integration -v -m integration` |
| PostgreSQL SQL validation queries | **Pending** - same reason | `psql -U postgres -d defect_tracker -f sql/validation_queries.sql` |
| Load / performance / security testing | **Not performed** - out of scope | - |

Full details, including the exit-criteria assessment, are in [`test-documentation/test-execution-report.md`](test-documentation/test-execution-report.md).

## 18. SQL database validation

**Scripts:** [`sql/schema.sql`](sql/schema.sql) (schema) and [`sql/validation_queries.sql`](sql/validation_queries.sql) (17 validation queries).

```powershell
psql -U postgres -d defect_tracker -f sql/validation_queries.sql

# individual queries
psql -U postgres -d defect_tracker -c "SELECT id, title, severity, status FROM issues ORDER BY id DESC LIMIT 10;"
psql -U postgres -d defect_tracker -c "SELECT status, COUNT(*) FROM issues GROUP BY status ORDER BY status;"
psql -U postgres -d defect_tracker -c "SELECT severity, COUNT(*) FROM issues GROUP BY severity ORDER BY severity;"
```

Check stored values after a create:

```sql
SELECT id, title, severity, status, category, environment,
       created_at AT TIME ZONE 'UTC' AS created_at_utc
FROM issues WHERE id = 1;
```

Detect invalid data (each must return 0 rows):

```sql
SELECT id, severity FROM issues WHERE severity NOT IN ('Low', 'Medium', 'High', 'Critical');
SELECT id, title  FROM issues WHERE length(trim(title)) < 3 OR length(title) > 200;
SELECT id         FROM issues WHERE updated_at < created_at;
```

Detect duplicates:

```sql
SELECT title, severity, environment, COUNT(*) AS occurrences
FROM issues GROUP BY title, severity, environment HAVING COUNT(*) > 1 ORDER BY occurrences DESC;
```

The step-by-step workflow (create -> capture id -> GET -> SQL check -> update -> SQL check -> delete -> verify) is documented in [`test-documentation/database-validation.md`](test-documentation/database-validation.md), including a summary table of checks and spaces for the PostgreSQL results.

## 19. Security notes

Implemented:

- **Input validation** at the API boundary (Pydantic: required fields, enum membership, length limits, type checks, trimming) and again as database `CHECK` constraints.
- **Parameterised queries / ORM** for all data access - no string concatenation of user data into SQL. The only raw SQL is `SELECT 1` in the health check, which takes no user input.
- **No secret or internal leakage:** error responses contain only a `type`, `message` and field-level `details`. SQL text, stack traces and credentials are logged server-side only, and a test asserts the 500 body contains none of `traceback`, `sqlalchemy`, `select `, `insert into` or `password`.
- **Environment-based configuration:** all settings come from environment variables / `.env`; `.env` is git-ignored and only `.env.example` placeholders are committed. `db_init` logs the database URL with the password masked.
- **Session hygiene:** the `get_db` dependency rolls back on exception and always closes the session; `pool_pre_ping` avoids stale connections.
- **CORS** allow-list configurable via `CORS_ORIGINS` (`allow_credentials=False`).
- **Synthetic test data only** - no real customer or personal information.

Not implemented (recommended for any real deployment): authentication/authorisation, rate limiting, HTTPS/TLS termination, security headers (CSP/HSTS), audit logging, a secrets manager, and dependency vulnerability scanning.

**No compliance certification or production security audit is claimed.** This is a portfolio project.

## 20. Limitations and future enhancements

**Limitations**

1. **No authentication or authorisation** - every endpoint is open; suitable for local development only.
2. **PostgreSQL-specific verification is scripted but was not executed here** - no PostgreSQL server was available in the build environment, so the integration tests are skipped and the SQL validation results are marked *pending*.
3. **No migration framework** - schema creation uses SQLAlchemy metadata (`app.db_init`) or `sql/schema.sql`; there is no Alembic history.
4. **SQLite is used for the automated unit/API suite**, so PostgreSQL-only behaviour (for example `timestamptz` offsets and server-side constraint error wording) is covered only by the opt-in integration suite.
5. **No soft delete or audit trail** - deletes are physical and untracked.
6. **No rate limiting, caching or background jobs.**
7. **`updated_at` is maintained by the application** (plus an optional PostgreSQL trigger); direct SQL updates that skip the trigger will not refresh it.
8. **Text search** uses a simple case-insensitive match, not full-text search, so it does not scale to very large tables.
9. **No load or security testing** has been performed.
10. **The dashboard is a lightweight convenience UI**, not a tested product surface.

**Future enhancements**

1. Add Alembic migrations and expand CI with coverage gates and Newman runs.
2. Add authentication (JWT or API key) with role-based permissions for testers and admins.
3. Add soft delete, an audit/history table, and explicit `assignee`, `reporter` and `fixed_in_version` fields.
4. Use PostgreSQL full-text search (`tsvector`) or trigram indexes for `search`.
5. Add contract testing (schemathesis / OpenAPI fuzzing) and load testing (k6 or Locust).
6. Enrich statistics: counts over time, per category/environment, mean age of open defects.
7. Add structured JSON logging with correlation ids and containerise the stack with Docker Compose.

## 21. Portfolio summary and GitHub topics

**Summary.** A layered FastAPI + PostgreSQL defect-tracking API surrounded by a complete QA toolchain: a 103-test pytest suite with 91% coverage, 5 opt-in PostgreSQL integration tests, a 16-request Postman collection with 69 assertions, 17 SQL validation queries, and five test-documentation deliverables. It demonstrates test design from requirements, negative and boundary-value testing, verification of stored data with SQL rather than trusting API responses, and fully isolated automated tests that cannot modify a developer's database.

**Documents to explore**

| Deliverable | Path |
| --- | --- |
| Detailed technical report | [`PROJECT_TECHNICAL_REPORT.md`](PROJECT_TECHNICAL_REPORT.md) |
| Test plan | [`test-documentation/test-plan.md`](test-documentation/test-plan.md) |
| Test cases (84) | [`test-documentation/test-cases.csv`](test-documentation/test-cases.csv) |
| Defect report template | [`test-documentation/defect-report-template.md`](test-documentation/defect-report-template.md) |
| Database validation workflow | [`test-documentation/database-validation.md`](test-documentation/database-validation.md) |
| Test execution report | [`test-documentation/test-execution-report.md`](test-documentation/test-execution-report.md) |
| Contribution guide | [`CONTRIBUTING.md`](CONTRIBUTING.md) |

**Suggested GitHub topics:** `fastapi` `python` `postgresql` `sqlalchemy` `pytest` `api-testing` `postman` `newman` `test-automation` `qa` `software-testing` `rest-api` `pydantic` `coverage` `defect-tracking`

## 22. License

No license has been chosen for this repository yet, so **no license is currently granted**
(all rights reserved by default). If you intend to publish it as open source, add a `LICENSE`
file (for example MIT) and update this section.

---

### Manual steps still required

1. **Install PostgreSQL 14+** and add `psql` to `PATH` (section 10.1).
2. **Create `defect_tracker` and `defect_tracker_test`** (section 10.2).
3. **Create `.env`** from `.env.example` and set the real `DATABASE_URL` (section 11).
4. **Initialise the schema** with `python -m app.db_init` or `psql -f sql/schema.sql` (section 10.3).
5. **Run the PostgreSQL integration tests and SQL validation queries**, then record the real output in `test-documentation/database-validation.md` section 3.2 - they are currently marked *pending* because no PostgreSQL server was available while building this project.
