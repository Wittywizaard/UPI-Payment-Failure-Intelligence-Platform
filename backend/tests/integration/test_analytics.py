"""
Integration tests -- run against a live PostgreSQL instance seeded with the
Phase 2 synthetic dataset (750K+ rows, injected BANK_A x Android x U28 x
v4.2.1 x 18:00-20:00 anomaly). These are intentionally NOT unit tests with
mocked data: they validate the analytics engine against the real, generated
dataset the way the RCA-evaluation section of the PRD (Section 21) requires.

Run with:
    DATABASE_URL_TEST=postgresql+psycopg2://upi_fip:localtest@localhost:5432/upi_fip \
    pytest tests/integration/test_analytics.py -v
"""

import datetime
import os

import pandas as pd
import pytest
from sqlalchemy import create_engine, text

from app.analytics.anomaly import detect_anomaly
from app.analytics.fingerprint import run_fingerprint_scan
from app.analytics.metrics import compute_core_metrics
from app.analytics.rca import run_rca

DATABASE_URL_TEST = os.environ.get(
    "DATABASE_URL_TEST",
    "postgresql+psycopg2://upi_fip:localtest@localhost:5432/upi_fip",
)

ANOMALY_WINDOW_START = datetime.datetime(2026, 8, 29, 18, 0, 0)
ANOMALY_WINDOW_END = datetime.datetime(2026, 8, 29, 20, 0, 0)
QUIET_WINDOW_START = datetime.datetime(2026, 8, 26, 18, 0, 0)
QUIET_WINDOW_END = datetime.datetime(2026, 8, 26, 20, 0, 0)


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(DATABASE_URL_TEST)
    with eng.connect() as conn:
        count = conn.execute(text("SELECT count(*) FROM transactions")).scalar()
    if count < 100_000:
        pytest.skip(f"transactions table has only {count} rows; run the Phase 2 generator + loader first")
    return eng


class TestMetricsEngine:
    def test_psr_matches_independent_pandas_calculation(self, engine):
        with engine.connect() as conn:
            df = pd.read_sql(
                text("SELECT status, is_eligible FROM transactions "
                     "WHERE ts >= :s AND ts < :e"),
                conn, params={"s": ANOMALY_WINDOW_START, "e": ANOMALY_WINDOW_END},
            )
        eligible = df[df["is_eligible"]]
        expected_psr = round(100.0 * (eligible["status"] == "SUCCESS").mean(), 2)

        result = compute_core_metrics(engine, {
            "start_date": ANOMALY_WINDOW_START, "end_date": ANOMALY_WINDOW_END,
        })
        assert result["psr"] == pytest.approx(expected_psr, abs=0.01)

    def test_failure_rate_is_complement_of_psr_minus_pending(self, engine):
        """
        PSR + Failure Rate is only exactly 100% if every eligible transaction
        resolves to SUCCESS or FAILED. Eligible PENDING transactions (a small,
        intentional share of the synthetic dataset -- see dimensions.PENDING_RATE)
        are correctly included in the eligible denominator but excluded from
        both numerators, so a small gap versus 100% is expected and correct.
        """
        result = compute_core_metrics(engine, {})
        assert result["psr"] + result["failure_rate"] == pytest.approx(100.0, abs=0.5)
        assert result["psr"] + result["failure_rate"] <= 100.0

    def test_value_at_risk_is_positive_during_anomaly_window(self, engine):
        result = compute_core_metrics(engine, {
            "payer_bank": "BANK_A", "device_type": "Android", "os": "U28", "app_version": "4.2.1",
            "start_date": ANOMALY_WINDOW_START, "end_date": ANOMALY_WINDOW_END,
        })
        assert result["value_at_risk"] > 1_000_000

    def test_anomaly_segment_psr_much_lower_than_overall(self, engine):
        overall = compute_core_metrics(engine, {})
        segment = compute_core_metrics(engine, {
            "payer_bank": "BANK_A", "device_type": "Android", "os": "U28", "app_version": "4.2.1",
            "start_date": ANOMALY_WINDOW_START, "end_date": ANOMALY_WINDOW_END,
        })
        assert segment["psr"] < overall["psr"] - 20


