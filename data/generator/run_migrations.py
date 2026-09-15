"""
Minimal migration runner. Not a replacement for Alembic -- a deliberately
small tool matching this project's "simplest robust solution" philosophy
(see docs/decisions.md D44) that solves one specific problem: a numbered SQL
file added to sql/migrations/ after a database volume already exists (like
002_observability.sql, added after 001_init.sql was already applied to every
developer's and every reviewer's existing local database) needs to be
applied without re-running 001 and hitting "relation already exists".

Tracks applied filenames in a schema_migrations table. Safe to run on every
container boot: already-applied files are skipped; the file that created
schema_migrations itself is bootstrapped separately and idempotently.

Usage:
    python run_migrations.py --migrations-dir /sql/migrations
"""

import argparse
import os
from pathlib import Path

import psycopg2

DATABASE_URL_PSYCOPG = os.environ.get(
    "DATABASE_URL_PSYCOPG",
    "postgresql://upi_fip:localtest@localhost:5432/upi_fip",
)

BOOTSTRAP_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    filename    TEXT PRIMARY KEY,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--migrations-dir", default="/sql/migrations")
    args = parser.parse_args()

    conn = psycopg2.connect(DATABASE_URL_PSYCOPG)
    conn.autocommit = False

    try:
        with conn.cursor() as cur:
            cur.execute(BOOTSTRAP_SQL)
        conn.commit()

        with conn.cursor() as cur:
            cur.execute("SELECT filename FROM schema_migrations")
            already_applied = {row[0] for row in cur.fetchall()}

        migration_files = sorted(Path(args.migrations_dir).glob("*.sql"))
        pending = [f for f in migration_files if f.name not in already_applied]

        if not pending:
            print(f"[migrations] Up to date ({len(already_applied)} already applied).")
            return

        for path in pending:
            print(f"[migrations] Applying {path.name}...")
            sql = path.read_text()
            with conn.cursor() as cur:
                cur.execute(sql)
                cur.execute(
                    "INSERT INTO schema_migrations (filename) VALUES (%s)",
                    (path.name,),
                )
            conn.commit()
            print(f"[migrations] Applied {path.name}.")

        print(f"[migrations] Done. Applied {len(pending)} new migration(s).")

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
