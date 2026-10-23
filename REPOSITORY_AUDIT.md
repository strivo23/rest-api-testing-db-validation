# Repository Quality Audit

| Field | Value |
| --- | --- |
| Repository | <https://github.com/strivo23/rest-api-testing-db-validation> |
| Project | REST API Testing & Database Validation Platform |
| Audited revision | `main` @ `d7fe203` (plus local uncommitted fixes, see FIX-01 / FIX-02) |
| Audit date | 2026-10-23 |
| Audit scope | Documentation, application code, tests, SQL, Postman collection, CI |

This document records what was inspected, what was found, what was fixed, and what is
deliberately left as a known limitation. Findings are separated into **confirmed defects**
(reproduced in this environment), **documentation inconsistencies**, and **maintainability /
optional** items. Every claim below is either backed by a command run in this environment or is
explicitly labelled as a potential risk.

## 0. What was inspected and how

| Area | Command / method | Outcome |
| --- | --- | --- |
| Git state | `git status`, `git branch`, `git log`, `git remote -v` | `main` @ `d7fe203`, remote = `origin`, 3 files modified locally |
| Application code | Full read of `app/*.py`, `app/routes/*.py` | see Phase 3 findings |
| Tests | Full read of `tests/**` | see Phase 4 findings |
| SQL | Read of `sql/schema.sql`, `sql/validation_queries.sql` | schema/vs model comparison below |
| Postman | Structural inspection of the collection + `pm.sendRequest` count | no contract mismatch found |
| CI | Read of `.github/workflows/tests.yml` | see Phase 5 findings |
| Test run | `pytest -q --cov=app --cov-report=term-missing` | **121 passed, 5 skipped, 92%** (after fixes) |

An earlier automated cross-check of the Postman collection and the SQL scripts against the API
contract found **no** assertion/response mismatches, **no** broken collection-variable chaining
and **no** hardcoded ids; `validation_queries.sql` contains only read-only queries (its single
`DELETE` is commented out as a labelled cleanup step). That result is consistent with the
manual schema comparison recorded in F-09.

---

## 1. Confirmed defects (reproduced in this environment)

### FIX-01 — `PATCH` with an explicit `null` on a `NOT NULL` column returned `500` instead of `422`

| Attribute | Detail |
| --- | --- |
| Severity | **Major** |
| Status | **Fixed** |
| Type | Confirmed bug — reproduced |
| File / location | `app/schemas.py`, `class IssueUpdate` |
| Also affects | `app/routes/issues.py` (`PATCH /issues/{id}`), which correctly lets the schema reject the payload |

**Evidence (before the fix).** A scratch probe (`POST` then one `PATCH` per field, run through
the real `TestClient` and the real dependency graph) produced:

```text
POST status: 201
PATCH {'title': null}       -> 500
PATCH {'severity': null}    -> 500
PATCH {'status': null}      -> 500
PATCH {'category': null}    -> 500
PATCH {'environment': null} -> 500
PATCH {'description': null} -> 500   # PendingRollbackError cascaded from the first failure
```

The server log showed `IntegrityError ... NOT NULL constraint failed: issues.title` on
`UPDATE issues SET title=?, updated_at=?`, surfaced to the client as
`{"error": {"type": "database_error", ...}}`.

**Root cause.** Every field of `IssueUpdate` was annotated `X | None = None` to mean "optional".
In Pydantic v2 that also accepts an *explicit* `null`, and the validators returned `None`
unchanged, so the `None` reached the database. `description` is genuinely nullable, the other
five columns are `NOT NULL`.

**Why it matters.** A malformed client request produced a `500`, which (a) misreports a client
error as a server fault, (b) makes the error contract inconsistent with the `422` returned for
every other invalid payload, and (c) left the shared session needing a rollback. A tester
following the documented contract would file this as a defect.

**Fix.** `title` now rejects `None` explicitly, and a `_reject_null` validator covers
`severity`, `status`, `category`, `environment`. `description` still accepts `null` (documented
behaviour: clear the field).

