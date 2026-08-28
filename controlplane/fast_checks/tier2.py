"""
Fast Check Tier 2 — ML-Based Checks on LLM Response
Runs inline but uses lightweight local classifiers.

In demo / no-GPU mode: uses rule-based heuristics instead of loading models.
In production: loads HuggingFace models lazily on first call.
"""
import re
import logging
from typing import Dict, Any, List

logger = logging.getLogger("controlplane.tier2")

# ---------------------------------------------------------------------------
# Toxicity signals (rule-based for demo — replace with toxic-bert in prod)
# ---------------------------------------------------------------------------
TOXIC_WORDS = [
    "idiot", "stupid", "moron", "hate", "kill", "attack", "bomb",
    "racist", "sexist", "discriminate", "slur", "harassment",
    "violent", "murder", "abuse", "threat",
]

SAFETY_RISK_PHRASES = [
    "how to make a bomb", "how to hack", "how to steal",
    "instructions for violence", "how to poison",
    "bypass security", "exploit vulnerability",
    "synthesize drugs", "create malware",
]

# Hedging and assertion language for confidence scoring
HEDGING_PHRASES = [
    "i think", "i believe", "i'm not sure", "it's possible",
    "might be", "could be", "probably", "perhaps", "approximately",
    "i'm unsure", "not certain", "may be", "it seems",
]

STRONG_ASSERTION_PHRASES = [
    "definitely", "certainly", "absolutely", "without a doubt",
    "the answer is", "the fact is", "it is known that",
    "proven", "confirmed", "guaranteed",
]


def tier2_check(response_text: str, query_text: str = "") -> Dict[str, Any]:
    """
    ML-based checks using rule-based approximations:
    - Toxicity score
    - Safety risk score
    - Topic drift (semantic similarity proxy)
    - NER PII (simulated)
    """
    text_lower = response_text.lower()

    # Toxicity score
    toxic_hits = sum(1 for w in TOXIC_WORDS if w in text_lower)
    toxicity_score = min(toxic_hits * 0.15, 1.0)

    # Safety risk score
    safety_hits = sum(1 for phrase in SAFETY_RISK_PHRASES if phrase in text_lower)
    safety_score = min(safety_hits * 0.4, 1.0)

    # Topic drift — simple word-overlap heuristic
    topic_drift = _estimate_topic_drift(query_text, response_text) if query_text else 0.0

    # NER-based PII (heuristic for demo — in prod: dslim/bert-base-NER)
    ner_entities = _heuristic_ner(response_text)

    return {
        "toxicity_score": round(toxicity_score, 3),
        "safety_score": round(safety_score, 3),
        "topic_drift": round(topic_drift, 3),
        "ner_entities": ner_entities,
        "ner_pii_detected": len(ner_entities) > 0,
        "anomaly": {},
    }


def _estimate_topic_drift(query: str, response: str) -> float:
    """
    Estimate semantic drift using word overlap (Jaccard similarity proxy).
    In production: use all-MiniLM-L6-v2 cosine similarity.
    """
    # Short correct answers (e.g. "Paris.") are not topic drift
    if len(response.strip()) < 60:
        return 0.0

    # Exclude common question words that add noise
    STOP = {"what", "when", "where", "which", "does", "your", "have", "with",
            "that", "this", "from", "they", "them", "their", "will", "been"}

    query_words    = set(re.findall(r"\b\w{4,}\b", query.lower()))    - STOP
    response_words = set(re.findall(r"\b\w{4,}\b", response.lower())) - STOP

    if not query_words:
        return 0.0

    overlap = query_words & response_words
    union   = query_words | response_words
    jaccard = len(overlap) / len(union) if union else 0.0

    # High similarity = low drift; low similarity = high drift
    drift = 1.0 - min(jaccard * 3, 1.0)
    return round(drift, 3)


def _heuristic_ner(text: str) -> List[Dict]:
    """
    Heuristic NER for person names and organizations.
    In production: use dslim/bert-base-NER.
    """
    entities = []

    # Capitalized sequences that look like names (simple heuristic)
    name_pattern = re.compile(r"\b([A-Z][a-z]+ [A-Z][a-z]+)\b")
    for match in name_pattern.finditer(text):
        # Exclude common false positives
        name = match.group()
        if not _is_common_proper_noun(name):
            entities.append({
                "text": name,
                "type": "PERSON",
                "start": match.start(),
                "end": match.end(),
                "confidence": 0.6,
            })

    return entities[:10]  # Cap at 10 entities


def _is_common_proper_noun(text: str) -> bool:
    """Filter out common proper nouns that are not person names."""
    common = {
        "United States", "New York", "Los Angeles", "San Francisco",
        "North America", "South America", "Middle East", "East Asia",
        "World War", "Cold War", "New Deal", "Big Data",
        "Machine Learning", "Artificial Intelligence",
    }
    return text in common
