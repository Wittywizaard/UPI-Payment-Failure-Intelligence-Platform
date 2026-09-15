"""
Observability aggregation (PRD Section 22). Queries the api_request_logs
table populated by the request-timing middleware in app/main.py, plus the
in-process DB query-timing counters and the pipeline_runs table already used
by /api/data-freshness.

Endpoint groupings (RCA, AI, etc.) are derived from the request path prefix
so "RCA generation latency" and "AI latency/errors" -- called out separately
in the PRD -- are visible as their own rows without a second logging path.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

ENDPOINT_GROUPS: list[tuple[str, str]] = [
    ("/api/rca", "rca_generation"),
    ("/api/ai", "ai_assistant"),
    ("/api/dashboard", "dashboard"),
    ("/api/failures", "failure_explorer"),
    ("/api/incidents", "incidents"),
    ("/api/interventions", "interventions"),
    ("/api/experiments", "experiments"),
    ("/api/auth", "auth"),
]


def _group_for_path(path: str) -> str:
    for prefix, label in ENDPOINT_GROUPS:
        if path.startswith(prefix):
            return label
    return "other"


def get_api_metrics(engine: Engine, window_minutes: int = 60) -> dict:
    since = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)

    with engine.connect() as conn:
        df = pd.read_sql(
            text("SELECT path, status_code, duration_ms FROM api_request_logs WHERE created_at >= :since"),
            conn,
            params={"since": since},
        )

    if df.empty:
        return {
            "window_minutes": window_minutes,
            "total_requests": 0,
            "error_rate_pct": None,
            "avg_latency_ms": None,
            "p95_latency_ms": None,
            "by_feature": [],
        }

    df["group"] = df["path"].apply(_group_for_path)
    df["is_error"] = df["status_code"] >= 500

    overall = {
        "window_minutes": window_minutes,
        "total_requests": int(len(df)),
        "error_rate_pct": round(100 * df["is_error"].mean(), 2),
        "avg_latency_ms": round(df["duration_ms"].mean(), 1),
        "p95_latency_ms": round(df["duration_ms"].quantile(0.95), 1),
    }

    by_feature = []
    for group, sub in df.groupby("group"):
        by_feature.append({
            "feature": group,
            "requests": int(len(sub)),
            "error_rate_pct": round(100 * sub["is_error"].mean(), 2),
            "avg_latency_ms": round(sub["duration_ms"].mean(), 1),
            "p95_latency_ms": round(sub["duration_ms"].quantile(0.95), 1),
        })
    by_feature.sort(key=lambda r: r["requests"], reverse=True)

    overall["by_feature"] = by_feature
    return overall


def get_pipeline_health(engine: Engine, limit: int = 5) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT run_id, started_at, completed_at, status, rows_processed, notes
                FROM pipeline_runs
                ORDER BY started_at DESC
                LIMIT :limit
            """),
            {"limit": limit},
        ).mappings().all()

    return [
        {
            "run_id": str(r["run_id"]),
            "started_at": r["started_at"].isoformat() if r["started_at"] else None,
            "completed_at": r["completed_at"].isoformat() if r["completed_at"] else None,
            "status": r["status"],
            "rows_processed": r["rows_processed"],
            "notes": r["notes"],
        }
        for r in rows
    ]