**Verified after the fix.** The same probe produced:

```text
PATCH {'title': null}       -> 422  error.details[0].field == "title"
PATCH {'severity': null}    -> 422  ... field == "severity"
PATCH {'status': null}      -> 422  ... field == "status"
PATCH {'category': null}    -> 422  ... field == "category"
PATCH {'environment': null} -> 422  ... field == "environment"
PATCH {'description': null} -> 200  description is null, row unchanged elsewhere
```

**Regression test added.** `tests/test_issues.py::test_patch_issue_rejects_explicit_null_for_not_null_columns`
(parametrised over all five columns) asserts the `422`, the reported field name, and that the
stored record is unchanged.

---

### FIX-02 — The pytest `get_db` override did not mirror the production rollback

| Attribute | Detail |
| --- | --- |
| Severity | **Major** |
| Status | **Fixed** |
| Type | Confirmed defect in the test harness — reproduced |
| File / location | `tests/conftest.py`, `client` fixture → `override_get_db` |

**Evidence.** While reproducing FIX-01, the first failing `PATCH` was followed by
`PendingRollbackError` on every later request *within the same test*. The production dependency
`app/database.py::get_db` wraps its `yield` in `try/except Exception: db.rollback(); raise`,
but the test override was a bare `yield db_session`.

**Why it matters.** A test harness that does not reproduce production transaction semantics can
mask exactly the kind of failure found in FIX-01, and can make tests pass for the wrong reason.

**Fix.** `override_get_db` now mirrors the rollback. It deliberately does **not** call
`db_session.close()`, because the `db_session` fixture owns the session lifecycle so tests can
still query the database after a request.

**Regression test added.**
`tests/test_issues.py::test_rejected_patch_does_not_poison_the_session_for_later_requests`.

---

## 2. Documentation inconsistencies

### F-03 — Static, stale badges in `README.md`

| Attribute | Detail |
| --- | --- |
| Severity | **Moderate** |
| Status | **Fixed** |
| Type | Documentation inconsistency — reproduced |
| File / location | `README.md` lines 11-17 |

**Evidence.** The badges were hardcoded snapshots: `tests-115 passed`, `coverage-91%`,
`FastAPI-0.161`. After FIX-01/FIX-02 the suite runs 121 tests at 92% coverage. The
`FastAPI-0.161` badge also contradicted `requirements.txt`, which declares
`fastapi>=0.110,<1.0`.

**Why it matters.** A recruiter reading the README sees a number that silently becomes wrong
after the next commit; the project has a real CI workflow that could report this honestly.

**Fix.** The stale test-count/coverage/FastAPI-version badges were replaced by a genuine GitHub
Actions status badge pointing at `.github/workflows/tests.yml`. The version-free
Python/PostgreSQL badges were kept.

### F-04 — `README.md` and `PROJECT_TECHNICAL_REPORT.md` recorded pre-fix test totals

| Attribute | Detail |
| --- | --- |
| Severity | **Moderate** |
| Status | **Fixed** |
| Type | Documentation inconsistency — reproduced |
| File / location | `README.md` §1, §11; `PROJECT_TECHNICAL_REPORT.md` §lines 703-735, 1060, 1087-1122; `test-documentation/test-execution-report.md` §2-3 |

**Evidence.** The recorded figures were `115 passed` / `403 statements` / `35 missed` / `91%`
and `tests/test_issues.py = 103 tests`. The post-fix run is 121 passed / 410 statements /
34 missed / 92% / `test_issues.py = 109 tests`.

**Fix.** All three documents were updated to the numbers produced by an actual re-run
(Phase 6), and the execution report now states the revision it refers to.

### F-05 — "production-style" / "production-ready" wording implies guarantees the project does not have

