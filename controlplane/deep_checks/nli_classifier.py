"""
Deep Check: NLI Classifier
Classifies evidence-claim pairs as ENTAILMENT / CONTRADICTION / NEUTRAL.
In demo mode: uses keyword heuristics. In production: deberta-v3-base-mnli.
"""
import re
from typing import Any, Dict, List, Optional


# Contradiction signal words between evidence and claim
CONTRADICTION_SIGNALS = [
    "however", "but", "although", "despite", "contrary",
    "incorrect", "false", "wrong", "not true", "disputed",
    "actually", "in fact", "instead", "rather",
]

ENTAILMENT_SIGNALS = [
    "confirms", "supports", "indeed", "correct", "true",
    "according to", "as stated", "established", "verified",
    "consistent with", "aligned with",
]


def run_nli(claim: str, evidence_snippets: List[str]) -> Dict[str, Any]:
    """
    Run NLI classification between a claim and evidence.
    Returns: label (ENTAILMENT/CONTRADICTION/NEUTRAL) + confidence.

    In production: use cross-encoder/nli-deberta-v3-base.
    """
    if not evidence_snippets:
        return {
            "label": "NEUTRAL",
            "confidence": 0.5,
            "status": "UNKNOWN",
        }

    # Use best evidence snippet (first one for demo)
    best_evidence = evidence_snippets[0]

    label, confidence = _heuristic_nli(claim, best_evidence)

    status_map = {
        "ENTAILMENT": "SUPPORTED",
        "CONTRADICTION": "CONTRADICTED",
        "NEUTRAL": "UNKNOWN",
    }

    return {
        "label": label,
        "confidence": round(confidence, 3),
        "status": status_map[label],
        "evidence_used": best_evidence[:200],
    }


def _heuristic_nli(claim: str, evidence: str) -> tuple:
    """
    Heuristic NLI: compares key entities and negation patterns
    between claim and evidence.
    """
    claim_lower = claim.lower()
    evidence_lower = evidence.lower()

    # Extract key entities (capitalized words, numbers)
    claim_entities = set(re.findall(r'\b[A-Z][a-z]+\b|\b\d+\b', claim))
    evidence_entities = set(re.findall(r'\b[A-Z][a-z]+\b|\b\d+\b', evidence))

    entity_overlap = len(claim_entities & evidence_entities)
    entity_union = len(claim_entities | evidence_entities)
    overlap_ratio = entity_overlap / entity_union if entity_union > 0 else 0

    # Check for negation of key terms
    claim_keywords = set(re.findall(r'\b\w{5,}\b', claim_lower))
    negated_in_evidence = any(
        f"not {kw}" in evidence_lower or f"no {kw}" in evidence_lower
        for kw in claim_keywords
    )
    affirmed_in_evidence = any(kw in evidence_lower for kw in claim_keywords)

    # Contradiction signal words
    has_contradiction_signal = any(s in evidence_lower for s in CONTRADICTION_SIGNALS)
    has_entailment_signal = any(s in evidence_lower for s in ENTAILMENT_SIGNALS)

    # Decision tree
    if negated_in_evidence and overlap_ratio > 0.3:
        return "CONTRADICTION", 0.75
    elif has_contradiction_signal and overlap_ratio > 0.2:
        return "CONTRADICTION", 0.65
    elif affirmed_in_evidence and (has_entailment_signal or overlap_ratio > 0.4):
        return "ENTAILMENT", 0.72
    elif overlap_ratio > 0.35:
        return "ENTAILMENT", 0.60
    elif overlap_ratio > 0.15:
        return "NEUTRAL", 0.55
    else:
        return "NEUTRAL", 0.50
