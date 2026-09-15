"""
Bulk-loads a generated transactions CSV into PostgreSQL using COPY (far faster
than row-by-row inserts for hundreds of thousands of rows). Also records a
pipeline_runs row so /api/data-freshness has something real to report.

Usage:
    python load_to_postgres.py --csv /path/to/transactions.csv
"""

import argparse
import os
import time

import psycopg2

DATABASE_URL_PSYCOPG = os.environ.get(
    "DATABASE_URL_PSYCOPG",
    "postgresql://upi_fip:localtest@localhost:5432/upi_fip",
)

COLUMNS = [
    "transaction_id", "ts", "payer_bank", "payee_bank", "psp", "amount", "currency",
    "status", "error_code", "error_category", "device_type", "os", "app_version",
    "network_type", "transaction_type", "geography", "processing_time_ms",
    "retry_count", "is_eligible", "is_duplicate", "original_transaction_id", "created_at",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True)
    parser.add_argument("--truncate", action="store_true", help="Truncate transactions before loading")
    args = parser.parse_args()

    conn = psycopg2.connect(DATABASE_URL_PSYCOPG)
    conn.autocommit = False
    started = time.time()

    try:
        with conn.cursor() as cur:
            run_id = None
            cur.execute(
                "INSERT INTO pipeline_runs (status) VALUES ('running') RETURNING run_id"
            )
            run_id = cur.fetchone()[0]
            conn.commit()

            if args.truncate:
                cur.execute("TRUNCATE TABLE transactions RESTART IDENTITY CASCADE")

            column_list = ", ".join(COLUMNS)
            copy_sql = (
                f"COPY transactions ({column_list}) FROM STDIN "
                f"WITH (FORMAT csv, HEADER true, NULL '')"
            )
            with open(args.csv, "r") as f:
                cur.copy_expert(copy_sql, f)

            cur.execute("SELECT COUNT(*) FROM transactions")
            row_count = cur.fetchone()[0]

            cur.execute(
                """
                UPDATE pipeline_runs
                SET status = 'success', completed_at = now(), rows_processed = %s,
                    notes = %s
                WHERE run_id = %s
                """,
                (row_count, f"Loaded from {args.csv}", run_id),
            )
            conn.commit()

        elapsed = time.time() - started
        print(f"Loaded {row_count:,} rows into transactions in {elapsed:.1f}s")

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