class TestAnomalyDetection:
    def test_detects_true_positive_in_injected_window(self, engine):
        result = detect_anomaly(engine, ANOMALY_WINDOW_START, ANOMALY_WINDOW_END, baseline_days=7)
        assert result["is_anomaly"] is True
        assert result["severity"] in {"P0", "P1", "P2"}
        assert result["baseline_psr"] - result["observed_psr"] >= 2.0

    def test_no_false_positive_in_quiet_window(self, engine):
        result = detect_anomaly(engine, QUIET_WINDOW_START, QUIET_WINDOW_END, baseline_days=7)
        assert result["is_anomaly"] is False


class TestFingerprintEngine:
    def test_finds_injected_fingerprint_as_top_result(self, engine):
        results = run_fingerprint_scan(engine, ANOMALY_WINDOW_START, ANOMALY_WINDOW_END, baseline_days=7)
        assert len(results) > 0
        top = results[0]
        assert top["dimensions"].get("payer_bank") == "BANK_A"
        assert top["dimensions"].get("os") == "U28"
        assert top["dimensions"].get("app_version") == "4.2.1"

    def test_no_nested_duplicate_fingerprints(self, engine):
        """
        The dedup contract (docs/decisions.md D14) is: a broader fingerprint is
        only dropped if a strictly more specific one already explains AT LEAST
        as much. A broader segment is allowed to survive alongside a narrower
        one if it independently explains MORE incremental failure (e.g. a
        network-wide WIFI issue can coexist with a bank-specific finding even
        though 'WIFI' and 'BANK_A x WIFI' overlap) -- that is a legitimate
        second finding, not redundancy.
        """
        results = run_fingerprint_scan(engine, ANOMALY_WINDOW_START, ANOMALY_WINDOW_END, baseline_days=7)
        for a in results:
            for b in results:
                if a is b:
                    continue
                a_dims = set(a["dimensions"].items())
                b_dims = set(b["dimensions"].items())
                if a_dims < b_dims:  # a is a strict subset of b (a is broader)
                    assert a["contribution_pct"] > b["contribution_pct"], (
                        f"{a['label']} is a redundant broader version of {b['label']} "
                        f"but wasn't dropped despite not adding explanatory value"
                    )

    def test_quiet_window_returns_no_or_few_fingerprints(self, engine):
        results = run_fingerprint_scan(engine, QUIET_WINDOW_START, QUIET_WINDOW_END, baseline_days=7)
        assert len(results) == 0


class TestRCAEngine:
    def test_full_pipeline_matches_ground_truth_fingerprint(self, engine):
        rca = run_rca(engine, ANOMALY_WINDOW_START, ANOMALY_WINDOW_END, baseline_days=7)
        assert rca["anomaly"] is True
        assert rca["severity"] == "P0"
        assert rca["fingerprint"]["dimensions"]["payer_bank"] == "BANK_A"
        assert rca["fingerprint"]["dimensions"]["app_version"] == "4.2.1"
        assert "probable contributor" in rca["ai_summary"]
        assert "not confirmed causal evidence" in rca["ai_summary"]
        assert len(rca["recommended_actions"]) >= 2

    def test_no_causal_language_in_summary(self, engine):
        rca = run_rca(engine, ANOMALY_WINDOW_START, ANOMALY_WINDOW_END, baseline_days=7)
        forbidden_phrases = ["confirmed root cause", "caused by", "definitely caused"]
        for phrase in forbidden_phrases:
            assert phrase not in rca["ai_summary"].lower()

    def test_quiet_window_produces_no_anomaly_rca(self, engine):
        rca = run_rca(engine, QUIET_WINDOW_START, QUIET_WINDOW_END, baseline_days=7)
        assert rca["anomaly"] is False
        assert rca["fingerprint"] is None
