#!/bin/sh
# Backend container entrypoint.
#
# Goals (per the PRD's Section 23 "ideal local experience"):
#   docker compose up --build
#   -> open the app -> immediately explore seeded demo data, no manual steps.
#
# This script is idempotent: reference-data seeds use ON CONFLICT upserts,
# and the synthetic transaction generation step only runs if the
# transactions table doesn't already have a realistic volume of rows, so
# restarting the stack does not regenerate or reload the ~750K-row dataset
# every time.
set -e

echo "[entrypoint] Waiting for database..."
python <<'PY'
import os
import sys
import time

import psycopg2

url = os.environ["DATABASE_URL"].replace("postgresql+psycopg2", "postgresql")
for attempt in range(30):
    try:
        conn = psycopg2.connect(url)
        conn.close()
        break
    except Exception:
        time.sleep(1)
else:
    sys.exit("[entrypoint] Database not reachable after 30s")
print("[entrypoint] Database is up.")
PY

export DATABASE_URL_PSYCOPG=$(echo "$DATABASE_URL" | sed 's/postgresql+psycopg2/postgresql/')

echo "[entrypoint] Seeding reference data (error codes, demo users, demo experiment)..."
python /data/generator/seed_error_codes.py
python /data/generator/seed_users.py
python /data/generator/seed_experiment.py

echo "[entrypoint] Checking existing transaction volume..."
NEED_SEED=$(python <<'PY'
import os
import psycopg2

conn = psycopg2.connect(os.environ["DATABASE_URL_PSYCOPG"])
cur = conn.cursor()
cur.execute("SELECT count(*) FROM transactions")
count = cur.fetchone()[0]
print(f"[entrypoint] Existing transactions: {count}", file=__import__("sys").stderr)
print("1" if count < 100000 else "0")
PY
)

if [ "$NEED_SEED" = "1" ]; then
  echo "[entrypoint] Generating synthetic dataset (first boot only, ~20-30s)..."
  python /data/generator/generate_transactions.py \
    --seed "${SYNTHETIC_SEED:-42}" \
    --count "${SYNTHETIC_TRANSACTION_COUNT:-750000}" \
    --out /tmp/transactions.csv \
    --ground-truth-out /data/generator/ground_truth.json
  python /data/generator/load_to_postgres.py --csv /tmp/transactions.csv --truncate
  echo "[entrypoint] Synthetic dataset loaded."
else
  echo "[entrypoint] Transactions table already populated; skipping generation."
fi

echo "[entrypoint] Starting API server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
