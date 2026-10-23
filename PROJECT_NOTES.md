# Project Notes

Developer notes for the REST API Testing & Database Validation Platform. This file records what
the code actually does and why it was written that way. Everything here describes the current
implementation; anything that is only an idea is explicitly labelled as future work.

The README is the entry point for someone who wants to *use* the project. This file is for
someone who wants to understand the decisions behind it.

---

## 1. What the project is for

The application under test is a small defect tracker: create a defect, read it, change its
status, delete it, and ask for counts grouped by status and severity. That is deliberately
ordinary. The point of the repository is the testing work built around it.

The goal was to practise the full loop a tester actually performs, end to end:

1. Read a written specification and turn it into test cases.
2. Exercise the API over HTTP and assert on the responses.
3. Then open the database and check that the rows match what the API claimed it stored.

Step 3 is the part that is easy to skip and the reason this repository is called a *validation*
platform rather than just an API.

## 2. Architecture decisions found in the code

These are the decisions a reader would notice while going through the source. They are all
visible in the code; the line references point at where.

### 2.1 The layers are separated, and the data layer never speaks HTTP

`app/crud.py` contains only database work. It returns ORM objects or `None`, and it raises no
HTTP errors. The routing layer in `app/routes/` owns status codes, the 404 case, and response
serialisation. `_get_issue_or_404` in
[app/routes/issues.py](app/routes/issues.py)
is the single place that turns "row missing" into `HTTPException(404)`.

**Why:** it keeps `crud.py` callable from a plain pytest function without a request object, and
it means "not found" is decided in exactly one place instead of in six handlers.

### 2.2 Validation happens twice, on purpose

Request bodies are validated by Pydantic in
[app/schemas.py](app/schemas.py)
(enum membership, string lengths, "an empty PATCH is rejected"). The same rules are then encoded
as `CHECK` constraints and `NOT NULL` in
[app/models.py](app/models.py).

**Why the duplication is worth keeping:** the two layers fail differently. Pydantic produces a
readable `422` for an API client. The `CHECK` constraints cover everything that does not go
through the API - a `psql` session, a migration script, a future import job. The tests prove
both: one test posts an invalid severity and expects `422`, and another executes a raw
`INSERT` that bypasses the API and expects the database to reject it.

### 2.3 One error shape for every failure

[app/errors.py](app/errors.py)
registers application-wide exception handlers and renders everything as
`{"error": {"type", "message", "details"}}`. Stack traces, SQL text and credentials are logged
server-side and never returned.

**Why:** a test suite should be able to assert on one error format rather than a different shape
per endpoint. It also means the client cannot accidentally learn about the internals from a
`500`.

The validation handler strips Pydantic's location prefix (`body`, `query`, `path`, ...) from
`error.details[].field`. That is what makes `field` read `title` for a body field and `page` for
a query parameter, instead of `body.title` in one case and `query.page` in the other.

### 2.4 Configuration is typed and never hardcoded

[app/config.py](app/config.py)
defines a `Settings` class read from environment variables or `.env`, cached with `@lru_cache`.
The default connection string points at a *local* PostgreSQL instance with placeholder
credentials; nothing real is committed.

**Why:** the connection string, pool sizes and page-size limits differ between a developer
machine, the test run and whatever machine a reviewer uses. Keeping them in one typed object
means there is a single place to look, and `.env.example` documents every key.

### 2.5 SQLite and PostgreSQL are handled by one engine builder

`build_engine()` in
[app/database.py](app/database.py)
branches on the URL: SQLite gets `check_same_thread=False`, PostgreSQL gets the configured pool
sizes. `pool_pre_ping=True` is set for both so a stale connection is retried instead of failing
the request.

**Why:** the unit suite runs on SQLite and needs no server, but the production target is
PostgreSQL. One builder means the application code does not need to know which one it is
talking to.

### 2.6 Router registration order is load-bearing

[app/main.py](app/main.py)
includes the statistics router before the issues router, and there is a comment saying so.

