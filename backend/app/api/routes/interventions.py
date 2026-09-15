import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.analytics.metrics import compute_core_metrics
from app.core.audit import log_action
from app.core.deps import get_current_user, require_role
from app.db.session import engine, get_db
from app.schemas.interventions import InterventionCreate, InterventionUpdate, MeasureImpactRequest

router = APIRouter(tags=["interventions"])
can_write_interventions = require_role("pm", "ops", "engineer")


def _row_to_dict(row) -> dict:
    d = dict(row)
    for key in ("incident_id", "intervention_id"):
        if key in d and d[key] is not None:
            d[key] = str(d[key])
    return d


@router.get("/interventions")
def list_interventions(incident_id: str | None = None, status: str | None = None,
                        db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """
    Extension beyond the strict API contract (only GET /api/interventions/{id} is
    specified) -- the Intervention Center screen needs a list to browse. See
    docs/decisions.md D19, which already covers the same rationale for experiments.
    """
    clauses = ["1=1"]
    params = {}
    if incident_id:
        clauses.append("incident_id = :incident_id")
        params["incident_id"] = incident_id
    if status:
        clauses.append("status = :status")
        params["status"] = status
    where = " AND ".join(clauses)

    rows = db.execute(
        text(f"SELECT * FROM interventions WHERE {where} ORDER BY created_at DESC"), params
    ).mappings().all()
    return {"interventions": [_row_to_dict(r) for r in rows]}


@router.post("/interventions", status_code=201)
def create_intervention(payload: InterventionCreate, db: Session = Depends(get_db),
                         current_user: dict = Depends(can_write_interventions)):
    incident = db.execute(
        text("SELECT incident_id FROM incidents WHERE incident_id = :id"),
        {"id": payload.incident_id},
    ).first()
    if not incident:
        raise HTTPException(status_code=404, detail={
            "error": {"code": "NOT_FOUND", "message": "Parent incident not found"}
        })

    intervention_id = uuid.uuid4()
    db.execute(
        text("""
            INSERT INTO interventions
                (intervention_id, incident_id, type, hypothesis, description, owner,
                 start_time, end_time, expected_impact, status, updated_at)
            VALUES
                (:intervention_id, :incident_id, :type, :hypothesis, :description, :owner,
                 :start_time, :end_time, :expected_impact, 'proposed', now())
        """),
        {
            "intervention_id": intervention_id,
            "incident_id": payload.incident_id,
            "type": payload.type,
            "hypothesis": payload.hypothesis,
            "description": payload.description,
            "owner": payload.owner,
            "start_time": payload.start_time,
            "end_time": payload.end_time,
            "expected_impact": payload.expected_impact,
        },
    )
    log_action(db, action="intervention.created", entity_type="intervention", entity_id=intervention_id,
               actor=current_user["email"], metadata={"incident_id": payload.incident_id, "type": payload.type})
    db.commit()
    return get_intervention(str(intervention_id), db, current_user)


@router.get("/interventions/{intervention_id}")
def get_intervention(intervention_id: str, db: Session = Depends(get_db),
                      current_user: dict = Depends(get_current_user)):
    row = db.execute(
        text("SELECT * FROM interventions WHERE intervention_id = :id"), {"id": intervention_id}
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail={
            "error": {"code": "NOT_FOUND", "message": "Intervention not found"}
        })
    return _row_to_dict(row)


@router.patch("/interventions/{intervention_id}")
def update_intervention(intervention_id: str, payload: InterventionUpdate, db: Session = Depends(get_db),
                         current_user: dict = Depends(can_write_interventions)):
    current = db.execute(
        text("SELECT intervention_id FROM interventions WHERE intervention_id = :id"),
        {"id": intervention_id},
    ).first()
    if not current:
        raise HTTPException(status_code=404, detail={
            "error": {"code": "NOT_FOUND", "message": "Intervention not found"}
        })

    updates = []
    params = {"id": intervention_id}
    changes = {}

    if payload.status is not None:
        updates.append("status = :status")
        params["status"] = payload.status
        changes["status"] = payload.status
    if payload.end_time is not None:
        updates.append("end_time = :end_time")
        params["end_time"] = payload.end_time
        changes["end_time"] = str(payload.end_time)
    if payload.outcome is not None:
        updates.append("outcome = :outcome")
        params["outcome"] = payload.outcome
        changes["outcome"] = "updated"

    if not updates:
        raise HTTPException(status_code=400, detail={
            "error": {"code": "NO_CHANGES", "message": "No fields provided to update"}
        })

    updates.append("updated_at = now()")
    db.execute(text(f"UPDATE interventions SET {', '.join(updates)} WHERE intervention_id = :id"), params)
    log_action(db, action="intervention.updated", entity_type="intervention", entity_id=intervention_id,
               actor=current_user["email"], metadata=changes)
    db.commit()
    return get_intervention(intervention_id, db, current_user)


@router.post("/interventions/{intervention_id}/measure-impact")
def measure_impact(intervention_id: str, payload: MeasureImpactRequest, db: Session = Depends(get_db),
                    current_user: dict = Depends(can_write_interventions)):
    """
    Computes real before/after metrics for the intervention's affected segment
    using the same metrics engine as the dashboard/RCA -- never a hand-typed
    number. Filters default to the parent incident's affected_fingerprint.
    """
    row = db.execute(
        text("SELECT incident_id FROM interventions WHERE intervention_id = :id"),
        {"id": intervention_id},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail={
            "error": {"code": "NOT_FOUND", "message": "Intervention not found"}
        })

    filters = payload.filters
    if filters is None:
        incident = db.execute(
            text("SELECT affected_fingerprint FROM incidents WHERE incident_id = :id"),
            {"id": row["incident_id"]},
        ).mappings().first()
        filters = (incident["affected_fingerprint"] or {}) if incident else {}

    before_filters = {**filters, "start_date": payload.before_start, "end_date": payload.before_end}
    after_filters = {**filters, "start_date": payload.after_start, "end_date": payload.after_end}

    before_metrics = compute_core_metrics(engine, before_filters)
    after_metrics = compute_core_metrics(engine, after_filters)

    def delta(key):
        b, a = before_metrics.get(key), after_metrics.get(key)
        if b is None or a is None:
            return None
        return round(a - b, 2)

    impact = {
        "before": before_metrics,
        "after": after_metrics,
        "delta": {
            "psr_pp": delta("psr"),
            "failure_rate_pp": delta("failure_rate"),
            "recovery_rate_pp": delta("recovery_rate"),
            "duplicate_rate_pp": delta("duplicate_rate"),
        },
        "guardrail_status": "within_threshold" if (delta("duplicate_rate_pp") or 0) <= 0.5 else "breached",
    }

    db.execute(
        text("UPDATE interventions SET actual_impact = CAST(:impact AS JSONB), updated_at = now() "
             "WHERE intervention_id = :id"),
        {"impact": _dump_json(impact), "id": intervention_id},
    )
    log_action(db, action="intervention.impact_measured", entity_type="intervention", entity_id=intervention_id,
               actor=current_user["email"], metadata={"psr_delta_pp": impact["delta"]["psr_pp"]})
    db.commit()

    return impact


def _dump_json(value) -> str:
    import json
    return json.dumps(value, default=str)
