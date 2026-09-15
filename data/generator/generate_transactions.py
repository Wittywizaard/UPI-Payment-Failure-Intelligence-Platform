"""
Deterministic synthetic UPI transaction generator.

Given the same --seed and --count, this script produces byte-for-byte identical
business data (only the vectorized RNG-derived transaction_ids are randomized
*from* that same seeded generator, so re-running with the same seed reproduces
an identical dataset end-to-end).

The dataset intentionally contains one injected failure anomaly:
BANK_A x Android x U28 x app v4.2.1 x 18:00-20:00 on the last day of the
generated window (see dimensions.ANOMALY_FINGERPRINT). Ground truth for that
injection is written to ground_truth.json for use by the RCA-evaluation test
suite only -- it is never fed to the detection/RCA engine itself.

Usage:
    python generate_transactions.py --seed 42 --count 750000 --out transactions.csv
"""

from __future__ import annotations

import argparse
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

import dimensions as dim

N_DAYS = 14
END_DATE = datetime(2026, 8, 29, tzinfo=timezone.utc)  # fixed anchor -> reproducible across runs
START_DATE = END_DATE - timedelta(days=N_DAYS - 1)

# Hourly traffic-shape weights (index = hour 0-23). Morning + evening peaks,
# a lunchtime bump, and a quiet overnight trough -- typical payment-app shape.
HOURLY_WEIGHTS = np.array([
    0.010, 0.006, 0.004, 0.003, 0.004, 0.008, 0.018, 0.032,
    0.048, 0.058, 0.062, 0.058, 0.060, 0.055, 0.048, 0.045,
    0.050, 0.058, 0.068, 0.065, 0.055, 0.042, 0.028, 0.017,
])
HOURLY_WEIGHTS = HOURLY_WEIGHTS / HOURLY_WEIGHTS.sum()


def weighted_choice(rng: np.random.Generator, weights: dict, size: int) -> np.ndarray:
    keys = np.array(list(weights.keys()), dtype=object)
    probs = np.array(list(weights.values()), dtype=float)
    probs = probs / probs.sum()
    idx = rng.choice(len(keys), size=size, p=probs)
    return keys[idx]


def rng_uuids(rng: np.random.Generator, size: int) -> np.ndarray:
    raw = rng.integers(0, 256, size=(size, 16), dtype=np.uint8)
    return np.array([uuid.UUID(bytes=row.tobytes()) for row in raw], dtype=object)


def sample_timestamps(rng: np.random.Generator, size: int, day_low: int, day_high: int,
                       hour_low: int = 0, hour_high: int = 24) -> pd.Series:
    """day_low/day_high are offsets from START_DATE (inclusive/exclusive)."""
    day_offsets = rng.integers(day_low, day_high, size=size)
    if hour_low == 0 and hour_high == 24:
        hours = rng.choice(24, size=size, p=HOURLY_WEIGHTS)
    else:
        hours = rng.integers(hour_low, hour_high, size=size)
    minutes = rng.integers(0, 60, size=size)
    seconds = rng.integers(0, 60, size=size)
    base = pd.to_datetime(START_DATE) + pd.to_timedelta(day_offsets, unit="D")
    ts = base + pd.to_timedelta(hours, unit="h") + pd.to_timedelta(minutes, unit="m") \
        + pd.to_timedelta(seconds, unit="s")
    return ts


def conditional_choice(rng: np.random.Generator, condition_values: np.ndarray,
                        weights_by_condition: dict) -> np.ndarray:
    """Vectorized weighted choice where the distribution depends on another column."""
    result = np.empty(len(condition_values), dtype=object)
    for cond_val, weights in weights_by_condition.items():
        mask = condition_values == cond_val
        n = int(mask.sum())
        if n > 0:
            result[mask] = weighted_choice(rng, weights, n)
    return result


def make_amounts(rng: np.random.Generator, size: int) -> np.ndarray:
    amounts = rng.lognormal(mean=6.6, sigma=1.05, size=size)
    amounts = np.clip(amounts, 10, 200_000)
    return np.round(amounts, 2)


