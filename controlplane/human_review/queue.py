"""
Human Review: Priority Queue
Routes high-risk events to a review queue with priority levels.

Priority levels:
  CRITICAL — risk > 0.7 + high confidence + high/critical impact
  HIGH     — risk > 0.5 OR any contradicted claims + high impact
  MEDIUM   — risk > 0.3 OR moderate concerns
  LOW      — logged only, no active review needed
"""
import logging
import time
from typing import Any, Dict, List, Optional

from telemetry.event_store import update_event

logger = logging.getLogger("controlplane.review_queue")


def compute_priority(
    risk_score: float,
    detector_confidence: float,
    impact: str,
    contradiction_count: int = 0,
) -> str:
    """
    Compute review priority based on risk signals.
    Higher risk + higher confidence + higher impact = higher priority.
    """
    impact_weight = {"critical": 1.0, "high": 0.8, "medium": 0.5, "low": 0.2}.get(impact, 0.5)

    # CRITICAL: high risk, confident detector, serious impact
    if risk_score > 0.7 and detector_confidence > 0.7 and impact_weight >= 0.8:
        return "CRITICAL"

    # HIGH: significant risk or contradictions in high-impact context
    if risk_score > 0.5 and impact_weight >= 0.8:
        return "HIGH"
    if contradiction_count >= 2 and impact_weight >= 0.5:
        return "HIGH"

    # MEDIUM: moderate risk
    if risk_score > 0.3:
        return "MEDIUM"
    if contradiction_count >= 1:
        return "MEDIUM"

    return "LOW"


def enqueue_for_review(
    event_id: str,
    risk_score: float,
    detector_confidence: float,
    impact: str,
    claims: List[Dict],
) -> Optional[Dict]:
    """
    Evaluate whether an event should be queued for human review.
    If yes, update the event with review metadata.

    Returns:
        Review metadata dict if queued, None if not needed.
    """
    contradicted = [c for c in claims if c.get("status") == "CONTRADICTED"]
    contradiction_count = len(contradicted)

    priority = compute_priority(
        risk_score=risk_score,
        detector_confidence=detector_confidence,
        impact=impact,
        contradiction_count=contradiction_count,
    )

    # LOW priority = log only, don't queue
    if priority == "LOW":
        return None

    review_data = {
        "review_status": "pending",
        "review_priority": priority,
        "review_queued_at": time.time(),
        "review_reason": _build_reason(risk_score, contradiction_count, impact, priority),
        "review_contradicted_claims": [
            {"text": c.get("text", "")[:150], "confidence": c.get("nli_confidence", 0)}
            for c in contradicted[:5]  # Cap at 5 to keep payload small
        ],
    }

    # Write to event store
    update_event(event_id, review_data)

    logger.info(
        f"Review queued | event_id={event_id} | priority={priority} | "
        f"risk={risk_score:.2f} | contradictions={contradiction_count}"
    )

    return review_data


def submit_review(
    event_id: str,
    reviewer_decision: str,
    reviewer_notes: str = "",
) -> Dict:
    """
    Submit a human reviewer's decision on a queued event.

    Args:
        event_id: The event to review
        reviewer_decision: "correct" | "incorrect" | "uncertain"
        reviewer_notes: Optional free-text notes

    Returns:
        Updated review metadata
    """
    valid_decisions = {"correct", "incorrect", "uncertain"}
    if reviewer_decision not in valid_decisions:
        raise ValueError(f"Decision must be one of {valid_decisions}")

    review_update = {
        "review_status": "reviewed",
        "review_decision": reviewer_decision,
        "review_notes": reviewer_notes,
        "review_completed_at": time.time(),
    }

    update_event(event_id, review_update)

    logger.info(
        f"Review submitted | event_id={event_id} | "
        f"decision={reviewer_decision}"
    )

    return review_update


def _build_reason(risk_score: float, contradiction_count: int, impact: str, priority: str) -> str:
    parts = []
    if contradiction_count > 0:
        parts.append(f"{contradiction_count} contradicted claim(s)")
    if risk_score > 0.5:
        parts.append(f"risk score {risk_score:.0%}")
    if impact in ("high", "critical"):
        parts.append(f"{impact} impact context")
    return " · ".join(parts) if parts else f"Queued at {priority} priority"
