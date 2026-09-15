"""
Seeds the one demo experiment described in the PRD (Section 23): the
intelligent-recovery-experience hypothesis. Simulated results only --
labeled is_simulated=TRUE, per the portfolio disclaimer.

Usage:
    python seed_experiment.py
"""

import json
import os

import psycopg2

DATABASE_URL_PSYCOPG = os.environ.get(
    "DATABASE_URL_PSYCOPG",
    "postgresql://upi_fip:localtest@localhost:5432/upi_fip",
)


def main() -> None:
    conn = psycopg2.connect(DATABASE_URL_PSYCOPG)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO experiments
                (name, hypothesis, control_definition, variant_definition, primary_metric,
                 secondary_metrics, guardrails, sample_size, result_summary, is_simulated)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
            """,
            (
                "Contextual Recovery Experience",
                "An intelligent recovery experience after eligible payment failures will increase "
                "successful completion without increasing duplicate transactions.",
                "Generic payment failed message.",
                "Contextual recovery/retry experience.",
                "Recovery Rate",
                json.dumps(["PSR", "Retry Rate", "Abandonment", "Time to Successful Payment"]),
                json.dumps(["Duplicate Transaction Rate"]),
                24000,
                json.dumps({
                    "status": "SIMULATED / PORTFOLIO DATA",
                    "recovery_rate_control_pct": 18.4,
                    "recovery_rate_variant_pct": 27.8,
                    "psr_control_pct": 94.2,
                    "psr_variant_pct": 96.1,
                    "duplicate_rate_control_pct": 0.12,
                    "duplicate_rate_variant_pct": 0.13,
                    "guardrail_status": "within_threshold",
                    "conclusion": "Variant improved recovery rate by +9.4pp without a material "
                                  "increase in duplicate transactions.",
                }),
            ),
        )
    print("Seeded 1 demo experiment.")
    conn.close()


if __name__ == "__main__":
    main()
