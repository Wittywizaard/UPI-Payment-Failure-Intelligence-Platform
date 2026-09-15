"""
Exercises the full demo-scenario workflow (PRD Section 24) against the real
app + live database via FastAPI's TestClient: login -> RCA -> create incident
-> lifecycle transitions -> create intervention -> measure real before/after
impact -> confirm linkage and audit timeline. No step is mocked.

Also covers auth/RBAC: unauthenticated requests are rejected, and viewers
cannot perform write actions reserved for pm/ops/engineer/admin.
"""

import pytest
from sqlalchemy import create_engine, text

from app.main import settings

ANOMALY_START = "2026-08-29T18:00:00"
ANOMALY_END = "2026-08-29T20:00:00"


@pytest.fixture(scope="module", autouse=True)
def _ensure_seeded_dataset():
    engine = create_engine(settings.DATABASE_URL)
    with engine.connect() as conn:
        count = conn.execute(text("SELECT count(*) FROM transactions")).scalar()
    if count < 100_000:
        pytest.skip("transactions table not seeded; run the Phase 2 generator + loader first")


def _create_incident(client, pm_headers, severity="P1"):
    payload = {"title": "Test incident", "severity": severity, "detected_at": ANOMALY_START}
    return client.post("/api/incidents", json=payload, headers=pm_headers).json()


class TestAuthAndRBAC:
    def test_unauthenticated_request_rejected(self, client):
        resp = client.get("/api/dashboard")
        assert resp.status_code == 401
        assert resp.json()["detail"]["error"]["code"] == "UNAUTHORIZED"

    def test_invalid_token_rejected(self, client):
        resp = client.get("/api/dashboard", headers={"Authorization": "Bearer not-a-real-token"})
        assert resp.status_code == 401

    def test_viewer_can_read_but_not_write(self, client, viewer_headers, pm_headers):
        read_resp = client.get("/api/dashboard", headers=viewer_headers)
        assert read_resp.status_code == 200

        write_resp = client.post(
            "/api/incidents",
            json={"title": "x", "severity": "P1", "detected_at": ANOMALY_START},
            headers=viewer_headers,
        )
        assert write_resp.status_code == 403
        assert write_resp.json()["detail"]["error"]["code"] == "FORBIDDEN"

    def test_pm_can_write(self, client, pm_headers):
        incident = _create_incident(client, pm_headers)
        assert "incident_id" in incident

    def test_wrong_password_rejected(self, client):
        resp = client.post("/api/auth/login", json={"email": "pm@upi-fip.dev", "password": "wrong"})
        assert resp.status_code == 401
        assert resp.json()["detail"]["error"]["code"] == "INVALID_CREDENTIALS"

    def test_audit_log_attributes_authenticated_user(self, client, pm_headers):
        incident = _create_incident(client, pm_headers)
        note_action = [t for t in incident["timeline"] if t["action"] == "incident.created"][0]
        assert note_action["metadata_json"]["actor"] == "pm@upi-fip.dev"


