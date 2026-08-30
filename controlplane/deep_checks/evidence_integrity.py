"""
Deep Check: Evidence Integrity Scanner
Scans retrieved evidence for adversarial content before using it for NLI.

Checks:
  1. Prompt injection patterns in evidence text
  2. Source domain trust scoring
  3. Content-type anomaly (code/instructions where factual prose expected)
"""
import logging
import re
from typing import Any, Dict, List

logger = logging.getLogger("controlplane.evidence_integrity")

# Patterns that indicate adversarial content in evidence
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"you\s+are\s+now",
    r"forget\s+(everything|all)",
    r"disregard\s+(all|any|the)",
    r"override\s+your",
    r"new\s+instructions?:",
    r"system\s*:",
    r"\bDAN\b",
    r"jailbreak",
]
_INJECTION_RE = re.compile("|".join(INJECTION_PATTERNS), re.IGNORECASE)

# Content that looks like instructions rather than factual prose
INSTRUCTION_PATTERNS = [
    r"^step\s+\d+:",
    r"^\d+\.\s+(click|open|go to|navigate|download)",
    r"(sudo|chmod|pip install|npm install)\s+",
    r"<script[\s>]",
    r"javascript:",
]
_INSTRUCTION_RE = re.compile("|".join(INSTRUCTION_PATTERNS), re.IGNORECASE | re.MULTILINE)

# Trusted domains get higher authority scores
TRUSTED_DOMAINS = {
    "wikipedia.org": 0.95,
    "who.int": 0.98,
    "cdc.gov": 0.97,
    "nih.gov": 0.97,
    "nhs.uk": 0.97,
    "mayoclinic.org": 0.97,
    "nasa.gov": 0.98,
    "nature.com": 0.95,
    "w3.org": 0.97,
    "docs.python.org": 0.98,
    "investopedia.com": 0.85,
    "history.com": 0.85,
    "britannica.com": 0.93,
    "ipcc.ch": 0.98,
}

# Untrusted / known-bad sources
UNTRUSTED_DOMAINS = {
    "reddit.com", "quora.com", "yahoo.com",
    "answers.com", "wiki.answers.com",
}


def scan_evidence_integrity(evidence: Dict[str, Any]) -> Dict[str, Any]:
    """
    Scan a single piece of evidence for integrity issues.

    Returns:
        {
            safe: bool,
            issues: [str],
            adjusted_authority: float,
            original_authority: float,
        }
    """
    issues = []
    snippet = evidence.get("snippet", "")
    source_url = evidence.get("source_url", "")
    original_authority = evidence.get("authority", 0.5)
    adjusted = original_authority

    # 1. Check for injection patterns in evidence text
    injection_matches = _INJECTION_RE.findall(snippet)
    if injection_matches:
        issues.append(f"injection_pattern: {injection_matches[0]}")
        adjusted = 0.0  # Discard entirely
        logger.warning(f"Evidence integrity: injection detected in '{source_url}'")

    # 2. Check source domain trust
    domain_trust = _score_domain(source_url)
    if domain_trust == "untrusted":
        issues.append(f"untrusted_source: {source_url}")
        adjusted = min(adjusted, 0.3)
    elif domain_trust == "unknown":
        # Unknown domains get a small penalty but aren't rejected
        adjusted = min(adjusted, 0.5)

    # 3. Check for instruction-heavy content (not factual prose)
    instruction_matches = _INSTRUCTION_RE.findall(snippet)
    if len(instruction_matches) >= 2:
        issues.append("content_anomaly: instructions_not_prose")
        adjusted *= 0.5

    # 4. Check for very short / empty evidence
    if len(snippet.strip()) < 20:
        issues.append("too_short")
        adjusted = 0.0

    safe = len(issues) == 0 or adjusted > 0.1

    return {
        "safe": safe,
        "issues": issues,
        "adjusted_authority": round(adjusted, 3),
        "original_authority": original_authority,
    }


def scan_all_evidence(evidence_list: List[Dict]) -> List[Dict]:
    """
    Scan all evidence items. Returns the list with integrity results attached.
    Unsafe evidence is flagged but not removed — caller decides what to do.
    """
    results = []
    for ev in evidence_list:
        integrity = scan_evidence_integrity(ev)
        ev_copy = {**ev}
        ev_copy["integrity"] = integrity
        if integrity["adjusted_authority"] != integrity["original_authority"]:
            ev_copy["authority"] = integrity["adjusted_authority"]
        results.append(ev_copy)

    safe_count = sum(1 for r in results if r["integrity"]["safe"])
    logger.info(f"Evidence integrity: {safe_count}/{len(results)} passed")
    return results


def _score_domain(url: str) -> str:
    """Score a URL's domain as trusted, untrusted, or unknown."""
    if not url or url.startswith("internal://"):
        return "trusted"  # Internal tools are always trusted

    url_lower = url.lower()
    for domain in TRUSTED_DOMAINS:
        if domain in url_lower:
            return "trusted"
    for domain in UNTRUSTED_DOMAINS:
        if domain in url_lower:
            return "untrusted"
    return "unknown"
