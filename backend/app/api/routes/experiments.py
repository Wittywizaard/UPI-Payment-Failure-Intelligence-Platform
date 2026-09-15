import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_role
from app.db.session import get_db
from app.schemas.experiments import ExperimentCreate

router = APIRouter(tags=["experiments"])
can_write_experiments = require_role("pm")


def _row_to_dict(row) -> dict:
    d = dict(row)
    if d.get("experiment_id") is not None:
        d["experiment_id"] = str(d["experiment_id"])
    return d


@router.get("/experiments/{experiment_id}")
def get_experiment(experiment_id: str, db: Session = Depends(get_db),
                    current_user: dict = Depends(get_current_user)):
    row = db.execute(
        text("SELECT * FROM experiments WHERE experiment_id = :id"), {"id": experiment_id}
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail={
            "error": {"code": "NOT_FOUND", "message": "Experiment not found"}
        })
    return _row_to_dict(row)


@router.get("/experiments")
def list_experiments(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """
    Extension beyond the strict API contract (only GET /api/experiments/{id}
    is specified) -- a list endpoint is needed for the Experiment Analysis
    screen to have anything to link to. See docs/decisions.md D19.
    """
    rows = db.execute(text("SELECT * FROM experiments ORDER BY created_at DESC")).mappings().all()
    return {"experiments": [_row_to_dict(r) for r in rows]}


@router.post("/experiments", status_code=201)
def create_experiment(payload: ExperimentCreate, db: Session = Depends(get_db),
                       current_user: dict = Depends(can_write_experiments)):
    experiment_id = uuid.uuid4()
    db.execute(
        text("""
            INSERT INTO experiments
                (experiment_id, name, hypothesis, control_definition, variant_definition,
                 primary_metric, secondary_metrics, guardrails, start_time, end_time,
                 sample_size, result_summary, is_simulated)
            VALUES
                (:experiment_id, :name, :hypothesis, :control_definition, :variant_definition,
                 :primary_metric, CAST(:secondary_metrics AS JSONB), CAST(:guardrails AS JSONB),
                 :start_time, :end_time, :sample_size, CAST(:result_summary AS JSONB), TRUE)
        """),
        {
            "experiment_id": experiment_id,
            "name": payload.name,
            "hypothesis": payload.hypothesis,
            "control_definition": payload.control_definition,
            "variant_definition": payload.variant_definition,
            "primary_metric": payload.primary_metric,
            "secondary_metrics": _dump_json(payload.secondary_metrics),
            "guardrails": _dump_json(payload.guardrails),
            "start_time": payload.start_time,
            "end_time": payload.end_time,
            "sample_size": payload.sample_size,
            "result_summary": _dump_json(payload.result_summary),
        },
    )
    db.commit()
    return get_experiment(str(experiment_id), db, current_user)


def _dump_json(value) -> str | None:
    import json
    return json.dumps(value) if value is not None else None
