from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class IncidentCreate(BaseModel):
    title: str
    severity: str = Field(pattern="^(P0|P1|P2)$")
    detected_at: datetime
    owner: str | None = None
    root_cause_summary: str | None = None
    affected_bank: str | None = None
    affected_error: str | None = None
    affected_fingerprint: dict | None = None
    estimated_value_at_risk: float | None = None
    affected_transactions: int | None = None
    observed_psr: float | None = None
    baseline_psr: float | None = None


class IncidentUpdate(BaseModel):
    status: str | None = Field(default=None, pattern="^(open|investigating|mitigated|resolved|closed)$")
    owner: str | None = None
    root_cause_summary: str | None = None
    note: str | None = None  # appended to the audit-log timeline, not stored as a column


class IncidentResponse(BaseModel):
    incident_id: str
    created_at: datetime
    detected_at: datetime
    severity: str
    title: str
    status: str
    owner: str | None
    root_cause_summary: str | None
    affected_bank: str | None
    affected_error: str | None
    affected_fingerprint: dict | None
    estimated_value_at_risk: float | None
    affected_transactions: int | None
    observed_psr: float | None
    baseline_psr: float | None
    resolved_at: datetime | None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
