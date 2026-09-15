import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

# NOTE: `transactions` (the ~750K-row fact table) is deliberately NOT mapped as
# a full ORM model. All analytics reads against it go through
# app/analytics/*.py using pandas.read_sql with explicit column selection —
# this keeps large aggregate queries fast and keeps the ORM layer focused on
# the operational tables (incidents, interventions, users, etc.) where
# row-by-row object mapping is actually useful.


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False, default="viewer")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ErrorCode(Base):
    __tablename__ = "error_codes"

    error_code: Mapped[str] = mapped_column(String, primary_key=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    owner_team: Mapped[str] = mapped_column(String, nullable=False)
    recommended_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    active_flag: Mapped[bool] = mapped_column(Boolean, default=True)


class Incident(Base):
    __tablename__ = "incidents"

    incident_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    severity: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="open")
    owner: Mapped[str | None] = mapped_column(String, nullable=True)
    root_cause_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    affected_bank: Mapped[str | None] = mapped_column(String, nullable=True)
    affected_error: Mapped[str | None] = mapped_column(String, nullable=True)
    affected_fingerprint: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    estimated_value_at_risk: Mapped[float | None] = mapped_column(Numeric(16, 2), nullable=True)
    affected_transactions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    observed_psr: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    baseline_psr: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    interventions: Mapped[list["Intervention"]] = relationship(back_populates="incident")


class Intervention(Base):
    __tablename__ = "interventions"

    intervention_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("incidents.incident_id"))
    type: Mapped[str] = mapped_column(String, nullable=False)
    hypothesis: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner: Mapped[str | None] = mapped_column(String, nullable=True)
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expected_impact: Mapped[str | None] = mapped_column(Text, nullable=True)
    actual_impact: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="proposed")
    outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    incident: Mapped["Incident"] = relationship(back_populates="interventions")


class Experiment(Base):
    __tablename__ = "experiments"

    experiment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    hypothesis: Mapped[str] = mapped_column(Text, nullable=False)
    control_definition: Mapped[str] = mapped_column(Text, nullable=False)
    variant_definition: Mapped[str] = mapped_column(Text, nullable=False)
    primary_metric: Mapped[str] = mapped_column(String, nullable=False)
    secondary_metrics: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    guardrails: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sample_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SavedView(Base):
    __tablename__ = "saved_views"

    view_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.user_id"))
    name: Mapped[str] = mapped_column(String, nullable=False)
    filter_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    sharing_scope: Mapped[str] = mapped_column(String, default="private")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AuditLog(Base):
    __tablename__ = "audit_logs"

    audit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True)
    action: Mapped[str] = mapped_column(String, nullable=False)
    entity_type: Mapped[str] = mapped_column(String, nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    rows_processed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