def build_base_population(rng: np.random.Generator, n: int) -> pd.DataFrame:
    device_type = weighted_choice(rng, dim.DEVICE_TYPES, n)
    os_ = conditional_choice(rng, device_type, dim.OS_BY_DEVICE)

    df = pd.DataFrame({
        "ts": sample_timestamps(rng, n, 0, N_DAYS),
        "payer_bank": weighted_choice(rng, dim.BANKS, n),
        "payee_bank": weighted_choice(rng, dim.BANKS, n),
        "psp": weighted_choice(rng, dim.PSPS, n),
        "amount": make_amounts(rng, n),
        "currency": "INR",
        "device_type": device_type,
        "os": os_,
        "app_version": weighted_choice(rng, dim.APP_VERSIONS, n),
        "network_type": weighted_choice(rng, dim.NETWORK_TYPES, n),
        "transaction_type": weighted_choice(rng, dim.TRANSACTION_TYPES, n),
        "geography": weighted_choice(rng, dim.GEOGRAPHIES, n),
    })

    # Failure probability modulated slightly by network quality -- realism,
    # not the injected anomaly (that's handled separately).
    base_prob = np.full(n, dim.BASELINE_FAILURE_RATE)
    base_prob = np.where(df["network_type"] == "UNSTABLE", base_prob * 2.6, base_prob)
    base_prob = np.where(df["network_type"] == "WIFI", base_prob * 0.85, base_prob)

    is_failed = rng.random(n) < base_prob
    df["status"] = np.where(is_failed, "FAILED", "SUCCESS")

    pending_mask = (df["status"] == "SUCCESS") & (rng.random(n) < dim.PENDING_RATE)
    df.loc[pending_mask, "status"] = "PENDING"

    df["error_code"] = None
    failed_mask = df["status"] == "FAILED"
    n_failed = int(failed_mask.sum())
    df.loc[failed_mask, "error_code"] = weighted_choice(rng, dim.FAILURE_ERROR_DIST, n_failed)
    df["error_category"] = df["error_code"].map(dim.ERROR_CATEGORY_BY_CODE)

    proc_time = np.where(
        df["status"] == "SUCCESS",
        rng.normal(800, 250, n),
        np.where(df["status"] == "FAILED", rng.normal(1300, 500, n), rng.normal(6000, 1500, n)),
    )
    df["processing_time_ms"] = np.clip(proc_time, 80, None).astype(int)

    df["retry_count"] = 0
    df["is_duplicate"] = False
    df["original_transaction_id"] = None
    df["transaction_id"] = rng_uuids(rng, n)
    return df


def build_anomaly_segment(rng: np.random.Generator, n: int) -> pd.DataFrame:
    fp = dim.ANOMALY_FINGERPRINT
    last_day_offset = N_DAYS - 1  # the last day of the window

    df = pd.DataFrame({
        "ts": sample_timestamps(
            rng, n, last_day_offset, last_day_offset + 1,
            hour_low=dim.ANOMALY_WINDOW_START_HOUR, hour_high=dim.ANOMALY_WINDOW_END_HOUR,
        ),
        "payer_bank": fp["payer_bank"],
        "payee_bank": weighted_choice(rng, dim.BANKS, n),
        "psp": weighted_choice(rng, dim.PSPS, n),
        "amount": make_amounts(rng, n),
        "currency": "INR",
        "device_type": fp["device_type"],
        "os": fp["os"],
        "app_version": fp["app_version"],
        "network_type": weighted_choice(rng, dim.NETWORK_TYPES, n),
        "transaction_type": weighted_choice(rng, dim.TRANSACTION_TYPES, n),
        "geography": weighted_choice(rng, dim.GEOGRAPHIES, n),
    })

    is_failed = rng.random(n) < dim.ANOMALY_FAILURE_RATE
    df["status"] = np.where(is_failed, "FAILED", "SUCCESS")

    df["error_code"] = None
    failed_mask = df["status"] == "FAILED"
    n_failed = int(failed_mask.sum())
    df.loc[failed_mask, "error_code"] = weighted_choice(rng, dim.ANOMALY_FAILURE_ERROR_DIST, n_failed)
    df["error_category"] = df["error_code"].map(dim.ERROR_CATEGORY_BY_CODE)

    proc_time = np.where(df["status"] == "SUCCESS", rng.normal(900, 250, n), rng.normal(2100, 700, n))
    df["processing_time_ms"] = np.clip(proc_time, 80, None).astype(int)

    df["retry_count"] = 0
    df["is_duplicate"] = False
    df["original_transaction_id"] = None
    df["transaction_id"] = rng_uuids(rng, n)
    return df


