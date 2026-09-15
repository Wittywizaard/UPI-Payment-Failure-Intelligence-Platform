"""
Seeds the error_codes reference table from the failure taxonomy defined in the
PRD (Section 13). Run once before generating synthetic transactions, since
transactions.error_code has a FK to this table.

Usage:
    python seed_error_codes.py
"""

import os

import psycopg2

DATABASE_URL_PSYCOPG = os.environ.get(
    "DATABASE_URL_PSYCOPG",
    "postgresql://upi_fip:localtest@localhost:5432/upi_fip",
)

# (error_code, description, category, severity, owner_team, recommended_action)
ERROR_CODES = [
    ("BANK_DECLINED", "Bank declined the transaction", "BANK", "HIGH", "Bank Partnerships",
     "Contact bank liaison; check bank-side outage status"),
    ("BANK_UNAVAILABLE", "Bank system unreachable or timing out", "BANK", "CRITICAL", "Bank Partnerships",
     "Escalate to bank NOC; consider temporary PSP routing change"),
    ("BANK_INSUFFICIENT_FUNDS", "Payer account has insufficient balance", "BANK", "LOW", "Bank Partnerships",
     "No action required; user-side condition"),
    ("TECHNICAL_ERROR", "Internal platform processing error", "TECHNICAL", "HIGH", "Platform Engineering",
     "Check recent deploys and service logs for the affected window"),
    ("INTERNAL_ERROR", "Unhandled internal exception during processing", "TECHNICAL", "CRITICAL", "Platform Engineering",
     "Page on-call engineer; check error tracking dashboard"),
    ("APP_CRASH", "Client application crashed mid-transaction", "TECHNICAL", "HIGH", "Mobile Engineering",
     "Correlate with app version and device/OS; check crash reporting"),
    ("NETWORK_ERROR", "Generic network failure between client and gateway", "NETWORK", "MEDIUM", "SRE",
     "Check CDN/gateway health and regional network status"),
    ("TIMEOUT", "Request exceeded processing time threshold", "NETWORK", "MEDIUM", "SRE",
     "Check downstream dependency latency"),
    ("CONNECTION_RESET", "Connection dropped before completion", "NETWORK", "MEDIUM", "SRE",
     "Check mobile network carrier patterns and Wi-Fi handoff issues"),
    ("INVALID_REQUEST", "Malformed or invalid payment request", "VALIDATION", "LOW", "Platform Engineering",
     "Review client-side request construction for the affected app version"),
    ("LIMIT_EXCEEDED", "Transaction exceeds configured amount/velocity limit", "VALIDATION", "LOW", "Risk & Fraud",
     "Review limit configuration; no immediate action needed"),
    ("INVALID_VPA", "Payee VPA/handle is invalid or not found", "VALIDATION", "LOW", "Platform Engineering",
     "User-side data issue; no platform action required"),
    ("USER_CANCELLED", "User cancelled the transaction before completion", "USER", "LOW", "Product",
     "Excluded from PSR denominator; monitor for UX friction signals"),
    ("UNKNOWN_ERROR", "Unclassified failure requiring investigation", "UNKNOWN", "MEDIUM", "Platform Engineering",
     "Investigate and reclassify; track volume of unknowns as a data-quality signal"),
]


def main() -> None:
    conn = psycopg2.connect(DATABASE_URL_PSYCOPG)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO error_codes
                (error_code, description, category, severity, owner_team, recommended_action, active_flag)
            VALUES (%s, %s, %s, %s, %s, %s, TRUE)
            ON CONFLICT (error_code) DO UPDATE SET
                description = EXCLUDED.description,
                category = EXCLUDED.category,
                severity = EXCLUDED.severity,
                owner_team = EXCLUDED.owner_team,
                recommended_action = EXCLUDED.recommended_action
            """,
            ERROR_CODES,
        )
    print(f"Seeded {len(ERROR_CODES)} error codes.")
    conn.close()


if __name__ == "__main__":
    main()
