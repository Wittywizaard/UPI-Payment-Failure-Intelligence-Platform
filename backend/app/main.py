import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import SessionLocal, engine
from app.api.routes import dashboard, failures, rca, incidents, interventions, experiments, auth, ai, observability

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("upi_fip")

settings = get_settings()

app = FastAPI(
    title="UPI Payment Failure Intelligence Platform API",
    version="0.1.0",
    description=(
        "Internal payment-observability API. Uses synthetic transaction data only. "
        "Does not process, authorize, or route real payments."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.limiter = auth.limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


# Endpoints excluded from api_request_logs to keep the table free of
# constant liveness-probe noise (health checks can fire every few seconds
# from Docker/Compose); everything that reflects real feature usage is kept.
_METRICS_EXCLUDED_PATHS = {"/api/health", "/api/data-freshness"}


def _record_request_metric(request_id: str, method: str, path: str, status_code: int, duration_ms: float) -> None:
    if path in _METRICS_EXCLUDED_PATHS:
        return
    try:
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO api_request_logs (request_id, method, path, status_code, duration_ms)
                    VALUES (:request_id, :method, :path, :status_code, :duration_ms)
                """),
                {
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": round(duration_ms, 2),
                },
            )
    except Exception:  # noqa: BLE001
        # Observability must never break the actual request it's measuring.
        logger.exception("Failed to record request metric [request_id=%s]", request_id)


@app.middleware("http")
async def add_request_id_and_metrics(request: Request, call_next):
    """Attaches a request ID to every response and records latency/status
    for the observability endpoint (PRD Section 22)."""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    start = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (time.perf_counter() - start) * 1000
        _record_request_metric(request_id, request.method, request.url.path, 500, duration_ms)
        raise

    duration_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Request-ID"] = request_id
    _record_request_metric(request_id, request.method, request.url.path, response.status_code, duration_ms)
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", "unknown")
    logger.exception("Unhandled error [request_id=%s]", request_id)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred.",
                "request_id": request_id,
            }
        },
    )


@app.get("/api/health", tags=["system"])
def health_check():
    """Liveness + DB connectivity check."""
    db_status = "ok"
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
    except Exception as exc:  # noqa: BLE001
        db_status = f"error: {exc}"

    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "database": db_status,
        "environment": settings.ENVIRONMENT,
    }


@app.get("/api/data-freshness", tags=["system"])
def data_freshness():
    """
    Reports the latest successful pipeline run so the UI can show
    'Data fresh as of ...' rather than implying real-time data.
    """
    db = SessionLocal()
    try:
        row = db.execute(
            text(
                """
                SELECT run_id, completed_at, rows_processed
                FROM pipeline_runs
                WHERE status = 'success'
                ORDER BY completed_at DESC
                LIMIT 1
                """
            )
        ).mappings().first()
    finally:
        db.close()

    if not row:
        return {"status": "no_successful_runs", "last_run": None}

    return {
        "status": "ok",
        "last_run": {
            "run_id": str(row["run_id"]),
            "completed_at": row["completed_at"].isoformat() if row["completed_at"] else None,
            "rows_processed": row["rows_processed"],
        },
    }


# Route modules are registered as each is implemented.
app.include_router(auth.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(failures.router, prefix="/api")
app.include_router(rca.router, prefix="/api")
app.include_router(incidents.router, prefix="/api")
app.include_router(interventions.router, prefix="/api")
app.include_router(experiments.router, prefix="/api")
app.include_router(ai.router, prefix="/api")
app.include_router(observability.router, prefix="/api")
