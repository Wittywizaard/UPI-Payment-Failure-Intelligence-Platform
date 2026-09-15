from pydantic import BaseModel, Field


class AiAnalyzeRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)


class AiAnalyzeResponse(BaseModel):
    question: str
    intent: str
    time_period: str
    filters: dict
    metrics_used: list[str]
    evidence: list[dict]
    limitations: str
    answer: str
    deep_link: str | None
    llm_used: bool
