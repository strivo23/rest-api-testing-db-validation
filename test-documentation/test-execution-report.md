# Test Execution Report

| Field | Value |
| --- | --- |
| Project | REST API Testing & Database Validation Platform |
| Version under test | 1.0.0 |
| Execution date | 2026-10-23 |
| Executed by | Automated suites + QA engineer (portfolio project) |
| Build / working copy | local working copy, no commit hash recorded |
| Result | **PASS - 0 failures in the executed suites** |

All numbers in this report were produced by actual command runs in the environment
described below. Nothing is estimated. The one part that could not be executed here
(the PostgreSQL integration tests) is listed explicitly as **skipped / pending** together
with the reason.

## 1. Test environment

| Item | Value |
| --- | --- |
| Operating system | Windows (Windows 11, PowerShell 5.1 shell) |
| Python | 3.12.9 (virtual environment `.venv`) |
| FastAPI | 0.161.1 |
| Starlette | 1.9.0 |
| Uvicorn | 0.54.0 |
| SQLAlchemy | 2.1.6 |
| Pydantic | 2.14.1 |
| psycopg2-binary | 2.9.13 (driver installed, PostgreSQL server not available) |
| pytest / pytest-cov | 9.1.1 / 7.1.0 |
| Postman collection runner | Newman, run through Node.js v24.14.0 (installed into a temporary folder, not part of the project) |
| Application database | PostgreSQL required for production use; not installed in this environment |
| Database used for execution | in-memory SQLite (pytest suite) and a throwaway SQLite file (live server verification) |

## 2. Automated test suite (pytest)

### Commands

```powershell
pytest -v
pytest --cov=app --cov-report=term-missing
```

### Result

```text
collected 120 items

tests/test_errors.py ....................... 3 tests
tests/test_health.py ....................... 4 tests
tests/test_issues.py ...................... 103 tests
tests/test_stats.py ........................ 5 tests
tests/integration/test_postgres_integration.py sssss  5 skipped

115 passed, 5 skipped, 1 warning in 3.93s
```

| Metric | Value |
| --- | --- |
| Test cases executed | 115 |
| Passed | 115 |
| Failed | 0 |
| Errors | 0 |
| Skipped | 5 (PostgreSQL integration tests - `TEST_DATABASE_URL` not configured) |
| Warnings | 1 (Starlette deprecation notice about the `httpx` TestClient shim inside FastAPI itself, not project code) |
| Execution time | 3.93 s |

### Suite contents

| File | Focus | Test cases |
| --- | --- | --- |
| `tests/test_health.py` | Health check, root endpoint, OpenAPI schema, degraded database | 4 |
| `tests/test_issues.py` | Create/read/update/delete, validation, boundary values, filtering, sorting, pagination, SQL constraints | 103 |
| `tests/test_stats.py` | Statistics accuracy, consistency after update/delete, route ordering | 5 |
| `tests/test_errors.py` | Global error contract, database failure handling, 404/405 | 3 |
| `tests/integration/test_postgres_integration.py` | PostgreSQL specific behaviour (skipped) | 5 |
| **Total collected** | | **120** |

## 3. Coverage report (pytest-cov)

```text
Name                     Stmts   Miss  Cover   Missing
------------------------------------------------------
app\__init__.py              1      0   100%
app\config.py               22      0   100%
app\crud.py                 61      1    98%   99
app\database.py             27      8    70%   31, 45-52
app\db_init.py              15     15     0%   11-34
app\errors.py               41      2    95%   109-110
app\main.py                 33      3    91%   33-35
app\models.py               48      0   100%
app\routes\__init__.py       2      0   100%
app\routes\health.py        18      0   100%
app\routes\issues.py        34      0   100%
app\routes\stats.py          9      0   100%
app\schemas.py              92      6    93%   45, 68, 71, 79-80, 110
------------------------------------------------------
TOTAL                      403     35    91%
```