def add_retries(rng: np.random.Generator, df: pd.DataFrame) -> pd.DataFrame:
    """For a subset of eligible failed transactions, append a follow-up retry row."""
    eligible_failed = df[(df["status"] == "FAILED") & (df["error_code"] != "USER_CANCELLED")]
    retry_mask = rng.random(len(eligible_failed)) < dim.RETRY_PROBABILITY_AFTER_FAILURE
    retried = eligible_failed[retry_mask]

    if retried.empty:
        return df

    df.loc[retried.index, "retry_count"] = 1

    n = len(retried)
    retry_success = rng.random(n) < dim.RETRY_SUCCESS_PROBABILITY
    retry_status = np.where(retry_success, "SUCCESS", "FAILED")

    delay_seconds = rng.integers(30, 300, n)
    retry_ts = (retried["ts"] + pd.to_timedelta(delay_seconds, unit="s")).to_numpy()

    retry_error = np.array([None] * n, dtype=object)
    failed_retry_mask = retry_status == "FAILED"
    n_failed_retry = int(failed_retry_mask.sum())
    if n_failed_retry:
        retry_error[failed_retry_mask] = weighted_choice(rng, dim.FAILURE_ERROR_DIST, n_failed_retry)

    retry_df = pd.DataFrame({
        "ts": retry_ts,
        "payer_bank": retried["payer_bank"].to_numpy(),
        "payee_bank": retried["payee_bank"].to_numpy(),
        "psp": retried["psp"].to_numpy(),
        "amount": retried["amount"].to_numpy(),
        "currency": "INR",
        "device_type": retried["device_type"].to_numpy(),
        "os": retried["os"].to_numpy(),
        "app_version": retried["app_version"].to_numpy(),
        "network_type": retried["network_type"].to_numpy(),
        "transaction_type": retried["transaction_type"].to_numpy(),
        "geography": retried["geography"].to_numpy(),
        "status": retry_status,
        "error_code": retry_error,
        "processing_time_ms": np.clip(rng.normal(1000, 300, n), 80, None).astype(int),
        "retry_count": 1,
        "is_duplicate": False,
        "original_transaction_id": retried["transaction_id"].to_numpy(),
        "transaction_id": rng_uuids(rng, n),
    })
    retry_df["error_category"] = retry_df["error_code"].map(dim.ERROR_CATEGORY_BY_CODE)

    return pd.concat([df, retry_df], ignore_index=True)


def add_duplicates(rng: np.random.Generator, df: pd.DataFrame) -> pd.DataFrame:
    """Append a small number of duplicate transactions for duplicate-rate testing."""
    n_dupes = int(len(df) * dim.DUPLICATE_RATE)
    if n_dupes == 0:
        return df

    source_idx = rng.choice(df.index.to_numpy(), size=n_dupes, replace=False)
    source = df.loc[source_idx]

    delay_seconds = rng.integers(2, 45, n_dupes)
    dup_ts = (source["ts"] + pd.to_timedelta(delay_seconds, unit="s")).to_numpy()
    dup_success = rng.random(n_dupes) < 0.9
    dup_status = np.where(dup_success, "SUCCESS", "FAILED")

    dup_error = np.array([None] * n_dupes, dtype=object)
    dup_failed_mask = dup_status == "FAILED"
    n_dup_failed = int(dup_failed_mask.sum())
    if n_dup_failed:
        dup_error[dup_failed_mask] = weighted_choice(rng, dim.FAILURE_ERROR_DIST, n_dup_failed)

    dup_df = pd.DataFrame({
        "ts": dup_ts,
        "payer_bank": source["payer_bank"].to_numpy(),
        "payee_bank": source["payee_bank"].to_numpy(),
        "psp": source["psp"].to_numpy(),
        "amount": source["amount"].to_numpy(),
        "currency": "INR",
        "device_type": source["device_type"].to_numpy(),
        "os": source["os"].to_numpy(),
        "app_version": source["app_version"].to_numpy(),
        "network_type": source["network_type"].to_numpy(),
        "transaction_type": source["transaction_type"].to_numpy(),
        "geography": source["geography"].to_numpy(),
        "status": dup_status,
        "error_code": dup_error,
        "processing_time_ms": np.clip(rng.normal(900, 250, n_dupes), 80, None).astype(int),
        "retry_count": 0,
        "is_duplicate": True,
        "original_transaction_id": source["transaction_id"].to_numpy(),
        "transaction_id": rng_uuids(rng, n_dupes),
    })
    dup_df["error_category"] = dup_df["error_code"].map(dim.ERROR_CATEGORY_BY_CODE)

    return pd.concat([df, dup_df], ignore_index=True)


