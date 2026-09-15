from fastapi import APIRouter, Depends, Query

from app.analytics.observability import get_api_metrics, get_pipeline_health
from app.core.deps import require_role
from app.db.session import engine, get_db_query_stats

router = APIRouter(tags=["observability"])
can_view_observability = require_role("admin", "engineer", "ops")


@router.get("/observability")
def get_observability(
    window_minutes: int = Query(60, ge=1, le=1440),
    current_user: dict = Depends(can_view_observability),
):
    """
    PRD Section 22: API latency/error rate, DB query latency, RCA generation
    latency, AI latency/errors (all derived from the same request log, see
    app/analytics/observability.py), and pipeline/data-freshness health.
    Restricted to admin/engineer/ops -- this is operational internals, not
    something a PM or Support persona needs day to day (see docs/decisions.md D44).
    """
    api_metrics = get_api_metrics(engine, window_minutes=window_minutes)
    db_stats = get_db_query_stats()
    pipeline_runs = get_pipeline_health(engine)

    return {
        "api": api_metrics,
        "database": db_stats,
        "pipeline_runs": pipeline_runs,
    }
