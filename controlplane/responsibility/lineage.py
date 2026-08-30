"""
Responsibility: Data Lineage Tracker
Tracks whether sensitive data from the user's input gets reproduced
in the LLM's output.

This is a deterministic check — no ML models required.
Compares PII items found in input against the output text
for verbatim or near-verbatim matches.
"""
import logging
import re
from typing import Any, Dict, List

logger = logging.getLogger("controlplane.lineage")


def check_data_lineage(
    input_text: str,
    output_text: str,
    input_pii: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Check if any PII detected in the input appears in the output.

    Args:
        input_text:  The user's original query
        output_text: The LLM's response text
        input_pii:   List of PII items detected by precheck/pii_input.py
                     Each item: {type: str, value: str, position: int}

    Returns:
        {
            leaked: bool,
            leaked_items: [{type, value, match_type}],
            severity: "none" | "low" | "medium" | "high" | "critical",
            summary: str,
        }
    """
    if not input_pii or not output_text:
        return _no_leak()

    leaked_items = []
    output_lower = output_text.lower()

    for pii_item in input_pii:
        pii_value = pii_item.get("value", "")
        pii_type = pii_item.get("type", "unknown")

        if not pii_value or len(pii_value) < 4:
            continue

        # Check 1: Exact match
        if pii_value in output_text:
            leaked_items.append({
                "type": pii_type,
                "value": _redact_for_log(pii_value, pii_type),
                "match_type": "exact",
            })
            continue

        # Check 2: Case-insensitive match
        if pii_value.lower() in output_lower:
            leaked_items.append({
                "type": pii_type,
                "value": _redact_for_log(pii_value, pii_type),
                "match_type": "case_insensitive",
            })
            continue

        # Check 3: Partial match for API keys / credentials
        # (model might reproduce part of the key)
        if pii_type in ("api_key", "aws_key", "private_key", "github_token"):
            # Check if any 8+ char substring appears
            if len(pii_value) >= 12:
                core = pii_value[3:-3]  # Strip prefix/suffix
                if core and core in output_text:
                    leaked_items.append({
                        "type": pii_type,
                        "value": _redact_for_log(pii_value, pii_type),
                        "match_type": "partial_credential",
                    })
                    continue

        # Check 4: Formatted variations for phone/CC numbers
        if pii_type in ("phone", "credit_card"):
            digits_only = re.sub(r"\D", "", pii_value)
            output_digits = re.sub(r"\D", "", output_text)
            if len(digits_only) >= 8 and digits_only in output_digits:
                leaked_items.append({
                    "type": pii_type,
                    "value": _redact_for_log(pii_value, pii_type),
                    "match_type": "reformatted",
                })

    if not leaked_items:
        return _no_leak()

    severity = _compute_severity(leaked_items)
    summary = f"{len(leaked_items)} sensitive item(s) from input reproduced in output"

    logger.warning(
        f"Data lineage: LEAKAGE detected | "
        f"items={len(leaked_items)} | severity={severity}"
    )

    return {
        "leaked": True,
        "leaked_items": leaked_items,
        "severity": severity,
        "summary": summary,
    }


def _compute_severity(leaked_items: List[Dict]) -> str:
    """Severity based on what leaked and how."""
    types = {item["type"] for item in leaked_items}

    # Credentials are always critical
    credential_types = {"api_key", "aws_key", "private_key", "github_token"}
    if types & credential_types:
        return "critical"

    # Financial data is high
    if "credit_card" in types or "ssn" in types:
        return "high"

    # Contact info is medium
    if "email" in types or "phone" in types:
        return "medium"

    return "low"


def _redact_for_log(value: str, pii_type: str) -> str:
    """Partially redact a PII value for safe logging."""
    if len(value) <= 6:
        return f"{value[:2]}***"
    return f"{value[:4]}...{value[-3:]}"


def _no_leak() -> Dict:
    return {
        "leaked": False,
        "leaked_items": [],
        "severity": "none",
        "summary": "No input data reproduced in output",
    }
