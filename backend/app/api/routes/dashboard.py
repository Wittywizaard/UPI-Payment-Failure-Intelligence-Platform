from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query

from app.analytics.anomaly import detect_anomaly
from app.analytics.metrics import compute_core_metrics
from app.core.deps import get_current_user
from app.db.session import engine

router = APIRouter(tags=["dashboard"])

DATASET_END = datetime(2026, 8, 29, 23, 59, 59, tzinfo=timezone.utc)  # matches generator's fixed anchor


@router.get("/dashboard")
def get_dashboard(hours: int = Query(24, ge=1, le=168, description="Lookback window size in hours"),
                   current_user: dict = Depends(get_current_user)):
    end = DATASET_END
    start = end - timedelta(hours=hours)
    previous_start = start - timedelta(hours=hours)

    current = compute_core_metrics(engine, {"start_date": start, "end_date": end})
    previous = compute_core_metrics(engine, {"start_date": previous_start, "end_date": start})

    anomaly = detect_anomaly(engine, start, end, baseline_days=7)

    psr_change = None
    if current["psr"] is not None and previous["psr"] is not None:
        psr_change = round(current["psr"] - previous["psr"], 2)

    return {
        "window": {"start": start.isoformat(), "end": end.isoformat(), "hours": hours},
        "kpis": {
            "psr": current["psr"],
            "psr_change_pp": psr_change,
            "total_transactions": current["total_transactions"],
            "failed_transactions": current["eligible_failed"],
            "value_at_risk": current["value_at_risk"],
            "retry_recovery_rate": current["recovery_rate"],
        },
        "anomaly_detected": anomaly["is_anomaly"],
        "anomaly_severity": anomaly.get("severity"),
        "data_freshness_note": "Batch pipeline. See /api/data-freshness for the last successful run.",
    }
