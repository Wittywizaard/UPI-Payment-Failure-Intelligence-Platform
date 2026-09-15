from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from app.analytics.rca import run_rca
from app.core.deps import get_current_user
from app.db.session import engine

router = APIRouter(tags=["rca"])


@router.get("/rca/ad-hoc")
def get_ad_hoc_rca(
    start: datetime = Query(..., description="Observed window start (ISO-8601)"),
    end: datetime = Query(..., description="Observed window end (ISO-8601)"),
    baseline_days: int = Query(7, ge=1, le=30),
    current_user: dict = Depends(get_current_user),
):
    """
    Runs the RCA engine for an arbitrary window without an existing Incident
    record -- used by the Failure Fingerprint / Explorer 'Investigate RCA'
    action before a formal incident exists.
    """
    if end <= start:
        raise HTTPException(status_code=400, detail={
            "error": {"code": "INVALID_FILTER", "message": "end must be after start"}
        })
    return run_rca(engine, start, end, baseline_days=baseline_days)


# GET /api/rca/{incident_id} (per the API contract) is implemented in Phase 7
# once the incidents table has a write path -- it will re-run this same
# engine using the incident's stored window and persist/compare against the
# original RCA snapshot rather than recomputing from scratch each time.
