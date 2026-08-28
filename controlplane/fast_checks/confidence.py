"""
Fast Check: Confidence Signal Extraction
Analyzes hedging language, assertion density, and modal verbs to estimate
how confident the LLM sounds (NOT a correctness signal).
"""
import re
from typing import Dict, List

HEDGING_PHRASES = [
    r"\bi think\b", r"\bi believe\b", r"\bi'm not sure\b",
    r"\bit's possible\b", r"\bpossibly\b", r"\bprobably\b",
    r"\bperhaps\b", r"\bapproximately\b", r"\baround\b",
    r"\bmight be\b", r"\bcould be\b", r"\bi'm unsure\b",
    r"\bnot certain\b", r"\bmay be\b", r"\bit seems\b",
    r"\bif i recall\b", r"\bto my knowledge\b",
]

STRONG_ASSERTION_PHRASES = [
    r"\bdefinitely\b", r"\bcertainly\b", r"\babsolutely\b",
    r"\bwithout a doubt\b", r"\bthe answer is\b",
    r"\bthe fact is\b", r"\bit is known that\b",
    r"\bproven\b", r"\bconfirmed\b", r"\bguaranteed\b",
    r"\balways\b", r"\bnever\b", r"\beveryone knows\b",
]

MODAL_VERBS = [
    r"\bmight\b", r"\bcould\b", r"\bwould\b",
    r"\bshould\b", r"\bmay\b", r"\bcan\b",
]

COMPILED_HEDGING = [re.compile(p, re.IGNORECASE) for p in HEDGING_PHRASES]
COMPILED_ASSERTIONS = [re.compile(p, re.IGNORECASE) for p in STRONG_ASSERTION_PHRASES]
COMPILED_MODALS = [re.compile(p, re.IGNORECASE) for p in MODAL_VERBS]


def confidence_signals(text: str) -> Dict:
    """
    Extract confidence signals from LLM response.
    Returns a confidence_score [0,1] where:
      - 1.0 = highly assertive (sounds very confident)
      - 0.0 = highly hedged (sounds uncertain)
    This is NOT a correctness signal — it's used as one input to risk scoring.
    """
    text_lower = text.lower()
    words = len(text.split())
    if words == 0:
        return {"score": 0.5, "hedging_count": 0, "assertion_count": 0, "modal_count": 0}

    hedging_count = sum(1 for p in COMPILED_HEDGING if p.search(text))
    assertion_count = sum(1 for p in COMPILED_ASSERTIONS if p.search(text))
    modal_count = sum(1 for p in COMPILED_MODALS if p.search(text))

    # Score: assertions push up, hedging pushes down
    # Base: 0.5 (neutral)
    score = 0.5
    score += assertion_count * 0.08
    score -= hedging_count * 0.07
    score -= modal_count * 0.02

    score = max(0.0, min(1.0, score))

    return {
        "score": round(score, 3),
        "hedging_count": hedging_count,
        "assertion_count": assertion_count,
        "modal_count": modal_count,
        "interpretation": _interpret(score),
    }


def _interpret(score: float) -> str:
    if score >= 0.75:
        return "highly_assertive"
    elif score >= 0.55:
        return "moderately_assertive"
    elif score >= 0.35:
        return "hedged"
    else:
        return "highly_uncertain"
