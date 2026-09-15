"""
Seeds one demo user per RBAC role for local development and the portfolio
demo. All accounts share the same demo password so the reviewer only needs
to remember one credential; this is explicitly a local/demo convenience, not
a production pattern (see docs/decisions.md D25).

Usage:
    python seed_users.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

import psycopg2
from passlib.context import CryptContext

DATABASE_URL_PSYCOPG = os.environ.get(
    "DATABASE_URL_PSYCOPG",
    "postgresql://upi_fip:localtest@localhost:5432/upi_fip",
)

DEMO_PASSWORD = "Demo123!"
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

DEMO_USERS = [
    ("admin@upi-fip.dev", "Aisha Admin", "admin"),
    ("pm@upi-fip.dev", "Priya PM", "pm"),
    ("ops@upi-fip.dev", "Omar Ops", "ops"),
    ("engineer@upi-fip.dev", "Elena Engineer", "engineer"),
    ("support@upi-fip.dev", "Sam Support", "support"),
    ("viewer@upi-fip.dev", "Vikram Viewer", "viewer"),
]


def main() -> None:
    password_hash = pwd_context.hash(DEMO_PASSWORD)
    conn = psycopg2.connect(DATABASE_URL_PSYCOPG)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO users (email, password_hash, display_name, role, is_active, created_at, updated_at)
            VALUES (%s, %s, %s, %s, TRUE, now(), now())
            ON CONFLICT (email) DO UPDATE SET
                password_hash = EXCLUDED.password_hash,
                display_name = EXCLUDED.display_name,
                role = EXCLUDED.role
            """,
            [(email, password_hash, name, role) for email, name, role in DEMO_USERS],
        )
    print(f"Seeded {len(DEMO_USERS)} demo users. Password for all: {DEMO_PASSWORD}")
    conn.close()


if __name__ == "__main__":
    main()
