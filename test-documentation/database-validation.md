# Database Validation Workflow

This document describes how to prove that what the API returns is actually what the
database stores. It covers the end-to-end workflow, the SQL used at every step, and
the results recorded during execution.

Two categories of evidence are used and clearly separated:

- **Executed** - results actually observed in this environment.
- **Pending** - steps that require a local PostgreSQL instance. The build environment for
  this repository had no PostgreSQL server available (`psql` was not installed), so those
  steps are left as a documented, repeatable procedure for the tester.

No result in this document is invented. Any value that was not produced by a real run is
explicitly marked as an example.

## 1. Environment

| Item | Value |
| --- | --- |
| API base URL | http://127.0.0.1:8000 |
| Application database | PostgreSQL (`DATABASE_URL` in `.env`) |
| SQL client | `psql`, pgAdmin or DBeaver |
| Test database (automation) | database whose name ends with `_test` |
| Local API verification run | executed against a throwaway SQLite file (`smoke.db`) because PostgreSQL was not available in the build environment |

## 2. The workflow

### Step 1 - Submit a valid defect through the API

```http
POST /issues
Content-Type: application/json

{
  "title": "Payment screen freezes after tapping Pay",
  "description": "Reproduced 3/3 times on the staging build.",
  "severity": "Critical",
  "status": "Open",
  "category": "Functional",
  "environment": "Android"
}
```

Expected: `HTTP 201` with the generated `id` in the body.

### Step 2 - Capture the generated issue id

Capture the `id` from the response (Postman: collection variable `issueId`;
manual runs: copy the value). Never hardcode an id that you did not just create.

### Step 3 - Retrieve the defect through the API

```http
GET /issues/{id}
```

Expected: `HTTP 200` and the same field values that were submitted.

### Step 4 - Verify the stored values with SQL

```sql
-- Compare the row with the API response, field by field.
SELECT id,
       title,
       description,
       severity,
       status,
       category,
       environment,
       created_at AT TIME ZONE 'UTC' AS created_at_utc,
       updated_at AT TIME ZONE 'UTC' AS updated_at_utc
FROM issues
WHERE id = <id>;
```

Checks to perform on the output:

| Check | Expected |
| --- | --- |
| `title` | identical to the submitted title |
| `severity`, `status`, `category`, `environment` | identical to the submitted values |
| `created_at` | non-null, UTC, close to the request time |
| `updated_at` | equal to `created_at` on creation |
| Row count | exactly 1 row for the id |

### Step 5 - Update the defect and verify the database reflects the change

```http
PATCH /issues/{id}
{"status": "In Progress", "severity": "High"}
```

```sql
SELECT id, status, severity, created_at, updated_at, (updated_at > created_at) AS was_updated
FROM issues
WHERE id = <id>;
```

Expected: `status = 'In Progress'`, `severity = 'High'`, `was_updated = true`.

### Step 6 - Delete the defect and confirm it no longer exists

```http
DELETE /issues/{id}     -- expects HTTP 204 with an empty body
```

```sql
-- Must return 0 rows.
SELECT COUNT(*) FROM issues WHERE id = <id>;

-- Or, to see the absence explicitly:
SELECT id, title FROM issues WHERE id = <id>;
```

Then repeat step 3: the API must answer `HTTP 404`.

### Step 7 - Record the results and any discrepancies

Record actual values in the tables below. If a value differs from the expectation,
raise a defect using `defect-report-template.md`.

## 3. Recorded results

### 3.1 API-side validation - EXECUTED

Executed against the real server (`uvicorn app.main:app`) with an empty database.
The application database was a throwaway SQLite file because PostgreSQL was not installed
in this environment; the API behaviour is driver independent, the SQL below (section 3.2)
is the PostgreSQL-specific part.

| Step | Action | Observed result | Status |
| --- | --- | --- | --- |
| 1 | `POST /issues` with severity `High` | `201`, `id = 1`, `created_at = 2026-10-23T04:25:30.666261Z` (UTC) | Pass |
| 2 | Capture id | `issueId = 1` | Pass |
| 3 | `GET /issues/1` | `200`, `title = "Live smoke test defect"` | Pass |
| 5 | `PATCH /issues/1 {"status":"In Progress"}` | `200`, `status = "In Progress"`, `updated_at = 2026-10-23T04:25:30.711037Z` (newer than `created_at`) | Pass |
| 5b | `GET /issues?page=1&page_size=5&sort_by=id&order=desc` | `200`, `total = 1`, `pages = 1` | Pass |
| 5c | `GET /issues/stats` after the update | `{"total":1,"by_status":{"Open":0,"In Progress":1,"Closed":0},"by_severity":{"Low":0,"Medium":0,"High":1,"Critical":0}}` | Pass |
| 6 | `DELETE /issues/1` | `204` with an empty body | Pass |
| 6b | `GET /issues/1` after deletion | `404`, `error.type = "not_found"` | Pass |
| 6c | `GET /issues/stats` after deletion | `{"total":0,...}` all buckets `0` | Pass |
| - | `GET /health` | `200`, `status = "ok"`, `database = "connected"` | Pass |