Notes on the uncovered lines (all intentional):

| Module | Uncovered | Reason |
| --- | --- | --- |
| `app/db_init.py` | CLI `main()` entry point | Executed manually (`python -m app.db_init`) - see section 5 |
| `app/database.py` | engine creation for a PostgreSQL URL and the pool branch | Only reachable with a real PostgreSQL server |
| `app/main.py` | `AUTO_CREATE_TABLES=true` startup branch | Optional convenience flag, exercised manually |
| `app/schemas.py` | Some defensive validators (`None` handling, `db_init` example) | Defensive branches kept for correctness |
| `app/errors.py` | Fallback generic exception handler | Deliberately hard to trigger |

## 4. Postman collection execution (Newman)

```powershell
newman run postman/REST_API_Testing.postman_collection.json
```

Executed twice against the live server (`uvicorn app.main:app` on `http://127.0.0.1:8000`).

| Metric | Run 1 | Run 2 |
| --- | --- | --- |
| Iterations | 1 | 1 |
| Requests executed | 21 | 21 |
| Requests failed | 0 | 0 |
| Test scripts executed | 16 | 16 |
| Test scripts failed | 0 | 0 |
| Pre-request scripts executed | 19 | 19 |
| Pre-request scripts failed | 0 | 0 |
| Assertions executed | 69 | 69 |
| Assertions failed | 0 | 0 |
| Total run duration | 1387 ms | - |
| Average response time | 15 ms (min 3 ms, max 61 ms) | - |

Per-request evidence from the JSON report of run 2 (all requests `pass`):

| Request | HTTP result |
| --- | --- |
| 01 - Health check | 200 |
| 02 - Create a valid defect | 201 |
| 03 - Create a defect with every supported severity | 201 (plus 4 sweep requests, all 201) |
| 04 - Create a defect with missing required fields | 422 |
| 05 - Create a defect with an invalid severity | 422 |
| 06 - Create a defect with a title shorter than 3 characters | 422 |
| 07 - Retrieve all defects | 200 |
| 08 - Retrieve a defect by ID | 200 |
| 09 - Retrieve a nonexistent defect | 404 |
| 10 - Update a defect status | 200 (plus follow-up GET 200) |
| 11 - Update a defect with invalid data | 422 (plus follow-up GET 200) |
| 12 - Delete a defect | 204 |
| 13 - Retrieve a deleted defect | 404 |
| 14 - Filter defects by severity and status | 200 (plus negative filter 200 with total 0) |
| 15 - Test pagination and sorting | 200 (plus page 2 and boundary checks) |
| 16 - Retrieve defect statistics | 200 |

## 5. Live server verification

Performed with the real server, not the test client:

| Step | Command / request | Observed result | Status |
| --- | --- | --- | --- |
| Schema initialisation | `python -m app.db_init` | `Tables available: issues` | Pass |
| Server start | `uvicorn app.main:app --host 127.0.0.1 --port 8000` | `Application startup complete`, listening on 127.0.0.1:8000 | Pass |
| Health | `GET /health` | `200 {"status":"ok","database":"connected","dialect":"sqlite","version":"1.0.0"}` | Pass |
| Create | `POST /issues` (severity High) | `201`, `id=1`, `created_at=2026-10-23T04:25:30.666261Z` | Pass |
| Read | `GET /issues/1` | `200`, title `Live smoke test defect` | Pass |
| Update | `PATCH /issues/1 {"status":"In Progress"}` | `200`, status `In Progress`, `updated_at=2026-10-23T04:25:30.711037Z` | Pass |
| List | `GET /issues?page=1&page_size=5&sort_by=id&order=desc` | `200`, `total=1`, `pages=1` | Pass |
| Statistics | `GET /issues/stats` | `200 {"total":1,"by_status":{"Open":0,"In Progress":1,"Closed":0},"by_severity":{"Low":0,"Medium":0,"High":1,"Critical":0}}` | Pass |
| Not found | `GET /issues/999999` | `404` | Pass |
| Validation | `POST /issues {"title":"ab","severity":"Blocker",...}` | `422` | Pass |
| Delete | `DELETE /issues/1` | `204` with an empty body | Pass |
| Read after delete | `GET /issues/1` | `404`, `error.type=not_found` | Pass |
| Swagger UI | `GET /docs` | `200`, `text/html; charset=utf-8` | Pass |
| OpenAPI schema | `GET /openapi.json` | `200` | Pass |
| Dashboard | `GET /dashboard/` | `200`, page title `Defect Tracker Dashboard` present | Pass |

