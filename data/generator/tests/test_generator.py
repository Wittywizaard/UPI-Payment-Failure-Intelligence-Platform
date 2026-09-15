"""
Run with: pytest data/generator/tests/test_generator.py -v

Uses small transaction counts for speed; determinism and data-quality
invariants hold regardless of scale.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import pytest

from generate_transactions import generate, dim


SMALL_N = 15_000


@pytest.fixture(scope="module")
def small_dataset():
    df, ground_truth = generate(seed=7, total_count=SMALL_N)
    return df, ground_truth


class TestDeterminism:
    def test_same_seed_produces_identical_data(self):
        df1, gt1 = generate(seed=99, total_count=SMALL_N)
        df2, gt2 = generate(seed=99, total_count=SMALL_N)
        pd.testing.assert_frame_equal(df1, df2)
        assert gt1 == gt2

    def test_different_seed_produces_different_data(self):
        df1, _ = generate(seed=1, total_count=SMALL_N)
        df2, _ = generate(seed=2, total_count=SMALL_N)
        assert not df1["transaction_id"].equals(df2["transaction_id"])


class TestDataQuality:
    def test_no_null_required_fields(self, small_dataset):
        df, _ = small_dataset
        required = ["transaction_id", "ts", "payer_bank", "payee_bank", "psp",
                    "amount", "status", "device_type", "os", "app_version"]
        for col in required:
            assert df[col].isna().sum() == 0, f"{col} has nulls"

    def test_status_values_valid(self, small_dataset):
        df, _ = small_dataset
        assert set(df["status"].unique()) <= {"SUCCESS", "FAILED", "PENDING"}

    def test_failed_rows_have_error_code(self, small_dataset):
        df, _ = small_dataset
        failed = df[df["status"] == "FAILED"]
        assert failed["error_code"].isna().sum() == 0

    def test_non_failed_rows_have_no_error_code(self, small_dataset):
        df, _ = small_dataset
        non_failed = df[df["status"] != "FAILED"]
        assert non_failed["error_code"].isna().all()

    def test_amounts_positive_and_bounded(self, small_dataset):
        df, _ = small_dataset
        assert (df["amount"] > 0).all()
        assert (df["amount"] <= 200_000).all()

    def test_timestamps_within_expected_window(self, small_dataset):
        df, _ = small_dataset
        assert df["ts"].min().date().isoformat() >= "2026-08-16"
        assert df["ts"].max().date().isoformat() <= "2026-08-29"

    def test_no_duplicate_transaction_ids(self, small_dataset):
        df, _ = small_dataset
        assert df["transaction_id"].is_unique

    def test_eligibility_rule_consistent(self, small_dataset):
        df, _ = small_dataset
        # Per docs/decisions.md D4: ineligible iff USER_CANCELLED or duplicate.
        expected_ineligible = (df["error_code"] == "USER_CANCELLED") | (df["is_duplicate"])
        assert (df["is_eligible"] == ~expected_ineligible).all()

    def test_retry_links_point_to_real_transactions(self, small_dataset):
        df, _ = small_dataset
        linked = df[df["original_transaction_id"].notna()]
        valid_ids = set(df["transaction_id"])
        assert linked["original_transaction_id"].isin(valid_ids).all()


class TestAnomalyInjection:
    def test_anomaly_segment_has_meaningful_volume(self, small_dataset):
        _, gt = small_dataset
        assert gt["segment_transaction_count"] > 50

    def test_anomaly_failure_rate_exceeds_baseline_substantially(self, small_dataset):
        _, gt = small_dataset
        assert gt["segment_observed_failure_rate"] > gt["baseline_failure_rate"] * 3

    def test_anomaly_confined_to_injected_dimensions(self, small_dataset):
        df, gt = small_dataset
        fp = gt["fingerprint"]
        window = gt["window"]
        segment = df[
            (df["payer_bank"] == fp["payer_bank"])
            & (df["device_type"] == fp["device_type"])
            & (df["os"] == fp["os"])
            & (df["app_version"] == fp["app_version"])
            & (df["ts"].dt.date.astype(str) == window["date"])
            & (df["ts"].dt.hour >= window["start_hour"])
            & (df["ts"].dt.hour < window["end_hour"])
        ]
        assert len(segment) == gt["segment_transaction_count"]

        # A neighbouring hour outside the window should look like baseline, not anomalous.
        outside = df[
            (df["payer_bank"] == fp["payer_bank"])
            & (df["device_type"] == fp["device_type"])
            & (df["os"] == fp["os"])
            & (df["app_version"] == fp["app_version"])
            & (df["ts"].dt.date.astype(str) == window["date"])
            & (df["ts"].dt.hour == window["end_hour"] + 2)
        ]
        if len(outside) > 20:
            outside_failure_rate = (outside["status"] == "FAILED").mean()
            assert outside_failure_rate < gt["segment_observed_failure_rate"] * 0.5
