from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ExperimentCreate(BaseModel):
    name: str
    hypothesis: str
    control_definition: str
    variant_definition: str
    primary_metric: str
    secondary_metrics: list[str] | None = None
    guardrails: list[str] | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    sample_size: int | None = None
    result_summary: dict | None = None


class ExperimentResponse(BaseModel):
    experiment_id: str
    name: str
    hypothesis: str
    control_definition: str
    variant_definition: str
    primary_metric: str
    secondary_metrics: list | None
    guardrails: list | None
    start_time: datetime | None
    end_time: datetime | None
    sample_size: int | None
    result_summary: dict | None
    is_simulated: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
