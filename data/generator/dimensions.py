"""
Dimension definitions for the synthetic UPI transaction generator.

All identifiers are synthetic (BANK_A, PSP_1, ...) and must never be presented
as real bank/PSP integrations. Weights are hand-tuned to produce a plausible,
skewed real-world distribution (a few large banks/PSPs, a long tail of
smaller ones) rather than a uniform toy distribution.
"""

BANKS = {
    "BANK_A": 0.19,
    "BANK_B": 0.16,
    "BANK_C": 0.14,
    "BANK_D": 0.12,
    "BANK_E": 0.10,
    "BANK_F": 0.08,
    "BANK_G": 0.07,
    "BANK_H": 0.06,
    "BANK_I": 0.05,
    "BANK_J": 0.03,
}

PSPS = {
    "PSP_ALPHA": 0.32,
    "PSP_BRAVO": 0.27,
    "PSP_CHARLIE": 0.18,
    "PSP_DELTA": 0.13,
    "PSP_ECHO": 0.10,
}

# device_type -> share of overall traffic
DEVICE_TYPES = {"Android": 0.66, "iOS": 0.34}

# OS build/version labels, conditioned on device_type
OS_BY_DEVICE = {
    "Android": {
        "U28": 0.34,   # majority current build — this is the anomaly-relevant version
        "U25": 0.22,
        "T21": 0.18,
        "T15": 0.14,
        "S30": 0.12,
    },
    "iOS": {
        "iOS 17.4": 0.30,
        "iOS 17.2": 0.24,
        "iOS 16.6": 0.20,
        "iOS 16.3": 0.14,
        "iOS 15.7": 0.12,
    },
}

APP_VERSIONS = {
    "4.2.1": 0.38,   # current release — anomaly-relevant version
    "4.2.0": 0.24,
    "4.1.5": 0.18,
    "4.0.9": 0.12,
    "3.9.2": 0.08,
}

NETWORK_TYPES = {"WIFI": 0.38, "4G": 0.42, "5G": 0.15, "UNSTABLE": 0.05}

TRANSACTION_TYPES = {
    "P2P": 0.40,
    "P2M": 0.32,
    "BILL_PAY": 0.14,
    "RECHARGE": 0.09,
    "QR_PAYMENT": 0.05,
}

GEOGRAPHIES = {
    "Mumbai": 0.14,
    "Delhi NCR": 0.13,
    "Bengaluru": 0.12,
    "Hyderabad": 0.09,
    "Chennai": 0.08,
    "Pune": 0.07,
    "Kolkata": 0.06,
    "Ahmedabad": 0.05,
    "Jaipur": 0.04,
    "Lucknow": 0.04,
    "Other Tier-2/3": 0.18,
}

# Baseline (non-anomalous) error code distribution, conditioned on the
# transaction being a failure. Categories map to sql/migrations error_codes.
FAILURE_ERROR_DIST = {
    "BANK_DECLINED": 0.20,
    "BANK_UNAVAILABLE": 0.08,
    "BANK_INSUFFICIENT_FUNDS": 0.17,
    "TECHNICAL_ERROR": 0.10,
    "INTERNAL_ERROR": 0.04,
    "APP_CRASH": 0.05,
    "NETWORK_ERROR": 0.12,
    "TIMEOUT": 0.09,
    "CONNECTION_RESET": 0.05,
    "INVALID_REQUEST": 0.03,
    "LIMIT_EXCEEDED": 0.02,
    "INVALID_VPA": 0.02,
    "USER_CANCELLED": 0.02,
    "UNKNOWN_ERROR": 0.01,
}

ERROR_CATEGORY_BY_CODE = {
    "BANK_DECLINED": "BANK",
    "BANK_UNAVAILABLE": "BANK",
    "BANK_INSUFFICIENT_FUNDS": "BANK",
    "TECHNICAL_ERROR": "TECHNICAL",
    "INTERNAL_ERROR": "TECHNICAL",
    "APP_CRASH": "TECHNICAL",
    "NETWORK_ERROR": "NETWORK",
    "TIMEOUT": "NETWORK",
    "CONNECTION_RESET": "NETWORK",
    "INVALID_REQUEST": "VALIDATION",
    "LIMIT_EXCEEDED": "VALIDATION",
    "INVALID_VPA": "VALIDATION",
    "USER_CANCELLED": "USER",
    "UNKNOWN_ERROR": "UNKNOWN",
}

# During the injected anomaly, failures skew heavily toward bank/technical
# causes, consistent with a bank-dependency-style incident.
ANOMALY_FAILURE_ERROR_DIST = {
    "BANK_UNAVAILABLE": 0.45,
    "BANK_DECLINED": 0.20,
    "TECHNICAL_ERROR": 0.20,
    "TIMEOUT": 0.10,
    "INTERNAL_ERROR": 0.05,
}

# --- Baseline health parameters ---
BASELINE_FAILURE_RATE = 0.028          # ~97.2% baseline PSR
RETRY_PROBABILITY_AFTER_FAILURE = 0.38
RETRY_SUCCESS_PROBABILITY = 0.55
DUPLICATE_RATE = 0.0015
PENDING_RATE = 0.002

# --- Injected anomaly definition (kept in sync with docs/decisions.md D5) ---
ANOMALY_FINGERPRINT = {
    "payer_bank": "BANK_A",
    "device_type": "Android",
    "os": "U28",
    "app_version": "4.2.1",
}
ANOMALY_WINDOW_START_HOUR = 18
ANOMALY_WINDOW_END_HOUR = 20  # exclusive
ANOMALY_FAILURE_RATE = 0.42     # observed PSR ~58% for this exact segment/window
ANOMALY_SEGMENT_TXN_COUNT_FRACTION = 0.012  # fraction of total dataset volume
