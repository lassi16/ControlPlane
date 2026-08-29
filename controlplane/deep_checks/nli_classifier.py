"""
Deep Check: NLI Classifier
Classifies evidence-claim pairs as ENTAILMENT / CONTRADICTION / NEUTRAL.

Implementation:
  Primary: Groq LLM — more accurate than DeBERTa for complex claims,
           free, no RAM overhead, works on Render free tier
  Fallback: Heuristic keyword + entity overlap (when Groq unavailable)

In a GPU environment you can swap _groq_nli() for cross-encoder/nli-deberta-v3-small
— the public API is identical.
"""
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger("controlplane.nli")


def run_nli(claim: str, evidence_snippets: List[str]) -> Dict[str, Any]:
    """
    Run NLI classification between a claim and evidence snippets.

    Returns:
        {label, confidence, status, reasoning, evidence_used, method}
    """
    if not evidence_snippets:
        return _neutral_result("no_evidence")

    # Use top 3 evidence snippets (best quality first, already sorted by caller)
    best_snippets = [s for s in evidence_snippets[:3] if s.strip()]

    # Try Groq LLM first (most accurate)
    result = _groq_nli(claim, best_snippets)

    # Fall back to heuristics if Groq fails
    if not result:
        logger.warning("Groq NLI unavailable — using heuristic fallback")
        result = _heuristic_nli_result(claim, best_snippets[0])

    return result


def _groq_nli(claim: str, evidence_snippets: List[str]) -> Optional[Dict]:
    """
    Use Groq LLM for NLI classification.
    Significantly more accurate than regex heuristics, especially for:
    - Negation handling ("not", "never", "contrary to")
    - Paraphrase detection
    - Indirect contradictions
    - Multi-hop reasoning
    """
    try:
        import httpx

        api_key = os.getenv("GROQ_API_KEY", "")
        if not api_key:
            return None

        evidence_text = "\n".join(
            f"[{i+1}] {snip[:400]}"
            for i, snip in enumerate(evidence_snippets)
        )

        prompt = f"""You are a precise NLI (Natural Language Inference) classifier.

CLAIM: {claim}

EVIDENCE:
{evidence_text}

Task: Determine if the evidence SUPPORTS, CONTRADICTS, or is NEUTRAL about the claim.

Rules:
- ENTAILMENT: Evidence clearly supports or confirms the claim
- CONTRADICTION: Evidence clearly contradicts or refutes the claim
- NEUTRAL: Evidence is unrelated or insufficient to make a determination

Respond with ONLY valid JSON (no markdown, no explanation outside JSON):
{{
  "label": "ENTAILMENT" | "CONTRADICTION" | "NEUTRAL",
  "confidence": 0.0-1.0,
  "reasoning": "One precise sentence explaining the classification",
  "key_evidence": "Most relevant quote from the evidence (max 100 chars)"
}}"""

        # Use synchronous httpx (NLI runs in thread pool via deep_verify)
        with httpx.Client(timeout=15) as client:
            resp = client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model":       "openai/gpt-oss-20b",
                    "messages":    [{"role": "user", "content": prompt}],
                    "max_tokens":  200,
                    "temperature": 0,  # Deterministic classification
                },
            )

        data = resp.json()
        raw  = data["choices"][0]["message"]["content"].strip()

        # Strip markdown fences if present
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)

        parsed = json.loads(raw)
        label  = parsed.get("label", "NEUTRAL").upper()

        if label not in ("ENTAILMENT", "CONTRADICTION", "NEUTRAL"):
            label = "NEUTRAL"

        status_map = {
            "ENTAILMENT":    "SUPPORTED",
            "CONTRADICTION": "CONTRADICTED",
            "NEUTRAL":       "UNKNOWN",
        }

        logger.info(
            f"NLI (Groq) | label={label} | conf={parsed.get('confidence', 0):.2f} "
            f"| claim='{claim[:60]}'"
        )

        return {
            "label":        label,
            "confidence":   round(float(parsed.get("confidence", 0.7)), 3),
            "status":       status_map[label],
            "reasoning":    parsed.get("reasoning", ""),
            "key_evidence": parsed.get("key_evidence", ""),
            "evidence_used": evidence_snippets[0][:200],
            "method":       "groq_llm",
        }

    except Exception as e:
        logger.warning(f"Groq NLI failed: {e}")
        return None


def _heuristic_nli_result(claim: str, evidence: str) -> Dict:
    """
    Heuristic fallback NLI when Groq is unavailable.
    Uses entity overlap + negation patterns.
    """
    label, confidence = _heuristic_nli(claim, evidence)
    status_map = {
        "ENTAILMENT":    "SUPPORTED",
        "CONTRADICTION": "CONTRADICTED",
        "NEUTRAL":       "UNKNOWN",
    }
    return {
        "label":        label,
        "confidence":   round(confidence, 3),
        "status":       status_map[label],
        "reasoning":    "Heuristic entity overlap analysis",
        "key_evidence": "",
        "evidence_used": evidence[:200],
        "method":       "heuristic_fallback",
    }


def _neutral_result(reason: str) -> Dict:
    return {
        "label":        "NEUTRAL",
        "confidence":   0.5,
        "status":       "UNKNOWN",
        "reasoning":    reason,
        "key_evidence": "",
        "evidence_used": "",
        "method":       "no_evidence",
    }


# ---------------------------------------------------------------------------
# Heuristic fallback (kept for when Groq is unavailable)
# ---------------------------------------------------------------------------

CONTRADICTION_SIGNALS = [
    "however", "but", "although", "despite", "contrary", "incorrect",
    "false", "wrong", "not true", "disputed", "actually", "in fact",
    "instead", "rather", "refute", "debunk", "disprove", "myth",
    "misleading", "inaccurate", "erroneous",
]

ENTAILMENT_SIGNALS = [
    "confirms", "supports", "indeed", "correct", "true", "according to",
    "as stated", "established", "verified", "consistent with", "aligned with",
    "evidence shows", "research confirms", "studies show", "known that",
]


def _heuristic_nli(claim: str, evidence: str) -> tuple:
    claim_lower    = claim.lower()
    evidence_lower = evidence.lower()

    claim_entities    = set(re.findall(r'\b[A-Z][a-z]+\b|\b\d+\b', claim))
    evidence_entities = set(re.findall(r'\b[A-Z][a-z]+\b|\b\d+\b', evidence))

    entity_overlap = len(claim_entities & evidence_entities)
    entity_union   = len(claim_entities | evidence_entities)
    overlap_ratio  = entity_overlap / entity_union if entity_union > 0 else 0

    claim_keywords   = set(re.findall(r'\b\w{5,}\b', claim_lower))
    negated          = any(
        f"not {kw}" in evidence_lower or f"no {kw}" in evidence_lower
        for kw in claim_keywords
    )
    affirmed = any(kw in evidence_lower for kw in claim_keywords)

    has_contradiction = any(s in evidence_lower for s in CONTRADICTION_SIGNALS)
    has_entailment    = any(s in evidence_lower for s in ENTAILMENT_SIGNALS)

    if negated and overlap_ratio > 0.3:
        return "CONTRADICTION", 0.75
    elif has_contradiction and overlap_ratio > 0.2:
        return "CONTRADICTION", 0.65
    elif affirmed and (has_entailment or overlap_ratio > 0.4):
        return "ENTAILMENT", 0.72
    elif overlap_ratio > 0.35:
        return "ENTAILMENT", 0.60
    elif overlap_ratio > 0.15:
        return "NEUTRAL", 0.55
    else:
        return "NEUTRAL", 0.50
