"""
Failure Fingerprint engine (PRD Section 9 / Section 14).

Searches a curated set of dimension combinations (not the full powerset --
see docs/decisions.md D13) for segments whose failure behavior in an
"observed" time window deviates materially from that same segment's own
historical baseline, and ranks them by their share of the window's total
incremental failures.

A fingerprint must clear ALL of:
  - MIN_VOLUME: enough transactions to be statistically/operationally meaningful
  - MIN_DEVIATION_RATIO: observed failure rate is at least Nx the segment's baseline
  - MIN_CONTRIBUTION: the segment explains a material share of the window's
    incremental (above-baseline) failures dataset-wide

Language throughout is "probable contributor" -- correlation, not proven
causation (PRD Section 11).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

MIN_VOLUME = 150
MIN_DEVIATION_RATIO = 2.5       # observed failure rate >= 2.5x segment baseline
MIN_ABSOLUTE_DEVIATION_PP = 8.0  # ...and at least +8 percentage points
MIN_CONTRIBUTION = 0.03         # explains >= 3% of the window's incremental failures
MAX_FINGERPRINTS_RETURNED = 15

# Curated candidate dimension sets -- avoids the combinatorial explosion of a
# full powerset over ~9 dimensions while still covering the patterns real
# payment incidents tend to take (single bank issue, bank+platform issue,
# app-release regression, network-class issue, and the compound
# bank+device+OS+app-version pattern the RCA screen is built around).
CANDIDATE_DIMENSION_SETS: list[tuple[str, ...]] = [
    ("payer_bank",),
    ("psp",),
    ("device_type",),
    ("os",),
    ("app_version",),
    ("network_type",),
    ("transaction_type",),
    ("error_code",),
    ("payer_bank", "device_type"),
    ("payer_bank", "os"),
    ("payer_bank", "app_version"),
    ("device_type", "os"),
    ("os", "app_version"),
    ("device_type", "app_version"),
    ("payer_bank", "network_type"),
    ("payer_bank", "device_type", "os"),
    ("payer_bank", "os", "app_version"),
    ("device_type", "os", "app_version"),
    ("payer_bank", "device_type", "os", "app_version"),
]

ALL_DIMENSIONS = sorted({d for combo in CANDIDATE_DIMENSION_SETS for d in combo})


@dataclass
class Fingerprint:
    dimensions: dict
    volume: int
    failed_count: int
    observed_failure_rate: float
    baseline_failure_rate: float
    deviation_pp: float
    contribution: float
    value_at_risk: float
    n_dims: int = field(init=False)

    def __post_init__(self):
        self.n_dims = len(self.dimensions)

    def label(self) -> str:
        return " × ".join(str(v) for v in self.dimensions.values())

    def to_dict(self) -> dict:
        return {
            "dimensions": self.dimensions,
            "label": self.label(),
            "volume": self.volume,
            "failed_count": self.failed_count,
            "observed_failure_rate_pct": round(self.observed_failure_rate * 100, 2),
            "baseline_failure_rate_pct": round(self.baseline_failure_rate * 100, 2),
            "deviation_pp": round(self.deviation_pp * 100, 2),
            "contribution_pct": round(min(self.contribution, 1.0) * 100, 2),
            "value_at_risk": round(self.value_at_risk, 2),
        }


def _grouped_counts(engine: Engine, dims: tuple[str, ...], start: datetime, end: datetime) -> pd.DataFrame:
    dim_cols = ", ".join(dims)
    sql = text(f"""
        SELECT {dim_cols},
               count(*) AS volume,
               sum((status = 'FAILED')::int) AS failed,
               coalesce(sum(amount) FILTER (WHERE status = 'FAILED'), 0) AS value_at_risk
        FROM transactions
        WHERE ts >= :start AND ts < :end AND is_eligible
        GROUP BY {dim_cols}
    """)
    with engine.connect() as conn:
        return pd.read_sql(sql, conn, params={"start": start, "end": end})


def _baseline_window(observed_start: datetime, observed_end: datetime, baseline_days: int) -> list[tuple[datetime, datetime]]:
    """Same hour-of-day range on each of the preceding `baseline_days` days."""
    windows = []
    duration = observed_end - observed_start
    for i in range(1, baseline_days + 1):
        b_start = observed_start - timedelta(days=i)
        windows.append((b_start, b_start + duration))
    return windows


def _baseline_grouped_counts(engine: Engine, dims: tuple[str, ...], observed_start: datetime,
                              observed_end: datetime, baseline_days: int) -> pd.DataFrame:
    frames = []
    for b_start, b_end in _baseline_window(observed_start, observed_end, baseline_days):
        frames.append(_grouped_counts(engine, dims, b_start, b_end))
    if not frames:
        return pd.DataFrame(columns=list(dims) + ["volume", "failed", "value_at_risk"])
    combined = pd.concat(frames, ignore_index=True)
    agg = combined.groupby(list(dims), as_index=False).agg(volume=("volume", "sum"), failed=("failed", "sum"))
    return agg


def _dataset_wide_incremental_failures(engine: Engine, observed_start: datetime, observed_end: datetime,
                                        baseline_days: int) -> float:
    """Total 'extra' failures in the observed window vs. the dataset's own overall baseline rate."""
    with engine.connect() as conn:
        observed_row = pd.read_sql(
            text("SELECT count(*) AS volume, sum((status='FAILED')::int) AS failed "
                 "FROM transactions WHERE ts >= :start AND ts < :end AND is_eligible"),
            conn, params={"start": observed_start, "end": observed_end},
        ).iloc[0]
    observed_volume = int(observed_row["volume"])
    observed_failed = int(observed_row["failed"] or 0)

    baseline_volume_total = 0
    baseline_failed_total = 0
    with engine.connect() as conn:
        for b_start, b_end in _baseline_window(observed_start, observed_end, baseline_days):
            b_row = pd.read_sql(
                text("SELECT count(*) AS volume, sum((status='FAILED')::int) AS failed "
                     "FROM transactions WHERE ts >= :start AND ts < :end AND is_eligible"),
                conn, params={"start": b_start, "end": b_end},
            ).iloc[0]
            baseline_volume_total += int(b_row["volume"])
            baseline_failed_total += int(b_row["failed"] or 0)

    baseline_rate = (baseline_failed_total / baseline_volume_total) if baseline_volume_total else 0.0
    incremental = observed_failed - baseline_rate * observed_volume
    return max(incremental, 1.0)  # avoid division by zero downstream


