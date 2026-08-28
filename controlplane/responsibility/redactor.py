"""
Responsibility: Deterministic Text Redactor
Safe transforms only — no semantic rewriting or LLM involvement.
"""
import re
from typing import Any, Dict, List


def redact_text(text: str, detections: List[Dict[str, Any]]) -> str:
    """
    Apply deterministic redaction to text based on detection results.
    Replaces detected values with labeled placeholders.
    Processes detections in reverse order to preserve string positions.
    """
    # Sort by start position descending to handle replacements without offset issues
    sorted_detections = sorted(detections, key=lambda d: d.get("start", 0), reverse=True)

    for det in sorted_detections:
        det_type = det.get("type", "unknown")
        value = det.get("value", "")
        category = det.get("category", "pii")

        if not value:
            continue

        label = _get_redaction_label(det_type, category)

        # Use string replacement (safer than index-based for UTF-8)
        text = text.replace(value, label, 1)

    return text


def _get_redaction_label(det_type: str, category: str) -> str:
    """Map detection type to a human-readable redaction placeholder."""
    labels = {
        # PII
        "email": "[EMAIL_REDACTED]",
        "phone_us": "[PHONE_REDACTED]",
        "credit_card": "[CREDIT_CARD_REDACTED]",
        "ssn": "[SSN_REDACTED]",
        "uk_nino": "[NATIONAL_ID_REDACTED]",
        "passport_like": "[PASSPORT_REDACTED]",
        # API Keys / Credentials
        "openai_key": "[API_KEY_REDACTED]",
        "aws_access_key": "[AWS_KEY_REDACTED]",
        "aws_secret": "[AWS_SECRET_REDACTED]",
        "github_token": "[GITHUB_TOKEN_REDACTED]",
        "generic_api_key": "[API_KEY_REDACTED]",
        "bearer_token": "[BEARER_TOKEN_REDACTED]",
        "private_key": "[PRIVATE_KEY_REDACTED]",
        "private_key_header": "[PRIVATE_KEY_REDACTED]",
        "certificate": "[CERTIFICATE_REDACTED]",
        "connection_string": "[CONNECTION_STRING_REDACTED]",
        "jwt_token": "[JWT_TOKEN_REDACTED]",
        "hex_secret": "[SECRET_HASH_REDACTED]",
        # NER-based
        "PERSON": "[PII_REDACTED]",
        "ADDRESS": "[ADDRESS_REDACTED]",
        "ORG": "[ORG_REDACTED]",
    }
    return labels.get(det_type, f"[{det_type.upper()}_REDACTED]")
