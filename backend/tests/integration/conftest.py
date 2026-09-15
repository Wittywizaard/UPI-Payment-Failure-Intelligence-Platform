import os

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://upi_fip:localtest@localhost:5432/upi_fip")
os.environ.setdefault("JWT_SECRET", "test-secret-for-integration-tests")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")

import pytest
from fastapi.testclient import TestClient

from app.main import app

DEMO_PASSWORD = "Demo123!"


@pytest.fixture(scope="session")
def client():
    return TestClient(app)


def _login(client: TestClient, email: str) -> dict:
    resp = client.post("/api/auth/login", json={"email": email, "password": DEMO_PASSWORD})
    if resp.status_code != 200:
        pytest.skip(f"Could not log in as {email}; run `python data/generator/seed_users.py` first")
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def pm_headers(client):
    return _login(client, "pm@upi-fip.dev")


@pytest.fixture(scope="session")
def viewer_headers(client):
    return _login(client, "viewer@upi-fip.dev")


@pytest.fixture(scope="session")
def admin_headers(client):
    return _login(client, "admin@upi-fip.dev")
