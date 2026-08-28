"""
Fast Check: Impact Re-Scorer
Scans response content for high-impact domain signals and upgrades the
preliminary impact tier if necessary. Can only increase, never decrease.
"""
import re
from typing import List

IMPACT_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}
IMPACT_LEVELS = ["low", "medium", "high", "critical"]

# Medical domain signals → HIGH or CRITICAL
MEDICAL_KEYWORDS = [
    "medication", "dosage", "dose", "drug interaction", "side effect",
    "contraindication", "prescription", "overdose", "symptom", "diagnosis",
    "treatment", "therapy", "serotonin syndrome", "anaphylaxis",
    "adverse reaction", "clinical trial", "ssri", "maoi", "opioid",
    "antidepressant", "antibiotic", "chemotherapy", "insulin",
    "blood pressure", "heart rate", "seizure", "stroke", "cardiac",
]

# Financial domain signals → HIGH
FINANCIAL_KEYWORDS = [
    "investment advice", "buy stock", "sell stock", "portfolio allocation",
    "financial planning", "account number", "routing number",
    "tax evasion", "insider trading", "margin call", "leverage",
    "specific fund recommendation", "guaranteed return",
]

# Legal domain signals → HIGH
LEGAL_KEYWORDS = [
    "legal citation", "court ruling", "case law", "statute",
    "you have the right", "miranda", "constitutional right",
    "legal advice", "lawsuit filing", "contract clause",
]

MEDICAL_PATTERNS = [re.compile(kw, re.IGNORECASE) for kw in MEDICAL_KEYWORDS]
FINANCIAL_PATTERNS = [re.compile(kw, re.IGNORECASE) for kw in FINANCIAL_KEYWORDS]
LEGAL_PATTERNS = [re.compile(kw, re.IGNORECASE) for kw in LEGAL_KEYWORDS]


def rescore_impact(response_text: str, preliminary_impact: str) -> str:
    """
    Re-score impact based on response content.
    Can only INCREASE impact — never decrease.
    """
    current_level = IMPACT_ORDER.get(preliminary_impact, 1)
    max_level = current_level

    # Medical detection → escalate to HIGH minimum
    medical_hits = sum(1 for p in MEDICAL_PATTERNS if p.search(response_text))
    if medical_hits >= 2:
        max_level = max(max_level, IMPACT_ORDER["high"])
    elif medical_hits >= 1:
        max_level = max(max_level, IMPACT_ORDER["medium"])

    # Financial → HIGH
    financial_hits = sum(1 for p in FINANCIAL_PATTERNS if p.search(response_text))
    if financial_hits >= 1:
        max_level = max(max_level, IMPACT_ORDER["high"])

    # Legal → HIGH
    legal_hits = sum(1 for p in LEGAL_PATTERNS if p.search(response_text))
    if legal_hits >= 1:
        max_level = max(max_level, IMPACT_ORDER["high"])

    # Critical escalation: very specific medical + high confidence phrasing
    if medical_hits >= 3 and "do not" in response_text.lower():
        max_level = max(max_level, IMPACT_ORDER["critical"])

    return IMPACT_LEVELS[max_level]