**Why:** `/issues/stats` and `/issues/{issue_id}` have the same shape. FastAPI matches routes in
registration order, so if the parameterised route came first, `stats` would be captured as an id
and the endpoint would answer `422` instead of returning counts. This is a real ordering
dependency, not a style preference, and there is a test that would fail if the order changed.

### 2.7 Pagination sorts by a stable key

`list_issues` in
[app/crud.py](app/crud.py)
appends `Issue.id.desc()` as a secondary sort key after whatever column the client asked for.

**Why:** sorting by a low-cardinality column such as `severity` leaves rows with equal values in
an undefined order, so the same row could appear on two pages or on none. The tie-breaker makes
paging deterministic.

### 2.8 `PATCH` updates only the fields that were sent

`update_issue` uses `payload.model_dump(exclude_unset=True)`, so a field the client did not
mention is left alone, while an explicit `null` clears a nullable field.

**Why:** that is the difference between `PATCH` and `PUT`, and it is the behaviour a partial
update test needs. There are tests for both the "omitted" case and the "explicit null" case.

### 2.9 Timestamps are UTC and timezone-aware everywhere

`utcnow()` in `app/models.py` returns `datetime.now(timezone.utc)`, the columns are
`DateTime(timezone=True)`, and the tests assert the serialised value carries a UTC designator.

**Why:** "when was this defect raised" is only meaningful with a timezone. SQLite does not store
the offset and returns naive datetimes, so the schema layer normalises on the way out; the
PostgreSQL integration suite is where the real `timestamptz` round-trip is checked.

### 2.10 The app object is created at import time, not in a factory

`app/main.py` builds the `FastAPI` instance at module level and configures optional table
creation through a `lifespan` context manager.

**Why:** it keeps `uvicorn app.main:app` and the pytest `TestClient` pointing at the same object
with no wiring step. A factory would add indirection for no benefit at this size. If the app
grew to need per-environment assembly, a `create_app()` factory is the natural next step.

## 3. Why each tool was chosen for this implementation

| Tool | Why it fits *this* project |
| --- | --- |
| **FastAPI** | The OpenAPI schema is generated from the code, so the documented API cannot drift from the routes without the tests noticing. Its `TestClient` runs the real application in-process, so the pytest suite tests the actual ASGI app rather than a re-implementation. Dependency injection is what makes `get_db` swappable for the in-memory test database. |
| **PostgreSQL** | The project is about verifying persistence, so it targets a real relational database with real constraints: native `CHECK` constraints, `timestamptz`, and indexes that can be inspected with `EXPLAIN`. Running only against SQLite would leave the parts most likely to differ unverified. |
| **SQLAlchemy 2.x** | One set of typed models (`Mapped[...]`) drives both the application queries and the test schema, and `select()` expressions can be reused by the CRUD layer and the aggregate endpoint. The same code path runs on SQLite in tests and PostgreSQL in production, with the differences isolated in `build_engine`. |
| **Pydantic v2** | The API needs enum and length validation with a machine-readable error payload. Pydantic gives that directly, and the consistent error shape in `app/errors.py` is built on top of its `loc`/`msg`/`type` output. |
| **pytest + pytest-cov** | Fixtures make the fresh-database-per-test setup cheap, and parametrised/table-driven cases keep the boundary tests readable. Coverage points at the modules that are not exercised, which is how the uncovered lines in `database.py` and `db_init.py` were identified and explained rather than ignored. |
| **Postman / Newman** | Some assertions are clearer at the HTTP level and by hand: status codes, content types, and "a rejected update did not modify the record". Postman collections are also what a tester is often handed at work, and Newman lets the same collection run without a GUI, which is how the recorded results in `test-execution-report.md` were produced. |

## 4. API testing versus database validation

These are related but they are not the same check, and keeping them separate is the central idea
of the project.

**API testing** asks: *did the service behave correctly over HTTP?* It checks status codes,
response bodies, headers, validation errors, filtering, sorting and pagination. It is entirely
satisfied by the HTTP response. A `201 Created` with the right JSON body passes an API test.

