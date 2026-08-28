"""
Fast Check Tier 1 — Deterministic Pattern Matching on LLM Response
Runs inline (before response is delivered to the user).
"""
import re
from typing import Any, Dict, List

# Re-use PII patterns from precheck
from precheck.pii_input import PII_PATTERNS, SEVERITY_MAP

# Additional output-specific patterns
CREDENTIAL_PATTERNS = {
    "private_key": re.compile(r"-----BEGIN\s+(?:RSA\s+|EC\s+|DSA\s+)?PRIVATE KEY-----"),
    "certificate": re.compile(r"-----BEGIN CERTIFICATE-----"),
    "aws_secret": re.compile(r"(?:aws_secret_access_key|AWS_SECRET)[=:\s]+[A-Za-z0-9+/]{40}\b", re.IGNORECASE),
    "connection_string": re.compile(r"(?:mongodb|postgres|mysql|redis|amqp)://[^@\s]+:[^@\s]+@[^\s]+", re.IGNORECASE),
    "jwt_token": re.compile(r"eyJ[A-Za-z0-9\-_]+\.eyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+"),
    "hex_secret": re.compile(r"\b[0-9a-f]{40}\b|\b[0-9a-f]{64}\b"),  # SHA1/SHA256-like
}

CREDENTIAL_SEVERITY = {k: "critical" for k in CREDENTIAL_PATTERNS}

# Loop detection: repeated token sequences > N chars
LOOP_THRESHOLD = 150


def tier1_check(text: str) -> Dict[str, Any]:
    """
    Deterministic checks on LLM response:
    - PII pattern matching
    - Credential / secret detection
    - Loop detection (repeated content)
    Returns structured detection results.
    """
    detections: List[Dict] = []
    pii_detected = False
    credentials_detected = False

    # PII patterns (same as input scanner, applied to output)
    for pii_type, pattern in PII_PATTERNS.items():
        for match in pattern.finditer(text):
            pii_detected = True
            detections.append({
                "type": pii_type,
                "value": match.group(),
                "start": match.start(),
                "end": match.end(),
                "severity": SEVERITY_MAP.get(pii_type, "medium"),
                "source": "output",
                "category": "pii",
            })

    # Credential patterns
    for cred_type, pattern in CREDENTIAL_PATTERNS.items():
        for match in pattern.finditer(text):
            credentials_detected = True
            detections.append({
                "type": cred_type,
                "value": match.group()[:50] + "...",  # Truncate for safety
                "start": match.start(),
                "end": match.end(),
                "severity": "critical",
                "source": "output",
                "category": "credential",
            })

    # Loop detection
    loop_detected = _detect_loop(text)

    return {
        "pii_detected": pii_detected,
        "credentials_detected": credentials_detected,
        "loop_detected": loop_detected,
        "detections": detections,
        "detection_count": len(detections),
        "highest_severity": _highest_severity(detections),
    }


def _detect_loop(text: str) -> bool:
    """Detect repeated token sequences (model repetition loops)."""
    if len(text) < LOOP_THRESHOLD * 2:
        return False
    chunk = text[:LOOP_THRESHOLD]
    rest = text[LOOP_THRESHOLD:]
    return chunk in rest


def _highest_severity(detections: List[Dict]) -> str:
    order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    if not detections:
        return "none"
    return max(detections, key=lambda d: order.get(d.get("severity", "low"), 0))["severity"]
