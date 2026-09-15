from collections.abc import Generator
from time import perf_counter

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings

settings = get_settings()

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator:
    """FastAPI dependency that yields a request-scoped DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- Lightweight in-process DB query timing (PRD Section 22: "Database query
# latency"). Deliberately NOT persisted to a table -- these are cheap,
# in-memory counters via SQLAlchemy's cursor-execute events, reset on
# process restart. See docs/decisions.md D45 for why this is in-process
# rather than logged per-query like api_request_logs.
_query_stats = {"count": 0, "total_ms": 0.0}


@event.listens_for(engine, "before_cursor_execute")
def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
    context._query_start_time = perf_counter()


@event.listens_for(engine, "after_cursor_execute")
def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
    elapsed_ms = (perf_counter() - context._query_start_time) * 1000
    _query_stats["count"] += 1
    _query_stats["total_ms"] += elapsed_ms


def get_db_query_stats() -> dict:
    count = _query_stats["count"]
    avg_ms = (_query_stats["total_ms"] / count) if count else None
    return {
        "total_queries_since_startup": count,
        "avg_query_ms": round(avg_ms, 2) if avg_ms is not None else None,
    }
