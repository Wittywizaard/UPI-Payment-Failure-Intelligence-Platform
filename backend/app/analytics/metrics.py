"""
Metrics engine. Implements the Metrics Dictionary from the PRD (Section 12)
with explicit, single-source-of-truth denominator rules.

All queries run as parameterized SQL (via app.analytics.filters) against the
live transactions table, then results are assembled into a plain dict by
pandas for consistent typing/rounding -- keeping heavy aggregation in
PostgreSQL (fast at 750K+ rows) while keeping the "shape the result" layer in
Python/Pandas per the TRD.
"""

from __future__ import annotations

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.analytics.filters import build_where_clause

CORE_METRICS_SQL_TEMPLATE = """
WITH scoped AS (
    SELECT transaction_id, amount, status, is_eligible, is_duplicate, original_transaction_id
    FROM transactions
    WHERE {where_clause}
),
elig_failed AS (
    SELECT transaction_id, amount
    FROM scoped
    WHERE is_eligible AND status = 'FAILED'
)
SELECT
    (SELECT count(*) FROM scoped) AS total_transactions,
    (SELECT count(*) FROM scoped WHERE is_eligible) AS total_eligible,
    (SELECT count(*) FROM scoped WHERE is_eligible AND status = 'SUCCESS') AS eligible_success,
    (SELECT count(*) FROM elig_failed) AS eligible_failed,
    (SELECT coalesce(sum(amount), 0) FROM elig_failed) AS value_at_risk,
    (SELECT count(*) FROM scoped WHERE is_duplicate) AS duplicate_count,
    (
        SELECT count(*) FROM elig_failed ef
        WHERE EXISTS (
            SELECT 1 FROM transactions r WHERE r.original_transaction_id = ef.transaction_id
        )
    ) AS retried_failed,
    (
        SELECT count(*) FROM elig_failed ef
        WHERE EXISTS (
            SELECT 1 FROM transactions r
            WHERE r.original_transaction_id = ef.transaction_id AND r.status = 'SUCCESS'
        )
    ) AS recovered_failed
"""


def compute_core_metrics(engine: Engine, filters: dict | None = None) -> dict:
    filters = filters or {}
    where_clause, params, expanding = build_where_clause(filters)
    sql = text(CORE_METRICS_SQL_TEMPLATE.format(where_clause=where_clause))
    if expanding:
        sql = sql.bindparams(*expanding)

    with engine.connect() as conn:
        row = pd.read_sql(sql, conn, params=params).iloc[0]

    total_eligible = int(row["total_eligible"])
    eligible_success = int(row["eligible_success"])
    eligible_failed = int(row["eligible_failed"])
    retried_failed = int(row["retried_failed"])
    recovered_failed = int(row["recovered_failed"])
    total_transactions = int(row["total_transactions"])
    duplicate_count = int(row["duplicate_count"])
    value_at_risk = float(row["value_at_risk"])

    def pct(numerator: int, denominator: int) -> float | None:
        if denominator == 0:
            return None
        return round(100.0 * numerator / denominator, 2)

    return {
        "total_transactions": total_transactions,
        "total_eligible": total_eligible,
        "eligible_success": eligible_success,
        "eligible_failed": eligible_failed,
        "psr": pct(eligible_success, total_eligible),
        "failure_rate": pct(eligible_failed, total_eligible),
        "recovery_rate": pct(recovered_failed, eligible_failed),
        "retry_rate": pct(retried_failed, eligible_failed),
        "duplicate_rate": pct(duplicate_count, total_transactions),
        "value_at_risk": round(value_at_risk, 2),
        "avg_processing_time_ms": None,  # populated by callers that need it (see get_avg_processing_time)
    }


def get_avg_processing_time_ms(engine: Engine, filters: dict | None = None) -> float | None:
    filters = filters or {}
    where_clause, params, expanding = build_where_clause(filters)
    sql = text(f"SELECT avg(processing_time_ms) AS avg_ms FROM transactions WHERE {where_clause}")
    if expanding:
        sql = sql.bindparams(*expanding)
    with engine.connect() as conn:
        row = pd.read_sql(sql, conn, params=params).iloc[0]
    return round(float(row["avg_ms"]), 1) if row["avg_ms"] is not None else None