| Attribute | Detail |
| --- | --- |
| Severity | **Moderate** |
| Status | **Fixed** |
| Type | Documentation inconsistency — reproduced |
| File / location | `PROJECT_TECHNICAL_REPORT.md` lines 44, 1078, 1087, 1094; `README.md` §2 ("PostgreSQL in production") |

**Evidence.** `grep` found `production-style` at lines 44 and 1087 and a "production-ready"
heading at 1078; the README described SQLAlchemy as running "against SQLite in tests and
PostgreSQL in production".

**Why it matters.** The README's own §14 states there is no authentication, no migrations and
no load/security testing. Calling it "production-ready" contradicts the document it sits in.

**Fix.** Reworded to "portfolio project" / "the deployment target" language. `README.md` §14
item 1 (no authentication) is unchanged and still explicit.

### F-06 — The README mixes "16 requests" and "21 requests" for the same collection

| Attribute | Detail |
| --- | --- |
| Severity | **Minor** |
| Status | **Fixed** |
| Type | Documentation inconsistency — reproduced |
| File / location | `README.md` §10 (lines 254, 438-461) |

**Evidence.** The collection file contains exactly **16** request items (`grep -c '"request":'`
= 16), and the README lists 16 in the structure tree and the assertion table. The Newman
summary line says "21 requests". The difference is real, not an error: the collection uses
`pm.sendRequest` (8 occurrences) for the follow-up `GET` checks and the severity sweep, and
Newman counts those programmatic calls too.

**Fix.** The README now states that 16 are collection requests and that Newman's higher count
includes the `pm.sendRequest` follow-ups, so the two numbers no longer look contradictory.

### F-07 — `requirements.txt` declares ranges, so the installed versions are not reproducible

| Attribute | Detail |
| --- | --- |
| Severity | **Moderate** |
| Status | **Mitigated (documented), not changed** |
| Type | Maintainability concern / documentation |
| File / location | `requirements.txt` |

**Evidence.** `requirements.txt` uses ranges (`fastapi>=0.110,<1.0`, `pytest>=8.0`, …). In this
environment they resolved to FastAPI 0.161.1, SQLAlchemy 2.1.6, Pydantic 2.14.1, pytest 9.1.1 -
far ahead of the lower bounds. Nothing in the repository stated which versions were tested.

**Why it matters.** "Install and it works" is not guaranteed across two different machines if
the ranges resolve differently.

**Decision.** No lock file was added. The tested environment is now described explicitly in
`test-documentation/test-execution-report.md` §1 and the README points to it, which is the
alternative the audit brief allows. A full lock file would pin versions (e.g. pytest 9.x) that
contradict the declared `pytest>=8.0` / Python 3.11+ support, so it was not the right tool here.

### F-08 — `README.md` §7 "Setup on Windows" is single-platform

| Attribute | Detail |
| --- | --- |
| Severity | **Minor** |
| Status | **Fixed** |
| Type | Usability / documentation |
| File / location | `README.md` §7 |

**Fix.** Added a short one-line POSIX equivalent (`python -m venv .venv` / `source
.venv/bin/activate` / `.venv/bin/python -m pytest`) so the section is not Windows-exclusive.
No personal machine paths exist anywhere in the repository (verified by search).

---

## 3. Implementation review (Phase 3) — remaining dimensions

The following were reviewed and found **correct**; they are recorded so the audit shows what was
checked, not only what was broken.