class TestIncidentLifecycle:
    def test_create_incident_from_rca_output(self, client, pm_headers):
        rca_resp = client.get(f"/api/rca/ad-hoc?start={ANOMALY_START}&end={ANOMALY_END}", headers=pm_headers)
        assert rca_resp.status_code == 200
        rca = rca_resp.json()
        assert rca["severity"] == "P0"

        payload = {
            "title": "P0 - Payment Success Rate Drop",
            "severity": rca["severity"],
            "detected_at": ANOMALY_START,
            "affected_fingerprint": rca["fingerprint"]["dimensions"],
            "estimated_value_at_risk": rca["value_at_risk"],
            "affected_transactions": rca["affected_transactions"],
            "observed_psr": rca["observed_psr"],
            "baseline_psr": rca["baseline_psr"],
        }
        create_resp = client.post("/api/incidents", json=payload, headers=pm_headers)
        assert create_resp.status_code == 201
        incident = create_resp.json()
        assert incident["status"] == "open"
        assert incident["severity"] == "P0"
        assert incident["affected_fingerprint"]["payer_bank"] == "BANK_A"

    def test_valid_status_transition_succeeds(self, client, pm_headers):
        incident = _create_incident(client, pm_headers)
        resp = client.patch(f"/api/incidents/{incident['incident_id']}",
                             json={"status": "investigating"}, headers=pm_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "investigating"

    def test_invalid_status_transition_rejected(self, client, pm_headers):
        incident = _create_incident(client, pm_headers)
        resp = client.patch(f"/api/incidents/{incident['incident_id']}",
                             json={"status": "resolved"}, headers=pm_headers)
        assert resp.status_code == 400
        assert resp.json()["detail"]["error"]["code"] == "INVALID_TRANSITION"

    def test_note_added_to_timeline(self, client, pm_headers):
        incident = _create_incident(client, pm_headers)
        client.patch(f"/api/incidents/{incident['incident_id']}",
                      json={"note": "Escalated to bank team"}, headers=pm_headers)
        detail = client.get(f"/api/incidents/{incident['incident_id']}", headers=pm_headers).json()
        notes = [t for t in detail["timeline"] if t["action"] == "incident.note_added"]
        assert len(notes) == 1
        assert notes[0]["metadata_json"]["note"] == "Escalated to bank team"

    def test_nonexistent_incident_returns_404(self, client, pm_headers):
        resp = client.get("/api/incidents/00000000-0000-0000-0000-000000000000", headers=pm_headers)
        assert resp.status_code == 404


class TestInterventionLifecycle:
    def test_create_intervention_and_measure_real_impact(self, client, pm_headers):
        incident = _create_incident(client, pm_headers)
        client.patch(f"/api/incidents/{incident['incident_id']}",
                      json={"status": "investigating"}, headers=pm_headers)

        intervention_payload = {
            "incident_id": incident["incident_id"],
            "type": "contextual_recovery_prompt",
            "hypothesis": "Test hypothesis",
            "start_time": ANOMALY_END,
        }
        intervention_resp = client.post("/api/interventions", json=intervention_payload, headers=pm_headers)
        assert intervention_resp.status_code == 201
        intervention = intervention_resp.json()
        assert intervention["status"] == "proposed"

        impact_resp = client.post(
            f"/api/interventions/{intervention['intervention_id']}/measure-impact",
            json={
                "before_start": ANOMALY_START, "before_end": ANOMALY_END,
                "after_start": ANOMALY_END, "after_end": "2026-08-29T22:00:00",
                "filters": {"payer_bank": "BANK_A", "device_type": "Android", "os": "U28", "app_version": "4.2.1"},
            },
            headers=pm_headers,
        )
        assert impact_resp.status_code == 200
        impact = impact_resp.json()
        assert impact["after"]["psr"] > impact["before"]["psr"]
        assert impact["before"]["psr"] == pytest.approx(58.28, abs=1.0)

    def test_incident_detail_shows_linked_intervention(self, client, pm_headers):
        incident = _create_incident(client, pm_headers)
        intervention_resp = client.post("/api/interventions", json={
            "incident_id": incident["incident_id"], "type": "test_type", "hypothesis": "h",
        }, headers=pm_headers)
        intervention_id = intervention_resp.json()["intervention_id"]

        detail = client.get(f"/api/incidents/{incident['incident_id']}", headers=pm_headers).json()
        linked_ids = [i["intervention_id"] for i in detail["interventions"]]
        assert intervention_id in linked_ids

    def test_intervention_for_nonexistent_incident_rejected(self, client, pm_headers):
        resp = client.post("/api/interventions", json={
            "incident_id": "00000000-0000-0000-0000-000000000000",
            "type": "x", "hypothesis": "h",
        }, headers=pm_headers)
        assert resp.status_code == 404

    def test_viewer_cannot_create_intervention(self, client, pm_headers, viewer_headers):
        incident = _create_incident(client, pm_headers)
        resp = client.post("/api/interventions", json={
            "incident_id": incident["incident_id"], "type": "x", "hypothesis": "h",
        }, headers=viewer_headers)
        assert resp.status_code == 403

    def test_list_interventions_filters_by_incident(self, client, pm_headers):
        incident = _create_incident(client, pm_headers)
        client.post("/api/interventions", json={
            "incident_id": incident["incident_id"], "type": "test_type", "hypothesis": "h",
        }, headers=pm_headers)

        resp = client.get(f"/api/interventions?incident_id={incident['incident_id']}", headers=pm_headers)
        assert resp.status_code == 200
        interventions = resp.json()["interventions"]
        assert len(interventions) == 1
        assert interventions[0]["incident_id"] == incident["incident_id"]


class TestExperiments:
    def test_seeded_demo_experiment_exists(self, client, pm_headers):
        resp = client.get("/api/experiments", headers=pm_headers)
        assert resp.status_code == 200
        experiments = resp.json()["experiments"]
        names = [e["name"] for e in experiments]
        assert "Contextual Recovery Experience" in names

    def test_experiment_marked_simulated(self, client, pm_headers):
        resp = client.get("/api/experiments", headers=pm_headers)
        experiments = resp.json()["experiments"]
        demo = next(e for e in experiments if e["name"] == "Contextual Recovery Experience")
        assert demo["is_simulated"] is True
        assert demo["result_summary"]["status"] == "SIMULATED / PORTFOLIO DATA"

    def test_viewer_cannot_create_experiment(self, client, viewer_headers):
        resp = client.post("/api/experiments", json={
            "name": "x", "hypothesis": "h", "control_definition": "c",
            "variant_definition": "v", "primary_metric": "m",
        }, headers=viewer_headers)
        assert resp.status_code == 403
