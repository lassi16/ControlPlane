"""
Pre-Check: Prompt Injection Detection
Detects attempts to override system instructions or hijack the AI's behavior.
"""
import re
from typing import Dict

# ---------------------------------------------------------------------------
# Rule-based injection patterns
# ---------------------------------------------------------------------------
INJECTION_PATTERNS = [
    # Role-override attempts
    re.compile(r"\bignore\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?|rules?|context)\b", re.IGNORECASE),
    re.compile(r"\byou\s+are\s+now\b", re.IGNORECASE),
    re.compile(r"\bact\s+as\s+(if\s+)?(?:you\s+are\s+)?(?:a\s+)?(?:an?\s+)?(?:DAN|evil|unfiltered|jailbreak)\b", re.IGNORECASE),
    re.compile(r"\bforget\s+(everything|all|your)\b", re.IGNORECASE),
    re.compile(r"\bdisregard\s+(your|all|any)\b", re.IGNORECASE),
    re.compile(r"\boverride\s+(?:your\s+)?(?:safety|ethical|previous)\b", re.IGNORECASE),
    # System prompt extraction
    re.compile(r"\brepeat\s+(your\s+)?(?:system\s+)?(?:prompt|instructions?|rules?)\b", re.IGNORECASE),
    re.compile(r"\bwhat\s+(is|are)\s+your\s+(?:system\s+)?(?:instructions?|prompt)\b", re.IGNORECASE),
    # Code injection via markdown
    re.compile(r"```.*?system.*?```", re.IGNORECASE | re.DOTALL),
    # Token manipulation
    re.compile(r"\|\|.{0,50}\|\|"),
    re.compile(r"<\s*\|.{0,50}\|\s*>"),
    # Jailbreak markers
    re.compile(r"\bDAN\b"),
    re.compile(r"\bjailbreak\b", re.IGNORECASE),
    re.compile(r"\bunfiltered\s+(?:AI|model|response)\b", re.IGNORECASE),
    # Role injection via fake system turns
    re.compile(r"\[SYSTEM\]", re.IGNORECASE),
    re.compile(r"\[INST\].*?\[/INST\]", re.DOTALL),
]

SUSPICIOUS_PHRASES = [
    "do anything now",
    "no restrictions",
    "no limitations",
    "pretend you have no",
    "hypothetically speaking, if you had no",
    "in this fictional scenario",
]


def detect_injection(text: str) -> Dict:
    """
    Detect prompt injection attempts.
    Returns a dict with score [0,1] and matched patterns.
    """
    matched = []
    score = 0.0

    # Pattern matching
    for pattern in INJECTION_PATTERNS:
        if pattern.search(text):
            matched.append(pattern.pattern[:60])
            score += 0.2

    # Phrase matching
    text_lower = text.lower()
    for phrase in SUSPICIOUS_PHRASES:
        if phrase in text_lower:
            matched.append(phrase)
            score += 0.15

    # Length anomaly (very long system-like preambles)
    if len(text) > 2000 and text_lower.count("system") > 3:
        score += 0.1
        matched.append("long_text_with_system_references")

    # Normalize to [0, 1]
    score = min(score, 1.0)

    return {
        "score": score,
        "matched_patterns": matched[:5],  # Return top 5 matches
        "is_injection": score > 0.4,
    }
