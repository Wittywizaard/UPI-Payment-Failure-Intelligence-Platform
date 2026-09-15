"""
Tests the observability endpoint (PRD Section 22) against real, measured
request-log data -- generates real traffic across several endpoint groups
first, then asserts the aggregation reflects it. Nothing here is mocked:
the latency and error-rate numbers are whatever the live system actually
measured for these specific test requests.
"""

import pytest
from sqlalchemy import create_engine, text

from app.main import settings


@pytest.fixture(scope="module", autouse=True)
def _ensure_seeded_dataset():
    engine = create_engine(settings.DATABASE_URL)
    with engine.connect() as conn:
        count = conn.execute(text("SELECT count(*) FROM transactions")).scalar()
        has_table = conn.execute(text("SELECT to_regclass('public.api_request_logs')")).scalar()
    if count < 100_000:
        pytest.skip("transactions table not seeded; run the Phase 2 generator + loader first")
    if not has_table:
        pytest.skip("api_request_logs table missing; run sql/migrations/002_observability.sql first")


class TestObservabilityRBAC:
    def test_requires_authentication(self, client):
        resp = client.get("/api/observability")
        assert resp.status_code == 401

    def test_pm_forbidden(self, client, pm_headers):
        resp = client.get("/api/observability", headers=pm_headers)
        assert resp.status_code == 403

    def test_viewer_forbidden(self, client, viewer_headers):
        resp = client.get("/api/observability", headers=viewer_headers)
        assert resp.status_code == 403

    def test_admin_allowed(self, client, admin_headers):
        resp = client.get("/api/observability", headers=admin_headers)
        assert resp.status_code == 200


class TestObservabilityMetrics:
    def test_real_traffic_is_reflected_in_aggregates(self, client, admin_headers):
        client.get("/api/dashboard", headers=admin_headers)
        client.get("/api/experiments", headers=admin_headers)

        resp = client.get("/api/observability?window_minutes=5", headers=admin_headers)
        data = resp.json()

        assert data["api"]["total_requests"] >= 2
        assert data["api"]["avg_latency_ms"] > 0
        feature_names = {f["feature"] for f in data["api"]["by_feature"]}
        assert "dashboard" in feature_names
        assert "experiments" in feature_names

    def test_rca_and_ai_appear_as_distinct_feature_groups(self, client, admin_headers):
        client.get(
            "/api/rca/ad-hoc?start=2026-08-29T18:00:00&end=2026-08-29T20:00:00",
            headers=admin_headers,
        )
        client.post("/api/ai/analyze", json={"question": "value at risk"}, headers=admin_headers)

        resp = client.get("/api/observability?window_minutes=5", headers=admin_headers)
        data = resp.json()
        feature_names = {f["feature"] for f in data["api"]["by_feature"]}
        assert "rca_generation" in feature_names
        assert "ai_assistant" in feature_names

    def test_database_query_stats_present_and_nonzero(self, client, admin_headers):
        resp = client.get("/api/observability", headers=admin_headers)
        data = resp.json()
        assert data["database"]["total_queries_since_startup"] > 0
        assert data["database"]["avg_query_ms"] is not None

    def test_pipeline_runs_included(self, client, admin_headers):
        resp = client.get("/api/observability", headers=admin_headers)
        data = resp.json()
        assert len(data["pipeline_runs"]) > 0
        assert data["pipeline_runs"][0]["status"] in {"success", "failed", "running"}

    def test_health_and_freshness_endpoints_excluded_from_logs(self, client, admin_headers):
        engine = create_engine(settings.DATABASE_URL)
        with engine.connect() as conn:
            before = conn.execute(
                text("SELECT count(*) FROM api_request_logs WHERE path = '/api/health'")
            ).scalar()

        client.get("/api/health")
        client.get("/api/health")

        with engine.connect() as conn:
            after = conn.execute(
                text("SELECT count(*) FROM api_request_logs WHERE path = '/api/health'")
            ).scalar()

        assert after == before  # excluded per docs/decisions.md D45
