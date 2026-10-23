-- ===========================================================================
-- Database validation queries
--
-- Purpose: verify through plain SQL (not through the API) that the data stored
-- by the REST API is correct, complete and consistent.
--
-- Usage:
--   psql -U postgres -d defect_tracker -f sql/validation_queries.sql
-- or run the individual statements in pgAdmin / DBeaver.
-- All statements are read-only, so they are safe on any database.
-- ===========================================================================


-- ---------------------------------------------------------------------------
-- 1. Stored records - full inspection of the most recent defects
-- ---------------------------------------------------------------------------
SELECT id, title, severity, status, category, environment,
       created_at AT TIME ZONE 'UTC' AS created_at_utc,
       updated_at AT TIME ZONE 'UTC' AS updated_at_utc
FROM issues
ORDER BY id DESC
LIMIT 20;


-- ---------------------------------------------------------------------------
-- 2. Verify one specific record that was just created through the API
--    Replace the id with the value returned by POST /issues.
-- ---------------------------------------------------------------------------
SELECT id, title, description, severity, status, category, environment, created_at, updated_at
FROM issues
WHERE id = 1;


-- ---------------------------------------------------------------------------
-- 3. Row count and latest identifiers (quick smoke check)
-- ---------------------------------------------------------------------------
SELECT COUNT(*) AS total_rows, MIN(id) AS first_id, MAX(id) AS last_id FROM issues;


-- ---------------------------------------------------------------------------
-- 4. Duplicate detection
--    A defect is considered a likely duplicate when the title, severity and
--    environment are identical. Nothing prevents this in the schema on purpose
--    (testers legitimately re-report similar defects), so it is validated here.
-- ---------------------------------------------------------------------------
SELECT title, severity, environment, COUNT(*) AS occurrences, ARRAY_AGG(id ORDER BY id) AS issue_ids
FROM issues
GROUP BY title, severity, environment
HAVING COUNT(*) > 1
ORDER BY occurrences DESC, title;


-- 5. Fully identical duplicates (stronger check)
SELECT title, description, severity, status, category, environment, COUNT(*) AS occurrences
FROM issues
GROUP BY title, description, severity, status, category, environment
HAVING COUNT(*) > 1;


-- ---------------------------------------------------------------------------
-- 6. Invalid values that must never exist (should return 0 rows)
--    These queries double-check the CHECK constraints from the outside.
-- ---------------------------------------------------------------------------
SELECT 'invalid severity' AS problem, id, severity AS value FROM issues
WHERE severity NOT IN ('Low', 'Medium', 'High', 'Critical')
UNION ALL
SELECT 'invalid status', id, status FROM issues
WHERE status NOT IN ('Open', 'In Progress', 'Closed')
UNION ALL
SELECT 'invalid category', id, category FROM issues
WHERE category NOT IN ('Functional', 'UI', 'API', 'Performance', 'Security')
UNION ALL
SELECT 'invalid environment', id, environment FROM issues
WHERE environment NOT IN ('Web', 'Android', 'iOS', 'Linux', 'Backend API');


-- 7. Missing or malformed data (should return 0 rows)
SELECT id, title, severity, status, category, environment, created_at, updated_at
FROM issues
WHERE title IS NULL
   OR length(trim(title)) < 3
   OR length(title) > 200
   OR severity IS NULL
   OR status IS NULL
   OR category IS NULL
   OR environment IS NULL
   OR created_at IS NULL
   OR updated_at IS NULL;


-- 8. Consistency of the timestamps (updated_at must never precede created_at)
SELECT id, created_at, updated_at
FROM issues
WHERE updated_at < created_at;


-- ---------------------------------------------------------------------------
-- 9. Status counts (must match GET /issues/stats -> by_status)
-- ---------------------------------------------------------------------------
SELECT status, COUNT(*) AS total
FROM issues
GROUP BY status
ORDER BY status;


-- 10. Severity counts (must match GET /issues/stats -> by_severity)
SELECT severity, COUNT(*) AS total
FROM issues
GROUP BY severity
ORDER BY severity;


-- 11. Status / severity matrix and overall total
SELECT status,
       COUNT(*) FILTER (WHERE severity = 'Low')      AS low,
       COUNT(*) FILTER (WHERE severity = 'Medium')   AS medium,
       COUNT(*) FILTER (WHERE severity = 'High')     AS high,
       COUNT(*) FILTER (WHERE severity = 'Critical') AS critical,
       COUNT(*)                                      AS total
FROM issues
GROUP BY status
ORDER BY status;


-- 12. Category and environment distribution
SELECT category, COUNT(*) AS total FROM issues GROUP BY category ORDER BY total DESC;
SELECT environment, COUNT(*) AS total FROM issues GROUP BY environment ORDER BY total DESC;


-- ---------------------------------------------------------------------------
-- 13. Verifying the result of a specific update
--     After PATCH /issues/{id} {"status":"In Progress"} this must show the new
--     status and an updated_at value that is newer than created_at.
-- ---------------------------------------------------------------------------
SELECT id, status, created_at, updated_at, (updated_at > created_at) AS was_updated
FROM issues
WHERE id = 1;


-- 14. Verifying a deletion (must return no rows)
SELECT id, title, status FROM issues WHERE id = 1;


-- ---------------------------------------------------------------------------
-- 15. Index usage proof for the filtering patterns used by GET /issues
-- ---------------------------------------------------------------------------
EXPLAIN ANALYZE
SELECT * FROM issues WHERE severity = 'Critical' AND status = 'Open';

EXPLAIN ANALYZE
SELECT * FROM issues ORDER BY created_at DESC LIMIT 20;


-- ---------------------------------------------------------------------------
-- 16. Constraint inventory (documents what the database enforces)
-- ---------------------------------------------------------------------------
SELECT conname AS constraint_name, pg_get_constraintdef(oid) AS definition
FROM pg_constraint
WHERE conrelid = 'issues'::regclass
ORDER BY conname;

SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'issues' ORDER BY indexname;


-- ---------------------------------------------------------------------------
-- 17. Data hygiene: rows created in bulk during test runs (cleanup helper)
--     Review the SELECT first, then run the DELETE if appropriate.
-- ---------------------------------------------------------------------------
SELECT id, title, created_at FROM issues WHERE title LIKE 'Severity sweep%' OR title LIKE 'Seeded defect%';

-- DELETE FROM issues WHERE title LIKE 'Severity sweep%' OR title LIKE 'Seeded defect%';