Discrepancies found: **none**.

### 3.2 PostgreSQL / SQL-side validation - PENDING

Not executed: no PostgreSQL server was available in the build environment. Run the
procedure below on a machine with PostgreSQL installed and paste the real output here.
The automated equivalent of these checks runs in `tests/integration/test_postgres_integration.py`
when `TEST_DATABASE_URL` is configured.

| # | SQL check | Expected | Actual | Status |
| --- | --- | --- | --- | --- |
| 1 | `SELECT * FROM issues WHERE id = <id>;` | stored values equal the API response | _pending_ | Pending |
| 2 | `SELECT COUNT(*) FROM issues;` | equals the number of defects created | _pending_ | Pending |
| 3 | Invalid values query (queries 6 in `sql/validation_queries.sql`) | 0 rows | _pending_ | Pending |
| 4 | Missing/invalid data query (query 7) | 0 rows | _pending_ | Pending |
| 5 | `updated_at < created_at` query (query 8) | 0 rows | _pending_ | Pending |
| 6 | Status counts (query 9) | equals `/issues/stats -> by_status` | _pending_ | Pending |
| 7 | Severity counts (query 10) | equals `/issues/stats -> by_severity` | _pending_ | Pending |
| 8 | Duplicate detection (query 4) | shows only intentional test duplicates | _pending_ | Pending |
| 9 | Constraint inventory (query 16) | 5 CHECK constraints + 1 PK + 6 indexes | _pending_ | Pending |
| 10 | Index usage via `EXPLAIN ANALYZE` | index scan used for filtered query | _pending_ | Pending |

## 4. Illustrative example (clearly marked as an example)

> The output block below is a **formatting example only** - it was not produced by a real
> PostgreSQL run. Use it as a template for the section 3.2 table.

```text
defect_tracker=# SELECT id, title, severity, status, created_at AT TIME ZONE 'UTC' FROM issues WHERE id = 7;
 id |              title               | severity | status |     created_at
----+----------------------------------+----------+--------+---------------------
  7 | Payment screen freezes (example)| Critical | Open   | 2026-10-23 04:25:30
(1 row)

defect_tracker=# SELECT status, COUNT(*) FROM issues GROUP BY status ORDER BY status;
   status    | count
-------------+-------
 Closed      |     1
 In Progress |     1
 Open        |     3
(3 rows)

defect_tracker=# SELECT COUNT(*) FROM issues WHERE severity NOT IN ('Low','Medium','High','Critical');
 count
-------
     0
(1 row)
```

## 5. Data consistency rules being validated

1. Every defect returned by `GET /issues/{id}` exists in the database with identical field values.
2. Enum columns only contain documented values (enforced by CHECK constraints and re-verified by query).
3. `title` is always between 3 and 200 characters.
4. `created_at` and `updated_at` are never null and `updated_at >= created_at`.
5. `DELETE` removes the row physically; a follow-up SELECT returns 0 rows.
6. Statistics returned by `/issues/stats` match the SQL aggregate counts exactly.
7. Pagination does not duplicate or skip rows: the union of all pages equals the full filtered result set.

## 6. How to validate duplicate and invalid data

```sql
-- Likely duplicates (same title, severity and environment)
SELECT title, severity, environment, COUNT(*) AS occurrences
FROM issues
GROUP BY title, severity, environment
HAVING COUNT(*) > 1
ORDER BY occurrences DESC;

-- Invalid enum values (must return 0 rows)
SELECT id, severity AS invalid_severity FROM issues
WHERE severity NOT IN ('Low','Medium','High','Critical');

-- Invalid title lengths (must return 0 rows)
SELECT id, title, length(title) FROM issues
WHERE length(trim(title)) < 3 OR length(title) > 200;

-- Orphan / NULL required columns (must return 0 rows)
SELECT id FROM issues
WHERE title IS NULL OR severity IS NULL OR status IS NULL
   OR category IS NULL OR environment IS NULL
   OR created_at IS NULL OR updated_at IS NULL;
```

## 7. Cleanup after validation

```sql
-- Review first, then delete the synthetic records created during validation.
SELECT id, title, created_at FROM issues WHERE title LIKE 'Severity sweep%' OR title LIKE 'Live smoke%';

-- DELETE FROM issues WHERE title LIKE 'Severity sweep%' OR title LIKE 'Live smoke%';
```
