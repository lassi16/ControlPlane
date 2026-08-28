"""
Deep Check: Claim Extractor
Extracts atomic factual claims from LLM response text.
Uses Groq API (free) for intelligent extraction, with regex fallback.
"""
import re
import json
import logging
from typing import Any, Dict, List

logger = logging.getLogger("controlplane.claim_extractor")

# Sentence splitter
SENT_SPLIT = re.compile(r'(?<=[.!?])\s+(?=[A-Z])')

OPINION_MARKERS = [
    "i think", "i believe", "in my opinion", "i feel", "it seems to me",
    "arguably", "some argue", "one could say",
]
NUMERICAL_MARKERS = re.compile(
    r'\b\d+[\.,]?\d*\s*(?:%|percent|million|billion|thousand|km|miles|kg|lbs|°|degrees|years?|months?|days?)\b',
    re.IGNORECASE,
)
CAUSAL_MARKERS    = ["because", "therefore", "thus", "hence", "as a result", "leads to", "caused by"]
RECOMMEND_MARKERS = ["should", "must", "recommend", "advised", "you need to", "it is important to"]
CODE_MARKER       = re.compile(r'```[\s\S]*?```|`[^`]+`')


def extract_claims(text: str) -> List[Dict[str, Any]]:
    """
    Extract atomic factual claims from response text.
    Tries Groq API first (better quality), falls back to regex heuristics.
    """
    try:
        claims = _extract_via_groq(text)
        if claims:
            return claims
    except Exception as e:
        logger.warning(f"Groq claim extraction failed, using regex fallback: {e}")

    return _extract_via_regex(text)


def _extract_via_groq(text: str) -> List[Dict[str, Any]]:
    """Use Groq (free) to extract and classify claims intelligently."""
    from config.settings import settings
    if not settings.GROQ_API_KEY:
        return []

    import httpx

    prompt = f"""Extract all factual claims from the following AI response. 
For each claim, output a JSON array with objects having:
- "text": the exact claim sentence
- "type": one of "factual_assertion", "numerical", "causal", "recommendation", "opinion"
- "verifiable": true or false

Only include claims that assert facts. Skip greetings, questions, and filler sentences.
Respond with ONLY a valid JSON array, nothing else.

AI Response:
{text[:1500]}

JSON:"""

    response = httpx.post(
        f"{settings.GROQ_API_BASE}/chat/completions",
        headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}", "Content-Type": "application/json"},
        json={
            "model": "openai/gpt-oss-20b",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": 800,
        },
        timeout=10.0,
    )
    response.raise_for_status()
    raw = response.json()["choices"][0]["message"]["content"].strip()

    # Extract JSON array from response
    match = re.search(r'\[[\s\S]*\]', raw)
    if not match:
        return []
    parsed = json.loads(match.group())

    claims = []
    for item in parsed:
        if not isinstance(item, dict) or not item.get("text"):
            continue
        claim_type = item.get("type", "factual_assertion")
        claims.append({
            "text": item["text"].strip(),
            "type": claim_type,
            "status": "NOT_VERIFIABLE" if claim_type == "opinion" else "pending",
            "evidence": [],
            "nli_result": None,
            "nli_confidence": 0.0,
        })
    return claims


def _extract_via_regex(text: str) -> List[Dict[str, Any]]:
    """Regex + heuristic fallback claim extractor."""
    text_no_code = CODE_MARKER.sub("[CODE_BLOCK]", text)
    sentences = SENT_SPLIT.split(text_no_code)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 20]

    claims = []
    for sent in sentences:
        claim_type = _classify_sentence(sent)
        if claim_type == "skip":
            continue
        claims.append({
            "text": sent,
            "type": claim_type,
            "status": "NOT_VERIFIABLE" if claim_type in ("opinion", "greeting") else "pending",
            "evidence": [],
            "nli_result": None,
            "nli_confidence": 0.0,
        })
    return claims


def _classify_sentence(sentence: str) -> str:
    s = sentence.lower()
    if any(m in s for m in OPINION_MARKERS):
        return "opinion"
    if NUMERICAL_MARKERS.search(sentence):
        return "numerical"
    if any(m in s for m in CAUSAL_MARKERS):
        return "causal"
    if any(m in s for m in RECOMMEND_MARKERS):
        return "recommendation"
    if "[CODE_BLOCK]" in sentence:
        return "code"
    if len(sentence) < 25 or sentence.strip().endswith("?"):
        return "skip"
    return "factual_assertion"
