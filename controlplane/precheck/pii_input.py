"""
Pre-Check: Input PII Scanner
Layer 0 — runs BEFORE the LLM call, scanning the user's prompt.
"""
import re
from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# PII Regex patterns
# ---------------------------------------------------------------------------
PII_PATTERNS = {
    "email": re.compile(
        r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
    ),
    "phone_us": re.compile(
        r"\b(?:\+?1[\s.\-]?)?\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}\b"
    ),
    "credit_card": re.compile(
        r"\b(?:4\d{3}|5[1-5]\d{2}|6(?:011|5\d{2})|3[47]\d{2}|3(?:0[0-5]|[68]\d)\d{2})"
        r"[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b"
    ),
    "ssn": re.compile(
        r"\b(?!000|666|9\d{2})\d{3}[- ](?!00)\d{2}[- ](?!0000)\d{4}\b"
    ),
    # API / secret key patterns
    "openai_key": re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    "aws_access_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "github_token": re.compile(r"\bghp_[A-Za-z0-9]{36}\b"),
    "generic_api_key": re.compile(r"\b(?:api[_\-]?key|token|secret)[=:\s]+[\w\-]{16,}\b", re.IGNORECASE),
    "bearer_token": re.compile(r"\bBearer\s+[A-Za-z0-9\-_\.]+\.[A-Za-z0-9\-_\.]+\.[A-Za-z0-9\-_\.]+\b"),
    "private_key_header": re.compile(r"-----BEGIN\s+(?:RSA\s+)?PRIVATE KEY-----"),
    # National IDs
    "uk_nino": re.compile(r"\b[A-Z]{2}\s?\d{6}\s?[A-D]\b"),
    "passport_like": re.compile(r"\b[A-Z]{1,2}\d{7}\b"),
}

SEVERITY_MAP = {
    "email": "medium",
    "phone_us": "medium",
    "credit_card": "high",
    "ssn": "high",
    "openai_key": "critical",
    "aws_access_key": "critical",
    "github_token": "critical",
    "generic_api_key": "high",
    "bearer_token": "high",
    "private_key_header": "critical",
    "uk_nino": "high",
    "passport_like": "medium",
}


def scan_input_pii(text: str) -> List[Dict[str, Any]]:
    """
    Scan user input for PII / credentials.
    Returns a list of detected items with type, position, and severity.
    Note: We log but do NOT block on input PII — the user chose to include it.
    """
    detections = []

    for pii_type, pattern in PII_PATTERNS.items():
        for match in pattern.finditer(text):
            detections.append({
                "type": pii_type,
                "value": match.group(),
                "start": match.start(),
                "end": match.end(),
                "severity": SEVERITY_MAP.get(pii_type, "medium"),
                "source": "input",
            })

    return detections
