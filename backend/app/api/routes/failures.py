from datetime import datetime

import pandas as pd
from fastapi import APIRouter, Depends, Query
from sqlalchemy import text

from app.analytics.filters import build_where_clause
from app.analytics.metrics import compute_core_metrics, get_avg_processing_time_ms
from app.core.deps import get_current_user
from app.db.session import engine

router = APIRouter(tags=["failures"])


@router.get("/failures")
def get_failures(
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    payer_bank: str | None = None,
    payee_bank: str | None = None,
    psp: str | None = None,
    error_code: str | None = None,
    error_category: str | None = None,
    device_type: str | None = None,
    os: str | None = None,
    app_version: str | None = None,
    network_type: str | None = None,
    transaction_type: str | None = None,
    geography: str | None = None,
    amount_min: float | None = None,
    amount_max: float | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    current_user: dict = Depends(get_current_user),
):
    filters = {k: v for k, v in {
        "start_date": start_date, "end_date": end_date, "payer_bank": payer_bank,
        "payee_bank": payee_bank, "psp": psp, "error_code": error_code,
        "error_category": error_category, "device_type": device_type, "os": os,
        "app_version": app_version, "network_type": network_type,
        "transaction_type": transaction_type, "geography": geography,
        "amount_min": amount_min, "amount_max": amount_max,
    }.items() if v is not None}

    metrics = compute_core_metrics(engine, filters)
    avg_processing_time = get_avg_processing_time_ms(engine, filters)

    where_clause, params, expanding = build_where_clause(filters)
    count_sql = text(f"SELECT count(*) AS n FROM transactions WHERE {where_clause}")
    if expanding:
        count_sql = count_sql.bindparams(*expanding)
    with engine.connect() as conn:
        total_rows = pd.read_sql(count_sql, conn, params=params).iloc[0]["n"]

    offset = (page - 1) * page_size
    detail_sql = text(f"""
        SELECT transaction_id, ts, payer_bank, payee_bank, psp, amount, status,
               error_code, device_type, os, app_version, network_type,
               transaction_type, geography, processing_time_ms
        FROM transactions
        WHERE {where_clause}
        ORDER BY ts DESC
        LIMIT :limit OFFSET :offset
    """)
    if expanding:
        detail_sql = detail_sql.bindparams(*expanding)
    with engine.connect() as conn:
        rows = pd.read_sql(detail_sql, conn, params={**params, "limit": page_size, "offset": offset})

    return {
        "filters": filters,
        "segment_summary": {
            "volume": metrics["total_transactions"],
            "success_count": metrics["eligible_success"],
            "failure_count": metrics["eligible_failed"],
            "psr": metrics["psr"],
            "failure_rate": metrics["failure_rate"],
            "avg_processing_time_ms": avg_processing_time,
            "value_at_risk": metrics["value_at_risk"],
        },
        "pagination": {
            "page": page, "page_size": page_size, "total_rows": int(total_rows),
            "total_pages": (int(total_rows) + page_size - 1) // page_size,
        },
        "transactions": rows.to_dict(orient="records"),
    }
