"""
Policy Engine — combines all check results into a final action decision.
"""
from typing import Any, Dict, Optional
from config.default_policies import ACTION_SEVERITY, IMPACT_WEIGHTS, DEFAULT_POLICIES


def evaluate_policy(
    tier1_results: Dict[str, Any],
    tier2_results: Dict[str, Any],
    impact: str,
    application_id: str,
    actual_cost: float = 0.0,
    deep_results: Optional[Dict] = None,
    lineage: Optional[Dict] = None,
) -> Dict[str, Any]:
    """
    Evaluate all check results and return a policy decision.
    The most severe action wins — but each decision is logged independently.
    """
    actions = []
    annotations = []

    # --- Responsibility policy ---
    resp_action, resp_annotations = _responsibility_policy(tier1_results, tier2_results, impact)
    actions.append(resp_action)
    annotations.extend(resp_annotations)

    # --- Data lineage policy ---
    lineage_action = "allow"
    if lineage and lineage.get("leaked"):
        severity = lineage.get("severity", "low")
        if severity in ("critical", "high"):
            lineage_action = "redact"
            annotations.append(f"DATA_LEAKAGE: {lineage['summary']} (severity={severity})")
        elif severity == "medium":
            lineage_action = "annotate"
            annotations.append(f"DATA_LEAKAGE: {lineage['summary']}")
    actions.append(lineage_action)

    # --- Performance policy (deep checks) ---
    perf_action = "allow"
    if deep_results:
        perf_action, perf_annotations = _performance_policy(deep_results, impact)
        actions.append(perf_action)
        annotations.extend(perf_annotations)

    # --- Cost policy ---
    cost_action = _cost_policy(actual_cost, impact)
    actions.append(cost_action)

    # Resolve: most severe wins
    final_action = max(actions, key=lambda a: ACTION_SEVERITY.get(a, 0))

    return {
        "action": final_action,
        "responsibility_action": resp_action,
        "lineage_action": lineage_action,
        "performance_action": perf_action,
        "cost_action": cost_action,
        "impact": impact,
        "annotations": annotations,
        "reasoning": _build_reasoning(final_action, tier1_results, tier2_results, impact),
    }



def _responsibility_policy(tier1: Dict, tier2: Dict, impact: str) -> tuple:
    """Determine action based on PII, credentials, toxicity."""
    annotations = []

    # Credentials in response → always REDACT (automatic)
    if tier1.get("credentials_detected"):
        annotations.append("CREDENTIAL_DETECTED: Automatic redaction applied.")
        return "redact", annotations

    # PII in response
    if tier1.get("pii_detected"):
        if impact in ("high", "critical"):
            annotations.append("PII_DETECTED: High-impact context — blocking response.")
            return "block", annotations
        else:
            annotations.append("PII_DETECTED: Redacting sensitive data from response.")
            return "redact", annotations


    # Topic drift — high threshold to avoid false positives on math/code
    drift = tier2.get("topic_drift", 0)
    if drift > 0.90:
        annotations.append(f"TOPIC_DRIFT: response may be off-topic (drift={drift:.2f})")
        return "annotate", annotations

    return "allow", annotations


def _performance_policy(deep_results: Dict, impact: str) -> tuple:
    """Determine action based on deep verification results."""
    annotations = []
    risk_score = deep_results.get("risk_score", 0.0)
    detector_confidence = deep_results.get("detector_confidence", 0.5)
    contradiction_rate = deep_results.get("contradiction_rate", 0.0)

    impact_weight = IMPACT_WEIGHTS.get(impact, 0.6)
    effective_risk = risk_score * detector_confidence * impact_weight

    if contradiction_rate > 0.5:
        annotations.append(f"CONTRADICTION_RATE: {contradiction_rate:.0%} of claims contradicted")

    if effective_risk > 0.5:
        annotations.append(f"HIGH_HALLUCINATION_RISK: effective_risk={effective_risk:.2f}")
        return "block", annotations
    elif effective_risk > 0.3:
        annotations.append(f"MODERATE_HALLUCINATION_RISK: effective_risk={effective_risk:.2f}")
        return "warn", annotations
    elif effective_risk > 0.15:
        annotations.append(f"LOW_HALLUCINATION_RISK: effective_risk={effective_risk:.2f}")
        return "annotate", annotations

    return "allow", annotations


def _cost_policy(actual_cost: float, impact: str) -> str:
    """Simple cost anomaly gate."""
    # Thresholds: $0.10 for low/medium, $0.25 for high/critical
    threshold = 0.25 if impact in ("high", "critical") else 0.10
    if actual_cost > threshold * 10:
        return "escalate"
    elif actual_cost > threshold * 3:
        return "warn"
    return "allow"


def _build_reasoning(action: str, tier1: Dict, tier2: Dict, impact: str) -> str:
    parts = [f"impact={impact}", f"action={action}"]
    if tier1.get("credentials_detected"):
        parts.append("credentials_in_response=true")
    if tier1.get("pii_detected"):
        parts.append(f"pii_detections={tier1.get('detection_count', 0)}")
    return " | ".join(parts)
