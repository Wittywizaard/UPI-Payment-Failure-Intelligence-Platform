-- UPI Payment Failure Intelligence Platform — Initial Schema
-- Applied automatically by the postgres container on first boot (docker-entrypoint-initdb.d)

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- =========================================================
-- USERS / RBAC
-- =========================================================
CREATE TYPE user_role AS ENUM ('admin', 'pm', 'ops', 'engineer', 'support', 'viewer');

CREATE TABLE users (
    user_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    display_name    TEXT NOT NULL,
    role            user_role NOT NULL DEFAULT 'viewer',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =========================================================
-- ERROR CODES (reference/taxonomy table)
-- =========================================================
CREATE TABLE error_codes (
    error_code          TEXT PRIMARY KEY,
    description         TEXT NOT NULL,
    category            TEXT NOT NULL CHECK (category IN
                            ('BANK', 'TECHNICAL', 'NETWORK', 'VALIDATION', 'USER', 'UNKNOWN')),
    severity            TEXT NOT NULL CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    owner_team          TEXT NOT NULL,
    recommended_action  TEXT,
    active_flag         BOOLEAN NOT NULL DEFAULT TRUE
);

-- =========================================================
-- TRANSACTIONS (core fact table)
-- =========================================================
CREATE TABLE transactions (
    transaction_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ts                       TIMESTAMPTZ NOT NULL,
    payer_bank               TEXT NOT NULL,
    payee_bank               TEXT NOT NULL,
    psp                      TEXT NOT NULL,
    amount                   NUMERIC(14,2) NOT NULL CHECK (amount >= 0),
    currency                 TEXT NOT NULL DEFAULT 'INR',
    status                   TEXT NOT NULL CHECK (status IN ('SUCCESS', 'FAILED', 'PENDING')),
    error_code               TEXT REFERENCES error_codes(error_code),
    error_category           TEXT,
    device_type              TEXT NOT NULL,
    os                       TEXT NOT NULL,
    app_version              TEXT NOT NULL,
    network_type             TEXT NOT NULL,
    transaction_type         TEXT NOT NULL,
    geography                TEXT NOT NULL,
    processing_time_ms       INTEGER NOT NULL CHECK (processing_time_ms >= 0),
    retry_count              INTEGER NOT NULL DEFAULT 0,
    is_eligible              BOOLEAN NOT NULL DEFAULT TRUE,
    is_duplicate             BOOLEAN NOT NULL DEFAULT FALSE,
    original_transaction_id  UUID REFERENCES transactions(transaction_id),
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_txn_ts ON transactions (ts);
CREATE INDEX idx_txn_status ON transactions (status);
CREATE INDEX idx_txn_payer_bank ON transactions (payer_bank);
CREATE INDEX idx_txn_psp ON transactions (psp);
CREATE INDEX idx_txn_error_code ON transactions (error_code);
CREATE INDEX idx_txn_device_os_app ON transactions (device_type, os, app_version);
CREATE INDEX idx_txn_eligible ON transactions (is_eligible);
CREATE INDEX idx_txn_original ON transactions (original_transaction_id);
-- Composite index tuned for the fingerprint engine's dimensional group-bys
CREATE INDEX idx_txn_fingerprint_dims ON transactions (ts, payer_bank, device_type, os, app_version);

-- =========================================================
-- INCIDENTS
-- =========================================================
CREATE TYPE incident_severity AS ENUM ('P0', 'P1', 'P2');
CREATE TYPE incident_status AS ENUM ('open', 'investigating', 'mitigated', 'resolved', 'closed');

CREATE TABLE incidents (
    incident_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    detected_at             TIMESTAMPTZ NOT NULL,
    severity                incident_severity NOT NULL,
    title                   TEXT NOT NULL,
    status                  incident_status NOT NULL DEFAULT 'open',
    owner                   TEXT,
    root_cause_summary      TEXT,
    affected_bank           TEXT,
    affected_error          TEXT,
    affected_fingerprint    JSONB,
    estimated_value_at_risk NUMERIC(16,2),
    affected_transactions   INTEGER,
    observed_psr            NUMERIC(5,2),
    baseline_psr            NUMERIC(5,2),
    resolved_at             TIMESTAMPTZ,
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_incidents_status ON incidents (status);
CREATE INDEX idx_incidents_severity ON incidents (severity);

-- =========================================================
-- INTERVENTIONS
-- =========================================================
CREATE TYPE intervention_status AS ENUM ('proposed', 'active', 'completed', 'abandoned');

CREATE TABLE interventions (
    intervention_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id         UUID NOT NULL REFERENCES incidents(incident_id) ON DELETE CASCADE,
    type                TEXT NOT NULL,
    hypothesis          TEXT NOT NULL,
    description         TEXT,
    owner               TEXT,
    start_time          TIMESTAMPTZ,
    end_time            TIMESTAMPTZ,
    expected_impact     TEXT,
    actual_impact       JSONB,
    status              intervention_status NOT NULL DEFAULT 'proposed',
    outcome             TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_interventions_incident ON interventions (incident_id);

-- =========================================================
-- EXPERIMENTS
-- =========================================================
CREATE TABLE experiments (
    experiment_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                TEXT NOT NULL,
    hypothesis          TEXT NOT NULL,
    control_definition  TEXT NOT NULL,
    variant_definition  TEXT NOT NULL,
    primary_metric      TEXT NOT NULL,
    secondary_metrics   JSONB,
    guardrails          JSONB,
    start_time          TIMESTAMPTZ,
    end_time            TIMESTAMPTZ,
    sample_size         INTEGER,
    result_summary      JSONB,
    is_simulated        BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =========================================================
-- SAVED VIEWS
-- =========================================================
CREATE TABLE saved_views (
    view_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id        UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    name           TEXT NOT NULL,
    filter_json    JSONB NOT NULL,
    sharing_scope  TEXT NOT NULL DEFAULT 'private' CHECK (sharing_scope IN ('private', 'team')),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_saved_views_user ON saved_views (user_id);

-- =========================================================
-- AUDIT LOGS
-- =========================================================
CREATE TABLE audit_logs (
    audit_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id        UUID REFERENCES users(user_id),
    action         TEXT NOT NULL,
    entity_type    TEXT NOT NULL,
    entity_id      TEXT,
    metadata_json  JSONB,
    timestamp      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_audit_logs_entity ON audit_logs (entity_type, entity_id);
CREATE INDEX idx_audit_logs_user ON audit_logs (user_id);

-- =========================================================
-- DATA FRESHNESS TRACKING (for the "Data fresh as of..." UI indicator)
-- =========================================================
CREATE TABLE pipeline_runs (
    run_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at    TIMESTAMPTZ,
    status          TEXT NOT NULL CHECK (status IN ('running', 'success', 'failed')),
    rows_processed  INTEGER,
    notes           TEXT
);