def scan_single_dimension(engine: Engine, dimension: str, observed_start: datetime, observed_end: datetime,
                           baseline_days: int = 7) -> list[dict]:
    """
    Ranks contribution for a single dimension WITHOUT the multi-combo dedup
    applied in run_fingerprint_scan. Used when a question is specifically
    about one dimension (e.g. "which bank contributed most?") -- the RCA
    screen's dedup deliberately drops a broader single-dimension finding when
    a more specific fingerprint fully explains it, but that same finding is
    exactly what a dimension-specific question is asking for. See
    docs/decisions.md D37.
    """
    total_incremental = _dataset_wide_incremental_failures(engine, observed_start, observed_end, baseline_days)
    dims = (dimension,)
    observed = _grouped_counts(engine, dims, observed_start, observed_end)
    if observed.empty:
        return []
    baseline = _baseline_grouped_counts(engine, dims, observed_start, observed_end, baseline_days)
    merged = observed.merge(baseline, on=list(dims), how="left", suffixes=("", "_baseline"))
    merged["volume_baseline"] = merged["volume_baseline"].fillna(0)
    merged["failed_baseline"] = merged["failed_baseline"].fillna(0)

    results = []
    for _, row in merged.iterrows():
        volume = int(row["volume"])
        failed = int(row["failed"])
        if volume < MIN_VOLUME or failed == 0:
            continue
        observed_rate = failed / volume
        baseline_volume = row["volume_baseline"]
        baseline_failed = row["failed_baseline"]
        baseline_rate = max((baseline_failed / baseline_volume) if baseline_volume > 0 else 0.005, 0.001)
        incremental = max(failed - baseline_rate * volume, 0.0)
        contribution = min(incremental / total_incremental, 1.0)
        results.append({
            "dimensions": {dimension: row[dimension]},
            "label": str(row[dimension]),
            "volume": volume,
            "failed_count": failed,
            "observed_failure_rate_pct": round(observed_rate * 100, 2),
            "baseline_failure_rate_pct": round(baseline_rate * 100, 2),
            "contribution_pct": round(contribution * 100, 2),
            "value_at_risk": round(float(row["value_at_risk"]), 2),
        })

    results.sort(key=lambda r: r["contribution_pct"], reverse=True)
    return results


