from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class InterventionCreate(BaseModel):
    incident_id: str
    type: str
    hypothesis: str
    description: str | None = None
    owner: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    expected_impact: str | None = None


class InterventionUpdate(BaseModel):
    status: str | None = Field(default=None, pattern="^(proposed|active|completed|abandoned)$")
    end_time: datetime | None = None
    outcome: str | None = None


class MeasureImpactRequest(BaseModel):
    """
    Computes a before/after comparison for the intervention's affected segment.
    Filters default to the parent incident's affected_fingerprint dimensions
    if not explicitly provided.
    """
    before_start: datetime
    before_end: datetime
    after_start: datetime
    after_end: datetime
    filters: dict | None = None


class InterventionResponse(BaseModel):
    intervention_id: str
    incident_id: str
    type: str
    hypothesis: str
    description: str | None
    owner: str | None
    start_time: datetime | None
    end_time: datetime | None
    expected_impact: str | None
    actual_impact: dict | None
    status: str
    outcome: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
