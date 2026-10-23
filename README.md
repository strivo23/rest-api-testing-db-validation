# REST API Testing & Database Validation Platform

A small defect-tracking REST API written with FastAPI, SQLAlchemy and PostgreSQL, plus the
testing assets that go around it: a pytest suite, a Postman collection with assertions, SQL
validation queries, and written test documentation.

The point of the project is not the API itself. It is the testing workflow: write tests from a
specification, exercise the API over HTTP, and then check with SQL that the database really
contains what the API claimed it stored.

<!-- The test badge is the live GitHub Actions status for .github/workflows/tests.yml.
     It reports whatever the latest run did - it is not a static snapshot, and there is
     deliberately no hardcoded test-count or coverage badge, because those go stale.
     The other three badges are not version-pinned and cannot drift. -->
[![tests](https://github.com/strivo23/rest-api-testing-db-validation/actions/workflows/tests.yml/badge.svg)](https://github.com/strivo23/rest-api-testing-db-validation/actions/workflows/tests.yml)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-009688)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-14%2B-336791)

---

## 1. What this project is

It is a defect tracker. You can file a defect, read it back, change its status, delete it, and
ask for counts grouped by status and severity.

| Field | Allowed values |
| --- | --- |
| `title` | required, 3-200 characters after trimming |
| `description` | optional, up to 2000 characters |
| `severity` | `Low`, `Medium`, `High`, `Critical` |
| `status` | `Open`, `In Progress`, `Closed` |
| `category` | `Functional`, `UI`, `API`, `Performance`, `Security` |
| `environment` | `Web`, `Android`, `iOS`, `Linux`, `Backend API` |

Every write is validated twice: once by Pydantic at the API boundary, and again by `CHECK`
constraints in the database. That duplication is deliberate - see
[PROJECT_NOTES.md](PROJECT_NOTES.md).

**Why a defect tracker?** Because it is the tool a tester actually uses, and it gives you
something concrete to test: required fields, enums, a workflow that changes over time, filters,
pagination and aggregates you can verify with SQL. It is also small enough to read end to end.

### Current status

| Part | State |
| --- | --- |
| API implementation | Working |
| pytest suite (SQLite) | 121 passed, 5 skipped |
| Postman / Newman collection | 16 requests, 0 assertion failures |
| PostgreSQL integration tests | Written, **not run here** - no PostgreSQL server in this environment |
| PostgreSQL SQL validation queries | Written, **not run here** - same reason |

The two PostgreSQL items are the honest gap in this project. They are scripted and ready; they
just need a machine with PostgreSQL installed. Nothing in this README claims they passed.

## 2. Technology stack, and why each piece is there

| Technology | Why it is used here |
| --- | --- |
| **Python 3.11+** | One language for the service, the tests and the SQL tooling. |
| **FastAPI** | Gives request parsing, dependency injection and an OpenAPI schema for free, so the API contract is documented without writing a second document by hand. Its `TestClient` lets the pytest suite call the real app in-process. |
| **Pydantic v2** | The first line of validation. Enum membership, string lengths and the "don't send an empty PATCH" rule live here, and the error format is normalised into one JSON shape. |
| **SQLAlchemy 2.x** | Typed models (`Mapped[...]`) plus `select()` expressions. Also the reason the same code runs against SQLite in tests and PostgreSQL in the deployment target the project is written for. |
| **PostgreSQL** | The real target: `timestamptz`, native `CHECK` constraints, indexes. Chosen because a tester should validate against the database that will actually be used. |
| **psycopg2-binary** | The driver behind `postgresql+psycopg2://` URLs. |
| **pydantic-settings** | Reads configuration from environment variables or `.env` into one typed object, so no connection string is hardcoded. |
| **pytest + pytest-cov** | The regression suite and its coverage report. The suite runs on in-memory SQLite so it needs no server. |
| **Postman / Newman** | Where the API-side assertions live: status codes, content types, field presence, and the fact that a rejected update leaves the record alone. Newman runs the same collection headlessly. |
| **SQL** | The part that makes this a *validation* project: queries that check the stored rows directly instead of trusting the API response. |
| **Uvicorn** | Runs the ASGI app. |
| **HTML/CSS/JS** | A small optional dashboard at `/dashboard/`. No build step. |

Nothing else is used. There is no Dockerfile, no migration tool and no CI beyond the pytest
workflow in `.github/workflows/tests.yml`.

## 3. Architecture

The routing layer contains no SQL, and `app/crud.py` never raises HTTP errors. That split is
what makes the CRUD functions testable on their own.

```mermaid
flowchart TB
    subgraph Clients["Callers"]
        PM["Postman / Newman"]
        PT["pytest + FastAPI TestClient"]
        BR["Optional dashboard at /dashboard/"]
    end

    subgraph App["FastAPI app (app/main.py)"]
        MW["CORS middleware<br/>lifespan<br/>exception handlers (app/errors.py)"]
        R1["routes/health.py<br/>GET /health"]
        R2["routes/stats.py<br/>GET /issues/stats"]
        R3["routes/issues.py<br/>POST / GET / PATCH / DELETE"]
        SCH["schemas.py<br/>Pydantic validation and serialisation"]
        CRUD["crud.py<br/>filters, sorting, pagination, aggregates"]
        ORM["models.py<br/>Issue + CHECK constraints + indexes"]
        DB["database.py<br/>engine, SessionLocal, get_db()"]
        CFG["config.py<br/>settings from .env"]
    end

    PG[("PostgreSQL<br/>issues table")]
    SQL["sql/schema.sql<br/>sql/validation_queries.sql"]

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
    SQL -.->|manual verification| PG
```

Two details worth knowing:

- `routes/stats.py` is registered **before** `routes/issues.py` in
  [main.py](app/main.py).
  If it were not, `/issues/stats` would be matched by `/issues/{issue_id}` and the API would
  answer `422` instead of the statistics. There is a test for this.
- `GET /issues` sorts by the requested column and then appends `id` as a tie-breaker, so two
  rows with the same `created_at` cannot swap places between pages.

## 4. API endpoints

Base URL: `http://127.0.0.1:8000`

| Method | Path | Success | Purpose |
| --- | --- | --- | --- |
| GET | `/health` | 200, or 503 when the database is unreachable | Liveness plus a real `SELECT 1` |
| POST | `/issues` | 201 | Create a defect |
| GET | `/issues` | 200 | List defects with filters, sorting and pagination |
| GET | `/issues/{id}` | 200 | Read one defect |
| PATCH | `/issues/{id}` | 200 | Update only the fields that were sent |
| DELETE | `/issues/{id}` | 204 | Delete a defect |
| GET | `/issues/stats` | 200 | Counts by status and severity, including empty buckets |
| GET | `/` | 200 | Discovery document (excluded from the OpenAPI schema) |

Query parameters of `GET /issues`:

| Parameter | Default | Notes |
| --- | --- | --- |
| `severity`, `status`, `category`, `environment` | - | exact match on the enum value |
| `search` | - | case-insensitive match in `title` or `description`, max 200 characters |
| `page` | `1` | must be >= 1 |
| `page_size` | `20` | must be between 1 and 100 |
| `sort_by` | `created_at` | `id`, `title`, `severity`, `status`, `category`, `environment`, `created_at`, `updated_at` |
| `order` | `desc` | `asc` or `desc` |

Errors always use the same shape, so a test only has to check one format:

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
| 404 | `not_found`, or `http_error` for an unknown route | unknown id |
| 405 | `http_error` | method not allowed |
| 422 | `validation_error` | invalid body or query parameter |
| 500 | `database_error` | the database failed while handling the request |
| 500 | `internal_error` | anything unexpected |
| 503 | not applicable | `/health` when the database does not answer; returns the health payload with `status: "degraded"` |

`error.details[].field` is always the plain parameter name - `title` for a body field, `page`
for a query parameter. No stack trace, SQL text or credential is ever returned to the client.

## 5. Creating and retrieving a defect

Start the API (section 8), then:

```powershell
# Create
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

```powershell
# Read it back
Invoke-RestMethod -Uri http://127.0.0.1:8000/issues/1

# Change only the status; every other field must survive
Invoke-RestMethod -Uri http://127.0.0.1:8000/issues/1 -Method Patch -ContentType 'application/json' -Body '{"status": "In Progress"}'

# Delete, then confirm it is gone
Invoke-RestMethod -Uri http://127.0.0.1:8000/issues/1 -Method Delete
Invoke-RestMethod -Uri http://127.0.0.1:8000/issues/1    # 404, error.type = "not_found"
```

The last two calls are the ones that matter for testing: a `204` only proves the API *said* it
deleted the row. Section 11 shows how to confirm it with SQL.

## 6. Project structure

```text
rest-api-testing-db-validation/
├── app/
│   ├── main.py            # FastAPI app, lifespan, CORS, router order, static mount
│   ├── config.py          # typed settings loaded from the environment / .env
│   ├── database.py        # engine, SessionLocal, Base, get_db() dependency
│   ├── models.py          # Issue model, enum values, CHECK constraints, indexes
│   ├── schemas.py         # Pydantic request/response models and validators
│   ├── crud.py            # data access: filters, sorting, pagination, aggregates
│   ├── errors.py          # APIError and the global exception handlers
│   ├── db_init.py         # python -m app.db_init creates the tables
│   ├── routes/
│   │   ├── health.py      # GET /health
│   │   ├── issues.py      # /issues CRUD
│   │   └── stats.py       # GET /issues/stats
│   └── static/            # optional dashboard (index.html, styles.css, app.js)
├── tests/
│   ├── conftest.py        # in-memory SQLite fixtures + TestClient
│   ├── test_health.py     # 4 tests
│   ├── test_issues.py     # 109 tests
│   ├── test_stats.py      # 5 tests
│   ├── test_errors.py     # 3 tests
│   └── integration/
│       └── test_postgres_integration.py   # 5 tests, skipped unless TEST_DATABASE_URL is set
├── postman/
│   └── REST_API_Testing.postman_collection.json   # 16 requests in 6 folders
├── sql/
│   ├── schema.sql             # PostgreSQL DDL: constraints, indexes, updated_at trigger
│   └── validation_queries.sql # 17 numbered validation checks
├── test-documentation/
│   ├── test-plan.md
│   ├── test-cases.csv         # 84 test cases
│   ├── defect-report-template.md
│   ├── database-validation.md
│   └── test-execution-report.md
├── .github/workflows/tests.yml   # runs pytest + coverage on push and pull request
├── .env.example               # placeholders only
├── CONTRIBUTING.md
├── PROJECT_NOTES.md           # design decisions, limitations, next steps
├── PROJECT_TECHNICAL_REPORT.md
├── REPOSITORY_AUDIT.md        # findings from the repository quality audit
├── pytest.ini
└── requirements.txt
```

## 7. Setup on Windows

```powershell
# 1. Get the code and enter it
git clone https://github.com/strivo23/rest-api-testing-db-validation.git
cd rest-api-testing-db-validation

# 2. Virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# If the execution policy blocks the activation script, use one of these instead:
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass ; .\.venv\Scripts\Activate.ps1
#   .\.venv\Scripts\python.exe -m pytest        (call the interpreter directly, no activation)

# 3. Dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt

# 4. Local configuration
copy .env.example .env
# then edit .env and set DATABASE_URL (section 8)
```

The pytest suite needs no database server - it creates its own in-memory SQLite database - so
you can run it immediately after step 3.

The commands above are PowerShell. On macOS or Linux use the same steps with
`python -m venv .venv`, `source .venv/bin/activate`, `pip install -r requirements.txt` and
`.venv/bin/python -m pytest`. Nothing in the project is Windows-specific except the examples.

### Which Python packages get installed

`requirements.txt` declares supported **ranges** (`fastapi>=0.110,<1.0`, `pytest>=8.0`, …) rather
than exact pins, so `pip install -r requirements.txt` on two machines can resolve to different
patch versions. The versions that were actually used for the test evidence in this repository
are listed in
[test-execution-report.md](test-documentation/test-execution-report.md) section 1. Treat that
list as "what was tested here", not as a guarantee about your own install.

## 8. PostgreSQL configuration

### 8.1 Install and create the databases

1. Install the EDB build from <https://www.postgresql.org/download/windows/>, keeping the
   default port `5432`.
2. Add the `bin` directory to `PATH` (for example `C:\Program Files\PostgreSQL\16\bin`) so
   `psql` is usable, then check it with `psql --version`.
3. Create one database for the application and one for the integration tests:

```powershell
psql -U postgres
```

```sql
CREATE DATABASE defect_tracker      WITH ENCODING 'UTF8';
CREATE DATABASE defect_tracker_test WITH ENCODING 'UTF8';
\q
```

### 8.2 Why there are two databases

The integration suite in `tests/integration/` **drops and recreates** the tables it uses. To make
that safe it refuses to start unless the database name ends with `_test`:

```python
if not TEST_DATABASE_URL.rsplit("/", 1)[-1].split("?")[0].endswith("_test"):
    pytest.skip("Refusing to run integration tests against a non *_test database")
```

That check exists so a typo in `TEST_DATABASE_URL` cannot wipe your development data. The
unit/API suite never uses PostgreSQL at all - each test gets a fresh in-memory SQLite database
and a fixture asserts the dialect really is SQLite.

### 8.3 Create the schema

Either of these produces the same structure:

```powershell
# Option A - SQLAlchemy metadata (recommended)
python -m app.db_init
# INFO Creating tables on postgresql+psycopg2://postgres:***@localhost:5432/defect_tracker
# INFO Tables available: issues

# Option B - raw SQL, which also installs the updated_at trigger
psql -U postgres -d defect_tracker -f sql/schema.sql
```

`sql/schema.sql` and `app/models.py` declare the same five `CHECK` constraints and the same six
indexes under the same names; keeping them in step is a documented convention, not something the
code enforces. Check the result with `psql -U postgres -d defect_tracker -c "\d issues"`.

### 8.4 Environment variables

`.env` is git-ignored. Only placeholders live in `.env.example`.

| Variable | Default | Meaning |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql+psycopg2://postgres:<your_password>@localhost:5432/defect_tracker` | SQLAlchemy connection string |
| `DB_ECHO` | `false` | `true` logs every SQL statement |
| `DB_POOL_SIZE` | `5` | Connection pool size (PostgreSQL only) |
| `DB_MAX_OVERFLOW` | `10` | Extra connections allowed above the pool |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins |
| `AUTO_CREATE_TABLES` | `false` | Create missing tables at start-up |
| `TEST_DATABASE_URL` | empty | Test database for `tests/integration/`; when empty, those tests skip |

```env
DATABASE_URL=postgresql+psycopg2://postgres:your_password@localhost:5432/defect_tracker
DB_ECHO=false
AUTO_CREATE_TABLES=false
TEST_DATABASE_URL=postgresql+psycopg2://postgres:your_password@localhost:5432/defect_tracker_test
```

**No PostgreSQL available?** You can still exercise the whole API. Point it at a throwaway
SQLite file - this is exactly how the live checks in
[test-execution-report.md](test-documentation/test-execution-report.md) were done:

```powershell
$env:DATABASE_URL="sqlite:///./local.db" ; $env:AUTO_CREATE_TABLES="true"
```

Delete `local.db` afterwards. It is already in `.gitignore`.

## 9. Running the API

```powershell
uvicorn app.main:app --reload                 # development
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

| URL | What it is |
| --- | --- |
| <http://127.0.0.1:8000/> | discovery document with links |
| <http://127.0.0.1:8000/health> | health check |
| <http://127.0.0.1:8000/docs> | Swagger UI |
| <http://127.0.0.1:8000/redoc> | ReDoc |
| <http://127.0.0.1:8000/openapi.json> | raw OpenAPI schema |
| <http://127.0.0.1:8000/dashboard/> | optional dashboard |

If PostgreSQL is down, `/health` answers `503` and `/issues` answers `500` with
`error.type = "database_error"`. That is the intended behaviour, not a crash.

## 10. Postman collection

File: [postman/REST_API_Testing.postman_collection.json](postman/REST_API_Testing.postman_collection.json)
(collection name *REST API Testing & Database Validation*, schema v2.1.0)

### Import and run

1. Start the API on `http://127.0.0.1:8000`.
2. In Postman: **Collections > Import** and pick the file.
3. Check the collection variable `baseUrl` in the **Variables** tab.
4. Run the whole collection with the **Collection Runner**, or send requests one at a time.

### Run headlessly with Newman

```powershell
npm install -g newman
newman run postman/REST_API_Testing.postman_collection.json
```

### How the chaining works

No request contains a hardcoded database id. Ids are captured from responses into collection
variables and reused:

| Variable | Set by | Used by |
| --- | --- | --- |
| `baseUrl` | collection definition | every request |
| `issueId` | `02 - Create a valid defect` | requests 08, 10, 11, 12 |
| `severityIssueIds` | `03 - Create a defect with every supported severity` | the severity sweep assertions |
| `deletedIssueId` | `12 - Delete a defect` | `13 - Retrieve a deleted defect` |

Requests 08 and 12 create their own defect in a pre-request script when `issueId` is empty, so
they also work when you send them on their own. The other requests in folder 5 assume request 02
ran first - that is the one ordering dependency in the collection, and it is stated in the
collection description.

### What the 16 requests assert

| # | Request | Asserts |
| --- | --- | --- |
| 01 | Health check | `200`, JSON content type, `status = ok`, database connected |
| 02 | Create a valid defect | `201`, generated id, fields echoed back, UTC timestamps; captures `issueId` |
| 03 | Create with every severity | one defect per severity, all `201`, ids stored in `severityIssueIds` |
| 04 | Create with missing required fields | `422`, every required field listed, no internals leaked |
| 05 | Create with an invalid severity | `422`, `severity` reported in the details |
| 06 | Create with a 2-character title | `422`, `title` reported (boundary: minimum is 3) |
| 07 | Retrieve all defects | `200`, pagination metadata, item schema, ISO-8601 UTC timestamps |
| 08 | Retrieve a defect by id | `200`, id matches, values inside the documented domains |
| 09 | Retrieve a nonexistent defect | `404`, `error.type = not_found` |
| 10 | Update a defect status | `200`, status changed, other fields intact; a follow-up `GET` proves it persisted |
| 11 | Update with invalid data | `422`, and a follow-up `GET` proves the record was not modified |
| 12 | Delete a defect | `204`, empty body; the id is remembered in `deletedIssueId` |
| 13 | Retrieve a deleted defect | `404`, `not_found` |
| 14 | Filter by severity and status | every returned item matches; an unmatched filter returns `total = 0` |
| 15 | Pagination and sorting | page metadata, page size respected, ids descending, page 2 does not overlap page 1, `page_size=1000` returns `422` |
| 16 | Statistics | all buckets present, status and severity sums equal the total |

Last recorded run (2026-10-23, Newman against the live server): **0 assertion failures**. Newman
reported 21 HTTP requests because several requests fire a follow-up `GET` with `pm.sendRequest`
to prove a change did or did not persist; the collection itself contains **16** request items in
6 folders. Full per-request evidence is in
[test-execution-report.md](test-documentation/test-execution-report.md) section 4.

## 11. pytest and coverage

```powershell
pytest -v
pytest -q
pytest tests/test_issues.py -v
pytest -k "validation" -v
pytest --cov=app --cov-report=term-missing
pytest --cov=app --cov-report=html            # writes htmlcov/index.html

# PostgreSQL integration tests (opt-in, needs a *_test database)
$env:TEST_DATABASE_URL="postgresql+psycopg2://postgres:<password>@localhost:5432/defect_tracker_test"
pytest tests/integration -v -m integration
```

### Latest result

```text
121 passed, 5 skipped in ~4-6s
TOTAL coverage: 92% (410 statements, 34 missed)
```

The skipped tests are the five PostgreSQL integration tests, which require `TEST_DATABASE_URL`.
No test is skipped to make the build green.

| File | Focus | Tests |
| --- | --- | --- |
| `tests/test_health.py` | health, root, OpenAPI schema, degraded database | 4 |
| `tests/test_issues.py` | CRUD, validation, boundaries, filters, sorting, pagination, raw SQL checks | 109 |
| `tests/test_stats.py` | statistics accuracy, consistency after update and delete | 5 |
| `tests/test_errors.py` | error contract, database failure, 404 and 405 | 3 |
| `tests/integration/test_postgres_integration.py` | real PostgreSQL behaviour | 5 (skipped by default) |

**What the suite covers beyond the happy path**

- *Negative*: missing required fields, invalid enum values, wrong data types, unknown ids, an
  unknown route, a method that is not allowed, and an empty PATCH body.
- *Boundary*: title of 2 / 3 / 200 / 201 characters, description of 2000 / 2001, `page = 0`,
  `page_size` of 0 / 1 / 100 / 101 / 1000, a page number past the last page, and `search` at
  200 / 201 characters.
- *Persistence and non-mutation*: a successful PATCH is re-read with SQL; a rejected PATCH is
  followed by a `GET` that proves the record is byte-for-byte unchanged; a rejected POST leaves
  the row count at 0. A `null` for a non-nullable column (`title`, `severity`, `status`,
  `category`, `environment`) is rejected with `422`, while `description` can be cleared with an
  explicit `null` - the two are asserted separately.
- *Database-level*: raw `INSERT` statements that bypass the API are still rejected by the
  `CHECK` constraints and `NOT NULL`, and the six expected indexes are present.
- *Contract*: `error.details[].field` names the offending parameter for both body and query
  errors.

**Isolation.** Each test builds a fresh in-memory SQLite database with `StaticPool` and drops it
afterwards. The `client` fixture overrides `get_db` and then asserts
`db_session.get_bind().dialect.name == "sqlite"`, so a misconfigured run fails loudly instead of
touching a real database.

### SQLite vs PostgreSQL

| | SQLite unit/API suite | PostgreSQL integration suite |
| --- | --- | --- |
| Location | `tests/` (excluding `tests/integration/`) | `tests/integration/` |
| Runs by default | Yes | No - skipped unless `TEST_DATABASE_URL` is set |
| Database | In-memory, one per test | A real database whose name ends with `_test` |
| Verifies | HTTP behaviour, validation, error contract, filtering, pagination, aggregates, and `CHECK` constraints enforced by SQLite | `timestamptz` round-tripping with a real UTC offset, native PostgreSQL constraint violations, and `updated_at` changing on PATCH |

The two suites are kept apart on purpose. SQLite is the default test runner in CI, but it does
not behave exactly like PostgreSQL, so anything storage-specific is checked in the integration
suite instead of being assumed.

## 12. SQL validation queries

Queries live in [sql/validation_queries.sql](sql/validation_queries.sql) and are read-only.

```powershell
psql -U postgres -d defect_tracker -f sql/validation_queries.sql
```

The checks that matter most, and what "correct" looks like:

```sql
-- 1. The row the API just returned really exists, with the same values.
SELECT id, title, severity, status, category, environment,
       created_at AT TIME ZONE 'UTC' AS created_at_utc
FROM issues
WHERE id = 1;

-- 2. No column ever holds a value outside its documented set. Expect 0 rows.
SELECT 'invalid severity' AS problem, id, severity AS value FROM issues
WHERE severity NOT IN ('Low', 'Medium', 'High', 'Critical')
UNION ALL
SELECT 'invalid status', id, status FROM issues
WHERE status NOT IN ('Open', 'In Progress', 'Closed');

-- 3. Titles are within the documented range. Expect 0 rows.
SELECT id, title FROM issues
WHERE title IS NULL OR length(trim(title)) < 3 OR length(title) > 200;

-- 4. updated_at never precedes created_at. Expect 0 rows.
SELECT id, created_at, updated_at FROM issues WHERE updated_at < created_at;

-- 5. After PATCH /issues/1 {"status":"In Progress"} the row shows the new value
--    and a newer updated_at. After DELETE /issues/1 this returns 0 rows.
SELECT id, status, created_at, updated_at, (updated_at > created_at) AS was_updated
FROM issues WHERE id = 1;

-- 6. These aggregates must equal GET /issues/stats.
SELECT status,   COUNT(*) AS total FROM issues GROUP BY status   ORDER BY status;
SELECT severity, COUNT(*) AS total FROM issues GROUP BY severity ORDER BY severity;

-- 7. Duplicate detection. Nothing in the schema prevents duplicates on purpose
--    (testers legitimately re-report similar defects), so they are reported here.
SELECT title, severity, environment, COUNT(*) AS occurrences, ARRAY_AGG(id ORDER BY id) AS issue_ids
FROM issues
GROUP BY title, severity, environment
HAVING COUNT(*) > 1
ORDER BY occurrences DESC;
```

The step-by-step workflow - create, capture the id, `GET`, SQL check, update, SQL check, delete,
verify - with a table of expected values is in
[test-documentation/database-validation.md](test-documentation/database-validation.md). Its
PostgreSQL section is still marked *pending*, because this was built on a machine without a
PostgreSQL server.

## 13. Test documentation

| Document | What it contains |
| --- | --- |
| [test-plan.md](test-documentation/test-plan.md) | Objectives, scope, entry and exit criteria, test strategy per level, risks |
| [test-cases.csv](test-documentation/test-cases.csv) | 84 test cases with steps, test data, expected and actual results |
| [database-validation.md](test-documentation/database-validation.md) | The API-versus-database validation workflow and the recorded results |
| [test-execution-report.md](test-documentation/test-execution-report.md) | Environment, commands, actual results, coverage, exit-criteria assessment |
| [defect-report-template.md](test-documentation/defect-report-template.md) | The report format, severity and priority definitions, plus one clearly labelled fictional example |
| [PROJECT_TECHNICAL_REPORT.md](PROJECT_TECHNICAL_REPORT.md) | A longer technical write-up of the same implementation |
| [PROJECT_NOTES.md](PROJECT_NOTES.md) | Design decisions, the API-testing versus database-validation distinction, limitations and next steps |
| [REPOSITORY_AUDIT.md](REPOSITORY_AUDIT.md) | Findings from the repository quality audit: confirmed defects, documentation inconsistencies and their fixes |

## 14. Known limitations

1. **No authentication or authorisation.** Every endpoint is open. This is fine for local
   development and testing practice, and unsuitable for anything else.
2. **The PostgreSQL-specific verification has not been executed.** The integration tests and the
   SQL validation queries are written and ready, but no PostgreSQL server was available when the
   project was put together, so both are marked *pending* rather than passing.
3. **No migration framework.** The schema is created by `app.db_init` or `sql/schema.sql`.
   Changing a column means changing both `app/models.py` and `sql/schema.sql` and recreating the
   table; there is no Alembic history.
4. **SQLite is not PostgreSQL.** `CHECK` violations, `timestamptz` handling and error wording can
   differ between the two. The unit suite runs on SQLite, so those differences are covered only
   by the opt-in integration suite.
5. **`sql/schema.sql` and `app/models.py` are two copies of one schema.** Nothing checks that
   they stay identical.
6. **`description` has no database-level length limit.** Pydantic caps it at 2000 characters, but
   the column is `TEXT`, so a raw `INSERT` could store more.
7. **Deletes are physical and untracked.** There is no soft delete and no audit trail.
8. **`updated_at` is maintained by the application**, plus an optional PostgreSQL trigger. A
   direct SQL update that bypasses the trigger will not refresh it.
9. **Text search is a simple `ILIKE` match**, not full-text search, so it will not scale to a
   large table. There is no index on `description` either.
10. **No load, stress or security testing has been performed.** The security section of
    `PROJECT_TECHNICAL_REPORT.md` describes what the code does; it is not a security audit.
11. **The dashboard is an untested convenience UI.** It is verified to load and to talk to the
    API, nothing more.
12. **CORS defaults to `*`.** `CORS_ORIGINS` is unrestricted out of the box (with
    `allow_credentials=False`), which is convenient locally but too permissive to expose on a
    network. Set it to the exact origins you need before deploying anywhere reachable.
13. **This is a portfolio project, not a production deployment.** No reverse proxy, no TLS, no
    rate limiting, no structured logging pipeline and no operational runbook are provided.

## 15. Next improvements

The order below is roughly the order I would do them in - smallest useful change first.

1. **Run the PostgreSQL verification on a machine that has PostgreSQL**, and paste the real
   output into `database-validation.md`. This closes the largest gap in the project.
2. **Split the API docs out of the errors module if it grows.** (A coverage gate now exists in
   `.github/workflows/tests.yml` - `--cov-fail-under=85` - so a large coverage drop fails the
   build.)
3. **Add a test that keeps `app/models.py` and `sql/schema.sql` in sync** - for example by
   comparing `inspect(engine).get_check_constraints()` against the constraint names in the SQL
   file.
4. **Add the missing `CHECK` on `description` length** so the database enforces what Pydantic
   already enforces.
5. **Introduce Alembic** once the schema starts changing, and stop hand-maintaining two copies.
6. **Add authentication** (an API key or JWT) with a role for testers and one for administrators,
   before this is exposed anywhere.
7. **Add soft delete plus an audit table**, which is what a real defect tracker needs before
   anyone is allowed to delete records.
8. **Replace `ILIKE` with a PostgreSQL `tsvector` or trigram index** if the table grows.
9. **Add contract testing** (`schemathesis` against `openapi.json`) and a small load test
   (`k6` or `Locust`) to cover the two areas currently untested.
10. **Extend the statistics endpoint** with per-category counts and the average age of open
    defects.

These are ideas, not implemented features. Nothing in section 14 or 15 is claimed as done.

## 16. What this project demonstrates

Short and specific - each point is something the code itself shows, so it can be pointed at
during a review:

- **Validation belongs in two places.** Pydantic gives a readable `422`; the database `CHECK`
  constraints mean a raw `INSERT` cannot store a severity that the API would have rejected. Both
  are tested, including by bypassing the API entirely.
- **Route order is a real bug source.** `/issues/stats` only works because the statistics router
  is registered before the issues router. There is a test that fails if that order changes.
- **Pagination needs a tie-breaker.** Sorting by a low-cardinality column such as `severity`
  leaves rows in an arbitrary order, so `id` is appended as a secondary sort key.
- **`PATCH` is not `PUT`.** Using `model_dump(exclude_unset=True)` is what makes "field omitted"
  different from "field set to null", and there are tests for both.
- **A `201` proves nothing about the database.** Every persistence claim in the suite is backed
  by a SQL query against the stored row, not by the API response.
- **Test isolation has to be enforced, not assumed.** The fixture asserts the dialect is SQLite
  before handing out a client, and the integration suite refuses to run against a database whose
  name does not end in `_test`.

If you are reading this repository as an interviewer, these are the points I would want to be
asked about.

## 17. License

No license has been chosen for this repository, so **no license is currently granted** (all
rights reserved by default). If you want to reuse this code, open an issue and a license can be
added.
