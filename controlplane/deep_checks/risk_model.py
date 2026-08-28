"""
Deep Check: Risk Model
Computes calibrated P(unsupported claim) from claim-level verification results.
"""
from typing import Any, Dict, List


def compute_risk_score(claims: List[Dict[str, Any]], confidence_score: float = 0.5) -> Dict:
    """
    Compute overall risk score from claim statuses.

    risk_score = 0.4 * contradiction_rate
               + 0.3 * (1 - groundedness_score)
               + 0.2 * (1 - verification_coverage)
               + 0.1 * (1 - confidence_calibration)
    """
    if not claims:
        return {
            "risk_score": 0.0,
            "detector_confidence": 0.3,  # Low confidence — nothing verified
            "contradiction_rate": 0.0,
            "groundedness_score": 0.0,
            "verification_coverage": 0.0,
        }

    total = len(claims)
    verifiable = [c for c in claims if c["type"] not in ("opinion", "skip")]
    verified = [c for c in claims if c["status"] in ("SUPPORTED", "CONTRADICTED", "UNKNOWN")]
    contradicted = [c for c in claims if c["status"] == "CONTRADICTED"]
    supported = [c for c in claims if c["status"] == "SUPPORTED"]

    contradiction_rate = len(contradicted) / total if total > 0 else 0.0
    groundedness_score = len(supported) / max(len(verifiable), 1)
    verification_coverage = len(verified) / total if total > 0 else 0.0

    # Confidence calibration: penalize highly assertive responses with low support
    confidence_calibration = 1.0 - abs(confidence_score - groundedness_score)

    risk_score = (
        0.4 * contradiction_rate
        + 0.3 * (1 - groundedness_score)
        + 0.2 * (1 - verification_coverage)
        + 0.1 * (1 - confidence_calibration)
    )
    risk_score = max(0.0, min(1.0, risk_score))

    # Detector confidence: higher when more claims verified
    detector_confidence = min(verification_coverage * 1.2, 1.0)
    if total < 2:
        detector_confidence *= 0.7  # Low sample → less confident

    return {
        "risk_score": round(risk_score, 3),
        "detector_confidence": round(detector_confidence, 3),
        "contradiction_rate": round(contradiction_rate, 3),
        "groundedness_score": round(groundedness_score, 3),
        "verification_coverage": round(verification_coverage, 3),
        "claim_summary": {
            "total": total,
            "supported": len(supported),
            "contradicted": len(contradicted),
            "unknown": len([c for c in claims if c["status"] == "UNKNOWN"]),
            "not_verifiable": len([c for c in claims if c["status"] == "NOT_VERIFIABLE"]),
        },
    }
