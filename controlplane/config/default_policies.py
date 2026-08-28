"""
Default Policy Rules — per impact tier and application type.
These are loaded at startup and can be overridden per-application via the DB.
"""

DEFAULT_POLICIES = {
    # Customer-facing assistant: strict
    "customer_support": {
        "low": {
            "performance": {"action": "allow", "threshold": 0.7},
            "responsibility": {"action": "annotate", "pii_threshold": 0.5},
            "cost": {"action": "allow", "budget_multiplier": 1.5},
        },
        "medium": {
            "performance": {"action": "annotate", "threshold": 0.5},
            "responsibility": {"action": "redact", "pii_threshold": 0.3},
            "cost": {"action": "warn", "budget_multiplier": 2.0},
        },
        "high": {
            "performance": {"action": "warn", "threshold": 0.3},
            "responsibility": {"action": "block", "pii_threshold": 0.1},
            "cost": {"action": "block", "budget_multiplier": 3.0},
        },
        "critical": {
            "performance": {"action": "block", "threshold": 0.1},
            "responsibility": {"action": "block", "pii_threshold": 0.0},
            "cost": {"action": "escalate", "budget_multiplier": 1.0},
        },
    },

    # Internal knowledge assistant: balanced
    "internal_kb": {
        "low": {
            "performance": {"action": "allow", "threshold": 0.8},
            "responsibility": {"action": "allow", "pii_threshold": 0.7},
            "cost": {"action": "allow", "budget_multiplier": 2.0},
        },
        "medium": {
            "performance": {"action": "annotate", "threshold": 0.6},
            "responsibility": {"action": "annotate", "pii_threshold": 0.5},
            "cost": {"action": "warn", "budget_multiplier": 2.5},
        },
        "high": {
            "performance": {"action": "annotate", "threshold": 0.4},
            "responsibility": {"action": "redact", "pii_threshold": 0.2},
            "cost": {"action": "warn", "budget_multiplier": 3.0},
        },
        "critical": {
            "performance": {"action": "block", "threshold": 0.2},
            "responsibility": {"action": "block", "pii_threshold": 0.0},
            "cost": {"action": "block", "budget_multiplier": 2.0},
        },
    },

    # Decision-support (regulated domain): most strict
    "decision_support": {
        "low": {
            "performance": {"action": "annotate", "threshold": 0.6},
            "responsibility": {"action": "annotate", "pii_threshold": 0.3},
            "cost": {"action": "allow", "budget_multiplier": 1.5},
        },
        "medium": {
            "performance": {"action": "warn", "threshold": 0.4},
            "responsibility": {"action": "redact", "pii_threshold": 0.1},
            "cost": {"action": "warn", "budget_multiplier": 2.0},
        },
        "high": {
            "performance": {"action": "block", "threshold": 0.2},
            "responsibility": {"action": "block", "pii_threshold": 0.0},
            "cost": {"action": "block", "budget_multiplier": 2.5},
        },
        "critical": {
            "performance": {"action": "escalate", "threshold": 0.1},
            "responsibility": {"action": "escalate", "pii_threshold": 0.0},
            "cost": {"action": "escalate", "budget_multiplier": 1.0},
        },
    },
}

# Impact weight multipliers for risk score calculation
IMPACT_WEIGHTS = {
    "low": 0.3,
    "medium": 0.6,
    "high": 1.0,
    "critical": 1.0,
}

# Action severity order
ACTION_SEVERITY = {
    "allow": 0,
    "annotate": 1,
    "warn": 2,
    "redact": 3,
    "block": 4,
    "escalate": 5,
}
