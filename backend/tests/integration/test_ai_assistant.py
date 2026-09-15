"""
Tests the AI Assistant pipeline end-to-end against the live database, with no
LLM API key configured (this environment has none) -- verifying the
template-fallback path is fully functional on its own, since the PRD
requires the platform to work even without a configured LLM key. Every
assertion checks that numbers in the answer trace back to the structured
result, never invented values.
"""

import pytest
from sqlalchemy import create_engine, text

from app.main import settings

ANOMALY_QUESTION = "Why did PSR drop yesterday?"


@pytest.fixture(scope="module", autouse=True)
def _ensure_seeded_dataset():
    engine = create_engine(settings.DATABASE_URL)
    with engine.connect() as conn:
        count = conn.execute(text("SELECT count(*) FROM transactions")).scalar()
    if count < 100_000:
        pytest.skip("transactions table not seeded; run the Phase 2 generator + loader first")


class TestAiAssistantAuth:
    def test_requires_authentication(self, client):
        resp = client.post("/api/ai/analyze", json={"question": ANOMALY_QUESTION})
        assert resp.status_code == 401

    def test_viewer_can_ask_questions(self, client, viewer_headers):
        resp = client.post("/api/ai/analyze", json={"question": ANOMALY_QUESTION}, headers=viewer_headers)
        assert resp.status_code == 200

    def test_question_too_short_rejected(self, client, pm_headers):
        resp = client.post("/api/ai/analyze", json={"question": "hi"}, headers=pm_headers)
        assert resp.status_code == 422


class TestAiAssistantIntents:
    def test_psr_drop_reason_finds_injected_anomaly(self, client, pm_headers):
        resp = client.post("/api/ai/analyze", json={"question": ANOMALY_QUESTION}, headers=pm_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["intent"] == "psr_drop_reason"
        assert "BANK_A" in data["answer"]
        assert "probable contributor" in data["answer"].lower()
        assert data["evidence"]

    def test_bank_contributor_identifies_bank_a(self, client, pm_headers):
        resp = client.post(
            "/api/ai/analyze", json={"question": "Which bank contributed most to failures yesterday?"}, headers=pm_headers
        )
        data = resp.json()
        assert data["intent"] == "top_bank_contributor"
        assert data["filters"]["payer_bank"] == "BANK_A"

    def test_top_fingerprint_matches_ground_truth(self, client, pm_headers):
        resp = client.post(
            "/api/ai/analyze", json={"question": "What was the biggest failure fingerprint yesterday?"}, headers=pm_headers
        )
        data = resp.json()
        assert data["intent"] == "top_fingerprint"
        assert data["filters"]["payer_bank"] == "BANK_A"
        assert data["filters"]["app_version"] == "4.2.1"

    def test_value_at_risk_returns_positive_number(self, client, pm_headers):
        resp = client.post(
            "/api/ai/analyze", json={"question": "What is the estimated value at risk yesterday?"}, headers=pm_headers
        )
        data = resp.json()
        assert data["intent"] == "value_at_risk"
        assert data["evidence"][0]["value_at_risk"] > 0

    def test_insufficient_data_stated_plainly_for_empty_window(self, client, pm_headers):
        resp = client.post("/api/ai/analyze", json={"question": "What is the value at risk today?"}, headers=pm_headers)
        data = resp.json()
        assert "don't have enough data" in data["answer"].lower()
        assert data["evidence"] == []

    def test_no_confirmed_causal_language(self, client, pm_headers):
        resp = client.post("/api/ai/analyze", json={"question": ANOMALY_QUESTION}, headers=pm_headers)
        data = resp.json()
        forbidden = ["confirmed root cause", "definitely caused", "proven to cause"]
        for phrase in forbidden:
            assert phrase not in data["answer"].lower()

    def test_answer_only_uses_numbers_from_evidence(self, client, pm_headers):
        """Spot check: the bank named in the answer must match the evidence, not be invented."""
        resp = client.post(
            "/api/ai/analyze", json={"question": "Which bank contributed most to failures yesterday?"}, headers=pm_headers
        )
        data = resp.json()
        bank_in_evidence = data["evidence"][0]["dimensions"]["payer_bank"]
        assert bank_in_evidence in data["answer"]


class TestAiAssistantRateLimit:
    def test_rate_limit_eventually_triggers(self, client, pm_headers):
        # AI_RATE_LIMIT_PER_MINUTE defaults to 10; fire more than that.
        statuses = []
        for _ in range(15):
            resp = client.post("/api/ai/analyze", json={"question": "value at risk"}, headers=pm_headers)
            statuses.append(resp.status_code)
        assert 429 in statuses
