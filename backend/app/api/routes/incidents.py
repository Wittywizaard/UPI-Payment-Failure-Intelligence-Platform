import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.core.deps import get_current_user, require_role
from app.db.session import get_db
from app.schemas.incidents import IncidentCreate, IncidentUpdate

router = APIRouter(tags=["incidents"])
can_write_incidents = require_role("pm", "ops", "engineer")

VALID_TRANSITIONS = {
    "open": {"investigating", "closed"},
    "investigating": {"mitigated", "open", "closed"},
    "mitigated": {"resolved", "investigating"},
    "resolved": {"closed", "investigating"},
    "closed": set(),
}


def _row_to_dict(row) -> dict:
    d = dict(row)
    for key in ("incident_id",):
        if key in d and d[key] is not None:
            d[key] = str(d[key])
    return d


@router.post("/incidents", status_code=201)
def create_incident(payload: IncidentCreate, db: Session = Depends(get_db),
                     current_user: dict = Depends(can_write_incidents)):
    incident_id = uuid.uuid4()
    db.execute(
        text("""
            INSERT INTO incidents
                (incident_id, detected_at, severity, title, status, owner, root_cause_summary,
                 affected_bank, affected_error, affected_fingerprint, estimated_value_at_risk,
                 affected_transactions, observed_psr, baseline_psr, updated_at)
            VALUES
                (:incident_id, :detected_at, :severity, :title, 'open', :owner, :root_cause_summary,
                 :affected_bank, :affected_error, CAST(:affected_fingerprint AS JSONB),
                 :estimated_value_at_risk, :affected_transactions, :observed_psr, :baseline_psr, now())
        """),
        {
            "incident_id": incident_id,
            "detected_at": payload.detected_at,
            "severity": payload.severity,
            "title": payload.title,
            "owner": payload.owner,
            "root_cause_summary": payload.root_cause_summary,
            "affected_bank": payload.affected_bank,
            "affected_error": payload.affected_error,
            "affected_fingerprint": _dump_json(payload.affected_fingerprint),
            "estimated_value_at_risk": payload.estimated_value_at_risk,
            "affected_transactions": payload.affected_transactions,
            "observed_psr": payload.observed_psr,
            "baseline_psr": payload.baseline_psr,
        },
    )
    log_action(db, action="incident.created", entity_type="incident", entity_id=incident_id,
               actor=current_user["email"], metadata={"severity": payload.severity, "title": payload.title})
    db.commit()
    return get_incident(str(incident_id), db, current_user)


@router.get("/incidents")
def list_incidents(status: str | None = None, severity: str | None = None, db: Session = Depends(get_db),
                    current_user: dict = Depends(get_current_user)):
    clauses = ["1=1"]
    params = {}
    if status:
        clauses.append("status = :status")
        params["status"] = status
    if severity:
        clauses.append("severity = :severity")
        params["severity"] = severity
    where = " AND ".join(clauses)

    rows = db.execute(
        text(f"SELECT * FROM incidents WHERE {where} ORDER BY created_at DESC"), params
    ).mappings().all()
    return {"incidents": [_row_to_dict(r) for r in rows]}


@router.get("/incidents/{incident_id}")
def get_incident(incident_id: str, db: Session = Depends(get_db),
                  current_user: dict = Depends(get_current_user)):
    row = db.execute(
        text("SELECT * FROM incidents WHERE incident_id = :id"), {"id": incident_id}
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail={
            "error": {"code": "NOT_FOUND", "message": "Incident not found"}
        })

    interventions = db.execute(
        text("SELECT * FROM interventions WHERE incident_id = :id ORDER BY created_at"),
        {"id": incident_id},
    ).mappings().all()

    timeline = db.execute(
        text("""
            SELECT action, metadata_json, timestamp FROM audit_logs
            WHERE entity_type = 'incident' AND entity_id = :id
            ORDER BY timestamp
        """),
        {"id": incident_id},
    ).mappings().all()

    result = _row_to_dict(row)
    result["interventions"] = [
        {**_row_to_dict(i), "intervention_id": str(i["intervention_id"]), "incident_id": str(i["incident_id"])}
        for i in interventions
    ]
    result["timeline"] = [dict(t) for t in timeline]
    return result


@router.patch("/incidents/{incident_id}")
def update_incident(incident_id: str, payload: IncidentUpdate, db: Session = Depends(get_db),
                     current_user: dict = Depends(can_write_incidents)):
    current = db.execute(
        text("SELECT status FROM incidents WHERE incident_id = :id"), {"id": incident_id}
    ).mappings().first()
    if not current:
        raise HTTPException(status_code=404, detail={
            "error": {"code": "NOT_FOUND", "message": "Incident not found"}
        })

    updates = []
    params = {"id": incident_id}
    changes = {}

    if payload.status is not None:
        if payload.status != current["status"] and payload.status not in VALID_TRANSITIONS.get(current["status"], set()):
            raise HTTPException(status_code=400, detail={
                "error": {"code": "INVALID_TRANSITION",
                          "message": f"Cannot move incident from {current['status']} to {payload.status}"}
            })
        updates.append("status = :status")
        params["status"] = payload.status
        changes["status"] = payload.status
        if payload.status == "resolved":
            updates.append("resolved_at = now()")

    if payload.owner is not None:
        updates.append("owner = :owner")
        params["owner"] = payload.owner
        changes["owner"] = payload.owner

    if payload.root_cause_summary is not None:
        updates.append("root_cause_summary = :rcs")
        params["rcs"] = payload.root_cause_summary
        changes["root_cause_summary"] = "updated"

    if not updates and not payload.note:
        raise HTTPException(status_code=400, detail={
            "error": {"code": "NO_CHANGES", "message": "No fields provided to update"}
        })

    if updates:
        updates.append("updated_at = now()")
        db.execute(text(f"UPDATE incidents SET {', '.join(updates)} WHERE incident_id = :id"), params)

    if changes:
        log_action(db, action="incident.updated", entity_type="incident", entity_id=incident_id,
                   actor=current_user["email"], metadata=changes)
    if payload.note:
        log_action(db, action="incident.note_added", entity_type="incident", entity_id=incident_id,
                   actor=current_user["email"], metadata={"note": payload.note})

    db.commit()
    return get_incident(incident_id, db, current_user)


def _dump_json(value) -> str | None:
    import json
    return json.dumps(value) if value is not None else None
