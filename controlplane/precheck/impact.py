"""
Pre-Check: Impact Estimator
Provides a preliminary impact tier (low/medium/high/critical) based on
application domain and query classification.
"""
from typing import Dict

# Application domain → base impact tier
APP_DOMAIN_IMPACT = {
    "medical": "high",
    "healthcare": "high",
    "financial": "high",
    "legal": "high",
    "decision_support": "high",
    "customer_support": "medium",
    "internal_kb": "medium",
    "hr": "medium",
    "entertainment": "low",
    "creative": "low",
    "education": "medium",
    "default": "medium",
}

# Query labels that escalate impact
ESCALATING_LABELS = {
    "medical": "high",
    "financial": "high",
    "legal": "high",
    "personal": "medium",
}

IMPACT_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}
IMPACT_LEVELS = ["low", "medium", "high", "critical"]


def estimate_impact(query_labels: Dict[str, float], application_id: str) -> str:
    """
    Estimate preliminary impact tier for a request.
    Uses application domain + active query labels.
    Can only be increased (never decreased) by impact_rescore.py after response.
    """
    # Map application_id to domain
    app_domain = _infer_app_domain(application_id)
    base_impact = APP_DOMAIN_IMPACT.get(app_domain, APP_DOMAIN_IMPACT["default"])

    # Check if any high-risk query labels are active (score > 0.2)
    max_escalation = base_impact
    for label, score in query_labels.items():
        if score >= 0.2 and label in ESCALATING_LABELS:
            escalated = ESCALATING_LABELS[label]
            if IMPACT_ORDER[escalated] > IMPACT_ORDER[max_escalation]:
                max_escalation = escalated

    return max_escalation


def _infer_app_domain(application_id: str) -> str:
    """Infer domain from application ID string."""
    app_lower = application_id.lower()
    for domain in APP_DOMAIN_IMPACT:
        if domain != "default" and domain in app_lower:
            return domain
    return "default"