**Database validation** asks: *is the data actually stored the way the API said it was?* It
queries the tables directly and ignores the API response. It catches things an API test cannot:
a handler that returns a success body without committing, a transaction that rolls back
silently, a field that is accepted and then dropped, a timestamp that is stored naive, or a row
that a rejected request modified anyway.

In this repository:

- The **pytest suite** and the **Postman collection** are the API-testing layer. They drive the
  endpoints and assert on responses.
- `sql/validation_queries.sql` and the SQL-backed assertions inside the test suite are the
  database-validation layer. They read the stored rows and compare them with the documented
  expectations.
- The **Postman collection already blurs the line on purpose** where it matters: request 11
  updates a defect with invalid data, expects `422`, and then issues a follow-up `GET` to prove
  the record was left untouched. That follow-up is a persistence check, not just a status-code
  check.

The practical rule used throughout: a write is not considered verified until it has been read
back out of the database, not just out of the response.

## 5. Current limitations

These are the honest gaps in the current version. Most of them are also listed in the README;
they are repeated here because they are the things a reader should know before treating the
project as more complete than it is.

1. **No authentication or authorisation.** Every endpoint is open to anyone who can reach it.
2. **The PostgreSQL-specific verification has not been executed.** The integration tests and the
   SQL validation queries are written and scripted, but the environment this was built in has no
   PostgreSQL server, so those results are marked *pending*, not passed.
3. **No migration framework.** The schema is created by `python -m app.db_init` or by
   `sql/schema.sql`. There is no Alembic history, so a column change means editing both files and
   recreating the table.
4. **`app/models.py` and `sql/schema.sql` are two descriptions of one schema.** Nothing enforces
   that they agree; keeping them in step is a manual convention.
5. **SQLite is not PostgreSQL in the default test run.** `CHECK` enforcement wording,
   `timestamptz` handling and some type behaviour differ. Those differences are only exercised by
   the opt-in integration suite.
6. **`description` has no database-level length limit.** Pydantic caps it at 2000 characters, but
   the column is `TEXT`, so a raw `INSERT` could store more.
7. **Deletes are physical and untracked.** There is no soft delete and no audit trail.
8. **`updated_at` is maintained by the application** (plus an optional PostgreSQL trigger). A
   direct SQL update that bypasses the trigger will not refresh it.
9. **Text search is a plain `ILIKE` match**, with no index on `description`, so it will not scale.
10. **No performance, load or security testing.** The code avoids leaking internals in responses,
    but that is a design choice, not the result of a security assessment.
11. **The dashboard is an untested convenience UI.** Only that it loads and talks to the API has
    been checked.

## 6. Practical improvements to do next

Ordered roughly smallest-first. Everything in this section is **future work**, not something that
has been built.

- [ ] **Run the PostgreSQL verification on a machine that has PostgreSQL** and record the real
      output in `test-documentation/database-validation.md`. This closes the biggest gap.
- [ ] **Add a coverage floor to the GitHub Actions workflow** (for example
      `--cov-fail-under=90`) so coverage cannot silently regress.
- [ ] **Add a test that keeps `app/models.py` and `sql/schema.sql` in sync** - compare the
      constraint names from `inspect(engine).get_check_constraints()` with the names in the SQL
      file so the two copies cannot drift.
- [ ] **Add the missing `CHECK` constraint for `description` length** so the database enforces the
      same 2000-character limit that Pydantic already enforces.
- [ ] **Introduce Alembic** once the schema starts changing, and stop hand-maintaining two copies
      of the DDL.
- [ ] **Add authentication** (an API key or JWT) with at least a tester role and an admin role
      before this is exposed anywhere.
- [ ] **Add soft delete plus an audit table**, which is what a defect tracker needs before anyone
      is allowed to delete a record.
- [ ] **Replace `ILIKE` with a PostgreSQL `tsvector` or trigram index** if the table grows, and
      mark the `search` test as the one that would need updating.
- [ ] **Add a contract test** (for example `schemathesis` against `/openapi.json`) and a small
      load test to cover the two areas that currently have no coverage at all.
- [ ] **Extend the statistics endpoint** with per-category counts and the average age of open
      defects, and add the matching `test_stats.py` cases.
