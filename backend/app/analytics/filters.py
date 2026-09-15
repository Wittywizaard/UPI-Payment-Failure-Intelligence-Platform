"""
Builds a parameterized WHERE clause from a filter dict shared by the metrics
engine, fingerprint engine, and Failure Explorer API. Every value is bound via
SQLAlchemy bindparams -- never string-interpolated -- per the PRD's SQL
injection requirement.

Supported filter keys (all optional):
    start_date, end_date: datetime
    payer_bank, payee_bank, psp, error_code, error_category, device_type,
    os, app_version, network_type, transaction_type, geography: str | list[str]
    amount_min, amount_max: float
"""

from __future__ import annotations

from sqlalchemy import bindparam

LIST_FILTER_COLUMNS = [
    "payer_bank", "payee_bank", "psp", "error_code", "error_category",
    "device_type", "os", "app_version", "network_type", "transaction_type",
    "geography",
]


def build_where_clause(filters: dict) -> tuple[str, dict, list]:
    """
    Returns (where_sql, params, expanding_bindparams).
    where_sql is safe to interpolate into a query string (it contains only
    column names and :param placeholders, never raw filter values).
    """
    clauses: list[str] = ["1=1"]
    params: dict = {}
    expanding: list = []

    if filters.get("start_date"):
        clauses.append("ts >= :start_date")
        params["start_date"] = filters["start_date"]

    if filters.get("end_date"):
        clauses.append("ts < :end_date")
        params["end_date"] = filters["end_date"]

    if filters.get("amount_min") is not None:
        clauses.append("amount >= :amount_min")
        params["amount_min"] = filters["amount_min"]

    if filters.get("amount_max") is not None:
        clauses.append("amount <= :amount_max")
        params["amount_max"] = filters["amount_max"]

    for col in LIST_FILTER_COLUMNS:
        value = filters.get(col)
        if value is None:
            continue
        values = value if isinstance(value, list) else [value]
        if not values:
            continue
        clauses.append(f"{col} IN :{col}_list")
        params[f"{col}_list"] = tuple(values)
        expanding.append(bindparam(f"{col}_list", expanding=True))

    return " AND ".join(clauses), params, expanding
