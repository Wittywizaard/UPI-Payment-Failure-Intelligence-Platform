from fastapi import APIRouter, Depends, Request

from app.ai.orchestrator import analyze_question
from app.api.routes.auth import limiter
from app.core.deps import get_current_user
from app.core.config import get_settings
from app.db.session import engine
from app.schemas.ai import AiAnalyzeRequest, AiAnalyzeResponse

router = APIRouter(tags=["ai"])
settings = get_settings()


@router.post("/ai/analyze", response_model=AiAnalyzeResponse)
@limiter.limit(f"{settings.AI_RATE_LIMIT_PER_MINUTE}/minute")
def analyze(request: Request, payload: AiAnalyzeRequest, current_user: dict = Depends(get_current_user)):
    """
    Natural-language payment intelligence (PRD Section 16). Available to all
    authenticated roles -- unlike incident/intervention writes, asking a
    question doesn't change platform state, so it isn't role-restricted.
    """
    result = analyze_question(engine, payload.question)
    return result