The throwaway database file used for this verification was deleted afterwards. No test or
verification step touched a real development database.

## 6. Defect summary

| Defect ID | Summary | Severity | Status |
| --- | --- | --- | --- |
| - | No defect was found in the delivered version. All executed assertions passed. | - | - |

The suite passed on the complete first run (100 passed, 5 skipped), again after the
error-handling tests were added (103 passed), and again after the boundary and validation
cases were added (115 passed). No failures were hidden or re-run until they passed; no test was
disabled to make the build green.

An **illustrative** defect entry (clearly labelled as fictional) is included in
`test-documentation/defect-report-template.md` to demonstrate the report format. It does
not describe a defect observed in this project.

## 7. Tests not executed here (and why)

| Item | Reason | How to execute |
| --- | --- | --- |
| 5 PostgreSQL integration tests | No PostgreSQL server is installed in this environment (`psql` not available) | Install PostgreSQL, create `defect_tracker_test`, set `TEST_DATABASE_URL`, then run `pytest tests/integration -v -m integration` |
| PostgreSQL SQL validation queries | Same reason | Run `psql -U postgres -d defect_tracker -f sql/validation_queries.sql` and record output in `database-validation.md` section 3.2 |
| Manual exploration of the dashboard | Optional component; verified only that it loads and is served (HTTP 200) | Open http://127.0.0.1:8000/dashboard/ in a browser and create/update/delete a defect |

## 8. Exit criteria assessment

| Exit criterion | Target | Actual | Verdict |
| --- | --- | --- | --- |
| Automated suite executed | 100% of collected tests | 115 executed, 5 skipped (environment), 0 failed | Met |
| Line coverage of `app` | Reported and justified | 91% (35 statements uncovered, each explained in section 3) | Met |
| Postman collection executed | All requests and assertions pass | 21 requests / 69 assertions, 0 failures | Met |
| Open Critical/High defect on a documented core flow | 0 | 0 | Met |
| SQL validation with 0 invalid rows | 0 rows | Pending - requires PostgreSQL (section 7) | Not verifiable here |
| Reports completed with real results | Yes | This report, `database-validation.md`, `test-cases.csv` | Met |

## 9. Risks observed during execution

1. **PostgreSQL unavailable in the build environment.** Mitigated by running the API suite on
   isolated SQLite, keeping the PostgreSQL-specific tests separate, and marking every
   PostgreSQL-dependent result as pending instead of claiming a pass.
2. **Timestamp normalisation across drivers.** SQLite returns naive datetimes; the API
   normalises them to UTC on serialisation and this is asserted
   (`test_create_issue_returns_201_with_generated_id` checks the UTC suffix).
3. **Test isolation.** Each pytest test runs on a fresh in-memory database and the API
   dependency is asserted to be SQLite, so a developer database can never be modified.

## 10. Conclusion

The implemented API meets the documented behaviour for all executed scenarios: 115 automated
tests and 69 Postman assertions pass with 0 failures, coverage is 91%, and the live server
verification confirms create/read/update/list/stats/delete behaviour end to end. The only
open item is the PostgreSQL-specific verification, which requires a PostgreSQL installation
and is fully scripted (`tests/integration/`, `sql/validation_queries.sql`).
