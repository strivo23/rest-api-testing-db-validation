-- ===========================================================================
-- REST API Testing & Database Validation Platform
-- PostgreSQL schema for the "issues" (defect) table.
--
-- Two equivalent ways to initialise the database:
--   1. python -m app.db_init                    (SQLAlchemy metadata, recommended)
--   2. psql -U postgres -d defect_tracker -f sql/schema.sql
--
-- This script is the documented raw-SQL alternative. It creates exactly the
-- same structure as the SQLAlchemy models in app/models.py (same constraint and
-- index names) plus a trigger that keeps updated_at accurate for manual SQL
-- updates.
-- ===========================================================================

-- Run once, as a PostgreSQL superuser or database owner:
--   CREATE DATABASE defect_tracker WITH ENCODING 'UTF8';

BEGIN;

CREATE TABLE IF NOT EXISTS issues (
    id          SERIAL       PRIMARY KEY,
    title       VARCHAR(200) NOT NULL,
    description TEXT,
    severity    VARCHAR(20)  NOT NULL DEFAULT 'Medium',
    status      VARCHAR(20)  NOT NULL DEFAULT 'Open',
    category    VARCHAR(20)  NOT NULL DEFAULT 'Functional',
    environment VARCHAR(20)  NOT NULL DEFAULT 'Web',
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),

    -- Business rules enforced by the database itself.
    CONSTRAINT ck_issues_title_length CHECK (length(title) >= 3 AND length(title) <= 200),
    CONSTRAINT ck_issues_severity     CHECK (severity IN ('Low', 'Medium', 'High', 'Critical')),
    CONSTRAINT ck_issues_status       CHECK (status IN ('Open', 'In Progress', 'Closed')),
    CONSTRAINT ck_issues_category     CHECK (category IN ('Functional', 'UI', 'API', 'Performance', 'Security')),
    CONSTRAINT ck_issues_environment  CHECK (environment IN ('Web', 'Android', 'iOS', 'Linux', 'Backend API'))
);

-- Indexes for the most frequently filtered / sorted columns.
CREATE INDEX IF NOT EXISTS ix_issues_severity            ON issues (severity);
CREATE INDEX IF NOT EXISTS ix_issues_status              ON issues (status);
CREATE INDEX IF NOT EXISTS ix_issues_category            ON issues (category);
CREATE INDEX IF NOT EXISTS ix_issues_environment         ON issues (environment);
CREATE INDEX IF NOT EXISTS ix_issues_created_at          ON issues (created_at);
CREATE INDEX IF NOT EXISTS ix_issues_status_severity     ON issues (status, severity);

-- Keep updated_at correct even when rows are changed outside the ORM.
CREATE OR REPLACE FUNCTION set_issues_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_issues_set_updated_at ON issues;
CREATE TRIGGER trg_issues_set_updated_at
    BEFORE UPDATE ON issues
    FOR EACH ROW
    EXECUTE FUNCTION set_issues_updated_at();

COMMIT;

-- Verification: the table, its constraints and its indexes.
-- SELECT column_name, data_type, is_nullable, column_default
--   FROM information_schema.columns WHERE table_name = 'issues' ORDER BY ordinal_position;
-- SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint
--   WHERE conrelid = 'issues'::regclass ORDER BY conname;
-- SELECT indexname FROM pg_indexes WHERE tablename = 'issues' ORDER BY indexname;