| Dimension | Assessment |
| --- | --- |
| HTTP methods / status codes | `POST` → 201, `GET` → 200, `PATCH` → 200, `DELETE` → 204 with empty body, `GET /health` → 200/503. All match `README.md` §4. |
| Transaction handling | `get_db` rolls back on exception and always closes; `crud.py` owns the commit. Verified by the FIX-02 test. |
| Filter / sort / search / pagination | `_apply_filters` uses `ilike` on title-or-description; `sort_by` is a `Literal` allow-list; `page`/`page_size` bounded by `Query(ge=1)` and `settings.max_page_size`. |
| Stable sorting | `order_by(ordering, Issue.id.desc())` — an `id` tie-breaker is always appended, so pagination cannot repeat or skip rows on a low-cardinality sort. |
| Error leakage | `app/errors.py` logs SQLAlchemy errors server-side and returns a generic `database_error`; `tests/test_errors.py` asserts no `traceback`/`sqlalchemy`/`select `/`password` substring appears in any error body. |
| Timestamp semantics | UTC-aware `DateTime(timezone=True)` with `onupdate=utcnow`; `PATCH` also sets `updated_at` explicitly. `test_patch_issue_updates_the_updated_at_timestamp` covers it. |
| Route registration | `stats` router is included before `issues`, so `/issues/stats` is not shadowed by `/issues/{issue_id}`; there is a test for the ordering. |
| Health check | Returns 503 with `status: "degraded"` when the database is unreachable; `tests/test_health.py` uses a deliberately broken engine. |
| Safe defaults | `AUTO_CREATE_TABLES=false`, no credential hardcoded in `app/config.py` (the default URL points at a *local* PostgreSQL instance only). |
| `.env.example` | Placeholders only (`<your_password>`); verified by read. `.gitignore` excludes `.env`/`.env.*` while keeping `.env.example`. |

### F-09 — `app/models.py` vs `sql/schema.sql` compatibility

| Attribute | Detail |
| --- | --- |
| Severity | **Minor** (informational — intentional difference) |
| Status | **Documented** |
| Type | Maintainability concern — verified, not a bug |
| File / location | `app/models.py`, `sql/schema.sql` |

**Evidence.** Column names, types, the five named `CHECK` constraints
(`ck_issues_title_length`, `ck_issues_severity`, `ck_issues_status`, `ck_issues_category`,
`ck_issues_environment`) and the six indexes match between the two definitions.

**Intentional difference.** `sql/schema.sql` additionally installs a PostgreSQL
`BEFORE UPDATE` trigger (`set_issues_updated_at()`) that refreshes `updated_at` at the database
level. `Base.metadata.create_all` (used by `app.db_init` and the tests) cannot express a
trigger, so the two paths are *not* byte-identical by design. The application also sets
`updated_at` in `crud.update_issue`, so the trigger is a belt-and-braces addition, not a
dependency.

**Accidental inconsistency found:** none. The `README.md` §8.3 note and `PROJECT_NOTES.md`
already record this as a documented convention rather than something the code enforces.

---

## 4. Test-suite review (Phase 4)

Checked for: status-code-only assertions, missing negatives/boundaries, order dependence,
fixtures that could touch a real database, missing persistence checks, sort-tie/multi-filter/
empty/pagination-edge coverage.

| Check | Result |
| --- | --- |
| Status-code-only assertions | Mostly paired with body checks; `test_patch_issue_with_invalid_data_returns_422` was status-only, but every one of its five payloads is also covered by a field-naming assertion elsewhere. Left as-is (no meaningful gap). |
| Missing negative / boundary cases | Covered: title 2/3/200/201, description 2000/2001, `page=0`, `page_size` 0/1/100/101/1000, page past the end, `search` 200/201. |
| Order dependence / persistent state | The suite is order-independent: each test gets a fresh in-memory SQLite database via `StaticPool`. |
| Fixtures touching a real database | Prevented — the `client` fixture asserts `db_session.get_bind().dialect.name == "sqlite"` before handing out a client, and the integration module skips unless the URL's database name ends with `_test`. |
| Persistence validation after API ops | Present — several tests re-read the row with raw SQL after a request. |
| Sort ties, multiple filters, empty results, pagination edges | Covered by `test_issues.py` and the statistics tests. |
| **Gap found** | No test asserted the PATCH-with-`null` behaviour (FIX-01) and none asserted that a rejected request leaves the session reusable (FIX-02). **Both added.** |
| PostgreSQL integration safety | `tests/integration/test_postgres_integration.py` refuses to run unless the database name ends with `_test`, then `TRUNCATE`s only that database. Correct and unchanged. |