# Canonical column order -- must match data/generator/load_to_postgres.py COLUMNS
# and the transactions table definition in sql/migrations/001_init.sql.
FINAL_COLUMNS = [
    "transaction_id", "ts", "payer_bank", "payee_bank", "psp", "amount", "currency",
    "status", "error_code", "error_category", "device_type", "os", "app_version",
    "network_type", "transaction_type", "geography", "processing_time_ms",
    "retry_count", "is_eligible", "is_duplicate", "original_transaction_id", "created_at",
]


def finalize(df: pd.DataFrame) -> pd.DataFrame:
    """Applies the single, consistent eligibility rule (see docs/decisions.md D4)."""
    df["ts"] = pd.to_datetime(df["ts"])
    df["is_eligible"] = ~(
        (df["error_code"] == "USER_CANCELLED") | (df["is_duplicate"])
    )
    df = df.sort_values("ts").reset_index(drop=True)
    df["created_at"] = END_DATE
    return df[FINAL_COLUMNS]


def generate(seed: int, total_count: int) -> tuple[pd.DataFrame, dict]:
    rng = np.random.default_rng(seed)

    anomaly_n = max(200, int(total_count * dim.ANOMALY_SEGMENT_TXN_COUNT_FRACTION))
    base_n = total_count - anomaly_n

    base_df = build_base_population(rng, base_n)
    anomaly_df = build_anomaly_segment(rng, anomaly_n)
    df = pd.concat([base_df, anomaly_df], ignore_index=True)

    df = add_retries(rng, df)
    df = add_duplicates(rng, df)
    df = finalize(df)

    # Ground truth for RCA evaluation only (never consumed by the RCA engine).
    fp = dim.ANOMALY_FINGERPRINT
    window_mask = (
        (df["payer_bank"] == fp["payer_bank"])
        & (df["device_type"] == fp["device_type"])
        & (df["os"] == fp["os"])
        & (df["app_version"] == fp["app_version"])
        & (df["ts"].dt.date == END_DATE.date())
        & (df["ts"].dt.hour >= dim.ANOMALY_WINDOW_START_HOUR)
        & (df["ts"].dt.hour < dim.ANOMALY_WINDOW_END_HOUR)
    )
    segment = df[window_mask]
    segment_failed = segment[segment["status"] == "FAILED"]
    ground_truth = {
        "fingerprint": fp,
        "window": {
            "date": str(END_DATE.date()),
            "start_hour": dim.ANOMALY_WINDOW_START_HOUR,
            "end_hour": dim.ANOMALY_WINDOW_END_HOUR,
        },
        "segment_transaction_count": int(len(segment)),
        "segment_failed_count": int(len(segment_failed)),
        "segment_observed_failure_rate": round(len(segment_failed) / max(len(segment), 1), 4),
        "segment_value_at_risk": round(float(segment_failed["amount"].sum()), 2),
        "baseline_failure_rate": dim.BASELINE_FAILURE_RATE,
        "seed": seed,
        "total_transaction_count": int(len(df)),
    }
    return df, ground_truth


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--count", type=int, default=750_000)
    parser.add_argument("--out", type=str, default="transactions.csv")
    parser.add_argument("--ground-truth-out", type=str, default="ground_truth.json")
    args = parser.parse_args()

    df, ground_truth = generate(args.seed, args.count)

    out_path = Path(args.out)
    df.to_csv(out_path, index=False)

    gt_path = Path(args.ground_truth_out)
    gt_path.write_text(json.dumps(ground_truth, indent=2))

    overall_psr = (df.loc[df["is_eligible"], "status"] == "SUCCESS").mean() * 100
    print(f"Generated {len(df):,} rows -> {out_path}")
    print(f"Overall eligible PSR: {overall_psr:.2f}%")
    print(f"Injected anomaly segment: {ground_truth['segment_transaction_count']:,} txns, "
          f"observed failure rate {ground_truth['segment_observed_failure_rate']*100:.1f}% "
          f"(baseline {dim.BASELINE_FAILURE_RATE*100:.1f}%)")
    print(f"Ground truth written -> {gt_path}")


if __name__ == "__main__":
    main()
