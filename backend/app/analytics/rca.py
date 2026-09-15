"""
RCA engine (PRD Section 11). Orchestrates:
  1. Anomaly detection (observed vs. expected PSR)
  2. Failure Fingerprint scan (probable contributors)
  3. Evidence assembly (volume/rate/delta/contribution per contributor)
  4. Severity assignment
  5. Recommended next actions

Produces the RCA output schema from PRD Section 15. Never claims a fingerprint
is a "confirmed root cause" -- only a "probable contributor" -- since this is
correlation-based attribution, not a causal experiment.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.engine import Engine

from app.analytics.anomaly import detect_anomaly
from app.analytics.fingerprint import run_fingerprint_scan

RECOMMENDED_ACTION_TEMPLATES = {
    "payer_bank": "Investigate {value} dependency health and recent incident reports",
    "psp": "Check {value} routing health and recent config/deploy changes",
    "device_type": "Review {value} client behavior for the affected window",
    "os": "Review OS build {value} compatibility with the current app release",
    "app_version": "Review app release {value} for regressions; consider a rollback if recent",
    "network_type": "Investigate {value} network-class reliability and timeout thresholds",
    "transaction_type": "Review {value} transaction flow for validation or downstream issues",
    "error_code": "Investigate {value} error spikes with the owning team",
}


def generate_recommended_actions(fingerprint: dict) -> list[str]:
    actions = []
    for dim, value in fingerprint["dimensions"].items():
        template = RECOMMENDED_ACTION_TEMPLATES.get(dim)
        if template:
            actions.append(template.format(value=value))
    actions.append("Create an engineering incident if the pattern persists beyond this window")
    return actions


def generate_ai_summary(anomaly: dict, top_fingerprint: dict | None) -> str:
    """
    Deterministic, template-based summary used when the LLM-backed AI Assistant
    (Phase 8) is unavailable or for fast inline display. The full AI Assistant
    wraps this same validated data with an LLM explanation layer -- it does not
    replace this computation.
    """
    if not anomaly["is_anomaly"]:
        return "No significant PSR anomaly detected for the selected window."

    if not top_fingerprint:
        return (
            f"PSR declined from {anomaly['baseline_psr']}% to {anomaly['observed_psr']}% "
            f"({anomaly['psr_drop_pp']}pp drop), but no single dimension combination met the "
            "significance thresholds to be reported as a probable contributor. Manual "
            "investigation across less common dimensions is recommended."
        )

    label = top_fingerprint["label"]
    contribution = top_fingerprint["contribution_pct"]
    observed_rate = top_fingerprint["observed_failure_rate_pct"]
    baseline_rate = top_fingerprint["baseline_failure_rate_pct"]

    return (
        f"PSR declined from {anomaly['baseline_psr']}% to {anomaly['observed_psr']}% "
        f"({anomaly['psr_drop_pp']}pp drop) during the selected window. The segment "
        f"{label} shows a failure rate of {observed_rate}% versus its own baseline of "
        f"{baseline_rate}%, and is estimated to account for approximately {contribution}% "
        f"of the incremental failures in this window. This is a probable contributor based "
        f"on observed correlation, not confirmed causal evidence."
    )


def run_rca(engine: Engine, observed_start: datetime, observed_end: datetime,
            baseline_days: int = 7) -> dict:
    anomaly = detect_anomaly(engine, observed_start, observed_end, baseline_days)

    fingerprints: list[dict] = []
    if anomaly["is_anomaly"]:
        fingerprints = run_fingerprint_scan(engine, observed_start, observed_end, baseline_days)

    top_fingerprint = fingerprints[0] if fingerprints else None

    return {
        "anomaly": anomaly["is_anomaly"],
        "severity": anomaly.get("severity"),
        "observed_psr": anomaly["observed_psr"],
        "baseline_psr": anomaly["baseline_psr"],
        "psr_drop_pp": anomaly.get("psr_drop_pp"),
        "affected_transactions": anomaly["affected_transactions"],
        "value_at_risk": anomaly["value_at_risk"],
        "window": {"start": observed_start.isoformat(), "end": observed_end.isoformat()},
        "fingerprint": top_fingerprint,
        "contributors": fingerprints,
        "evidence": [
            {
                "dimension_combo": fp["label"],
                "volume": fp["volume"],
                "failure_rate_pct": fp["observed_failure_rate_pct"],
                "baseline_failure_rate_pct": fp["baseline_failure_rate_pct"],
                "deviation_pp": fp["deviation_pp"],
                "contribution_pct": fp["contribution_pct"],
                "value_at_risk": fp["value_at_risk"],
            }
            for fp in fingerprints[:8]
        ],
        "ai_summary": generate_ai_summary(anomaly, top_fingerprint),
        "recommended_actions": generate_recommended_actions(top_fingerprint) if top_fingerprint else [
            "Continue monitoring; no single probable contributor identified yet"
        ],
        "disclaimer": "Probable contributor based on observed correlation; not confirmed causal evidence.",
    }