---

## 5. CI review (Phase 5)

| Attribute | Detail |
| --- | --- |
| File | `.github/workflows/tests.yml` |
| Name | `tests` (matches what a status badge must reference) |
| Matrix | Python 3.11 and 3.12 |
| Steps | install `requirements.txt`, run `pytest -v --cov=app --cov-report=term-missing --cov-report=xml`, upload `coverage.xml` with `if: always()` |
| Failure visibility | Already visible — a failing test fails the job. No hardcoded success. |
| Gap | No coverage gate, so a coverage regression would not fail the build. |

**Change made.** A modest `--cov-fail-under=85` gate was added, consistent with `README.md` §15
item 2 (which already listed a coverage gate as a next step) and comfortably below the current
92%.

**PostgreSQL integration job — added but unverified.** A second, isolated job (`postgres-integration`)
spins up a disposable `postgres:16` service with `POSTGRES_DB=defect_tracker_test`, installs the
dependencies, and runs `pytest tests/integration -v -m integration` with `TEST_DATABASE_URL`
pointing at that service. It runs in parallel with the SQLite job, so it cannot mask a failure in
the main suite. **This job has not been executed on GitHub from this environment; it must not be
described as passing until a real workflow run confirms it.**

**Newman in CI — not added.** A headless Newman run needs Node plus a live server and a
database, and its result would be unverifiable from here. It was deliberately left out rather
than added speculatively.

---

## 6. Security and repository hygiene (Phase 7)

| Check | Result |
| --- | --- |
| `.env` / secrets committed | No. `.gitignore` excludes `.env` and `.env.*`, keeps `.env.example`. Verified trackable-file listing contains no `.env`. |
| `.env.example` content | Placeholders only (`<your_password>`). |
| Virtualenvs / caches / coverage / temp DBs / IDE files | Excluded (`.venv/`, `__pycache__/`, `.pytest_cache/`, `.coverage*`, `coverage.xml`, `htmlcov/`, `*.db`, `.idea/`, `.vscode/`). |
| Sensitive data in docs / commands | None found — no connection strings with real passwords, no tokens. Documentation uses placeholders and relative links. |
| Stack traces / raw SQL in API errors | Not returned; enforced by tests. |
| Authentication | **Not implemented** and clearly documented (`README.md` §14 item 1). |
| CORS | `CORS_ORIGINS` defaults to `*` with `allow_credentials=False`. This is safe for local use but broad; a note was added to the README limitations so the risk is explicit. |
| Files deleted for size | None. |

---

## 7. Prioritised summary

| ID | Severity | Type | Status |
| --- | --- | --- | --- |
| FIX-01 | Major | Confirmed bug — PATCH `null` on `NOT NULL` → 500 | **Fixed + regression test** |
| FIX-02 | Major | Confirmed defect — test harness missing rollback | **Fixed + regression test** |
| F-03 | Moderate | Stale static badges | **Fixed** |
| F-04 | Moderate | Recorded test totals out of date | **Fixed** |
| F-05 | Moderate | "production-style" claims | **Fixed** |
| F-07 | Moderate | Unpinned dependencies | **Mitigated (documented)** |
| F-06 | Minor | "16" vs "21" requests confusion | **Fixed** |
| F-08 | Minor | Windows-only setup section | **Fixed** |
| F-09 | Minor | Two copies of one schema | **Documented (intentional trigger difference)** |
| — | Minor | No coverage gate in CI | **Fixed (`--cov-fail-under=85`)** |
| — | Enhancement | PostgreSQL integration CI job | **Added, unverified** |
| — | Known limitation | No auth, broad default CORS, no migrations | Documented, unchanged |

No Critical-severity finding was identified. The two Major findings were both reproduced and
fixed. Nothing in this audit claims a result that was not produced by a command run in this
environment.