def run_fingerprint_scan(engine: Engine, observed_start: datetime, observed_end: datetime,
                          baseline_days: int = 7) -> list[dict]:
    total_incremental = _dataset_wide_incremental_failures(engine, observed_start, observed_end, baseline_days)

    candidates: list[Fingerprint] = []

    for dims in CANDIDATE_DIMENSION_SETS:
        observed = _grouped_counts(engine, dims, observed_start, observed_end)
        if observed.empty:
            continue
        baseline = _baseline_grouped_counts(engine, dims, observed_start, observed_end, baseline_days)

        merged = observed.merge(baseline, on=list(dims), how="left", suffixes=("", "_baseline"))
        merged["volume_baseline"] = merged["volume_baseline"].fillna(0)
        merged["failed_baseline"] = merged["failed_baseline"].fillna(0)

        for _, row in merged.iterrows():
            volume = int(row["volume"])
            failed = int(row["failed"])
            if volume < MIN_VOLUME or failed == 0:
                continue

            observed_rate = failed / volume
            baseline_volume = row["volume_baseline"]
            baseline_failed = row["failed_baseline"]
            baseline_rate = (baseline_failed / baseline_volume) if baseline_volume > 0 else 0.005
            baseline_rate = max(baseline_rate, 0.001)  # floor to avoid inflated ratios from sparse baselines

            deviation_ratio = observed_rate / baseline_rate
            deviation_pp = observed_rate - baseline_rate

            if deviation_ratio < MIN_DEVIATION_RATIO or deviation_pp < (MIN_ABSOLUTE_DEVIATION_PP / 100):
                continue

            incremental = max(failed - baseline_rate * volume, 0.0)
            contribution = incremental / total_incremental
            if contribution < MIN_CONTRIBUTION:
                continue

            dim_values = {d: row[d] for d in dims}
            candidates.append(Fingerprint(
                dimensions=dim_values,
                volume=volume,
                failed_count=failed,
                observed_failure_rate=observed_rate,
                baseline_failure_rate=baseline_rate,
                deviation_pp=deviation_pp,
                contribution=contribution,
                value_at_risk=float(row["value_at_risk"]),
            ))

    candidates.sort(key=lambda fp: (fp.contribution, fp.n_dims), reverse=True)
    deduped = _dedupe_nested_fingerprints(candidates)
    return [fp.to_dict() for fp in deduped[:MAX_FINGERPRINTS_RETURNED]]


def _dedupe_nested_fingerprints(candidates: list[Fingerprint]) -> list[Fingerprint]:
    """
    Drops broader (fewer-dimension) fingerprints whose dimension/value pairs
    are a strict subset of an already-selected, higher-contribution, more
    specific fingerprint -- e.g. don't report 'BANK_A' AND
    'BANK_A x Android x U28 x v4.2.1' as two separate findings when the
    latter already explains the former. See docs/decisions.md D14.
    """
    selected: list[Fingerprint] = []
    for candidate in candidates:
        is_redundant = any(
            _is_subset(candidate.dimensions, kept.dimensions) and candidate.contribution <= kept.contribution
            for kept in selected
        )
        if not is_redundant:
            selected.append(candidate)
    return selected


def _is_subset(smaller: dict, larger: dict) -> bool:
    if len(smaller) >= len(larger):
        return False
    return all(larger.get(k) == v for k, v in smaller.items())
