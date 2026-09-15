-- Observability: API request-level metrics (PRD Section 22).
-- Applied automatically on a fresh volume (docker-entrypoint-initdb.d runs
-- *.sql files in filename order, so this runs after 001_init.sql). For an
-- existing database, apply manually:
--   psql -U upi_fip -d upi_fip -f sql/migrations/002_observability.sql
-- (see docs/decisions.md D44 -- this project uses plain numbered SQL files
-- for fresh installs rather than a full migration framework like Alembic).

CREATE TABLE IF NOT EXISTS api_request_logs (
    id           BIGSERIAL PRIMARY KEY,
    request_id   UUID,
    method       TEXT NOT NULL,
    path         TEXT NOT NULL,
    status_code  INTEGER NOT NULL,
    duration_ms  NUMERIC(10,2) NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_api_request_logs_created_at ON api_request_logs (created_at);
CREATE INDEX IF NOT EXISTS idx_api_request_logs_path ON api_request_logs (path);
