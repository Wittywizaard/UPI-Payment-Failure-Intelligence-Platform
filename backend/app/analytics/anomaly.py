"""
MVP anomaly detection (PRD Section 10). Deliberately a rules/statistics-based
approach comparing observed PSR/failure rate against a rolling historical
baseline for the same time-of-day window -- not a fake "AI-powered" model.
Later extensions (change-point detection, forecasting, Isolation Forest) are
documented as roadmap items, not implemented here.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.analytics.fingerprint import _baseline_window  # reuse the same rolling-window definition

# Business thresholds for triggering an anomaly (PRD: "statistical/business thresholds")
MIN_ABSOLUTE_PSR_DROP_PP = 2.0     # observed PSR at least 2pp below baseline
MIN_RELATIVE_PSR_DROP = 0.02       # ...and at least a 2% relative drop
MIN_AFFECTED_VOLUME = 200          # ignore drops with too little volume to matter operationally

SEVERITY_THRESHOLDS = [
    (10.0, "P0"),
    (5.0, "P1"),
    (2.0, "P2"),
]


def _window_stats(engine: Engine, start: datetime, end: datetime) -> dict:
    sql = text("""
        SELECT count(*) FILTER (WHERE is_eligible) AS eligible,
               count(*) FILTER (WHERE is_eligible AND status = 'SUCCESS') AS eligible_success,
               count(*) FILTER (WHERE is_eligible AND status = 'FAILED') AS eligible_failed,
               coalesce(sum(amount) FILTER (WHERE is_eligible AND status = 'FAILED'), 0) AS value_at_risk
        FROM transactions
        WHERE ts >= :start AND ts < :end
    """)
    with engine.connect() as conn:
        row = conn.execute(sql, {"start": start, "end": end}).mappings().first()
    eligible = row["eligible"] or 0
    success = row["eligible_success"] or 0
    return {
        "eligible": eligible,
        "eligible_failed": row["eligible_failed"] or 0,
        "psr": round(100.0 * success / eligible, 2) if eligible else None,
        "value_at_risk": float(row["value_at_risk"]),
    }


def detect_anomaly(engine: Engine, observed_start: datetime, observed_end: datetime,
                    baseline_days: int = 7) -> dict:
    observed = _window_stats(engine, observed_start, observed_end)

    baseline_windows = [_window_stats(engine, s, e) for s, e in
                        _baseline_window(observed_start, observed_end, baseline_days)]
    valid_baselines = [w for w in baseline_windows if w["psr"] is not None]
    baseline_psr = round(sum(w["psr"] for w in valid_baselines) / len(valid_baselines), 2) if valid_baselines else None

    result = {
        "observed_start": observed_start.isoformat(),
        "observed_end": observed_end.isoformat(),
        "observed_psr": observed["psr"],
        "baseline_psr": baseline_psr,
        "affected_transactions": observed["eligible_failed"],
        "value_at_risk": observed["value_at_risk"],
        "is_anomaly": False,
        "severity": None,
    }

    if observed["psr"] is None or baseline_psr is None or observed["eligible"] < MIN_AFFECTED_VOLUME:
        result["reason"] = "insufficient_data"
        return result

    absolute_drop = baseline_psr - observed["psr"]
    relative_drop = absolute_drop / baseline_psr if baseline_psr else 0

    if absolute_drop < MIN_ABSOLUTE_PSR_DROP_PP or relative_drop < MIN_RELATIVE_PSR_DROP:
        result["reason"] = "within_normal_range"
        return result

    result["is_anomaly"] = True
    result["psr_drop_pp"] = round(absolute_drop, 2)
    result["severity"] = _assign_severity(absolute_drop)
    return result


def _assign_severity(absolute_drop_pp: float) -> str:
    for threshold, severity in SEVERITY_THRESHOLDS:
        if absolute_drop_pp >= threshold:
            return severity
    return "P2"
