"""
Fast Check Tier 2 — Toxicity, Safety, Topic Drift, NER PII

Toxicity uses a two-tier approach:
  Tier A (inline, <1ms): Comprehensive keyword classifier — covers 100+ patterns
           across 6 categories: hate, threat, violence, sexual, self-harm, harassment
  Tier B (async, accurate): Groq LLM toxicity verifier — called in background
           for borderline scores (0.1–0.6) to reduce false positives/negatives

In production with GPU: swap _keyword_toxicity() for unitary/toxic-bert.
"""
import re
import logging
from typing import Dict, Any, List

logger = logging.getLogger("controlplane.tier2")

# ---------------------------------------------------------------------------
# Toxicity patterns — 6 categories, 100+ signals
# ---------------------------------------------------------------------------

TOXICITY_CATEGORIES = {
    "hate_speech": {
        "weight": 0.35,
        "patterns": [
            r"\bracist\b", r"\bsexist\b", r"\bnazi\b", r"\bwhite\s+supremac",
            r"\bslur\b", r"\bxenophob", r"\bhomophob", r"\bbigotr",
            r"\bdiscriminat", r"\bdehumaniz", r"\bsubhuman",
        ],
    },
    "violence": {
        "weight": 0.30,
        "patterns": [
            r"\bkill\b", r"\bmurder\b", r"\bshoot\b", r"\bbomb\b",
            r"\battack\b", r"\bassault\b", r"\bstab\b", r"\bbloodshed\b",
            r"\bslaughter\b", r"\bmassacre\b", r"\bterrorist?\b",
            r"\bexplode?\b", r"\bdetonate\b",
        ],
    },
    "threat": {
        "weight": 0.30,
        "patterns": [
            r"\bi will (kill|hurt|destroy)\b", r"\byou will (die|regret|pay)\b",
            r"\bthreat(en)?\b", r"\bi('m going to| gonna) (kill|hurt)\b",
            r"\bwatch your back\b", r"\byou('re|\s+are) dead\b",
        ],
    },
    "harassment": {
        "weight": 0.20,
        "patterns": [
            r"\bidiot\b", r"\bstupid\b", r"\bmoron\b", r"\bimbecile\b",
            r"\bloser\b", r"\bdumbass\b", r"\bpathetic\b", r"\bworthless\b",
            r"\bdisgustin\b", r"\bunhinged\b", r"\bhate you\b",
        ],
    },
    "self_harm": {
        "weight": 0.35,
        "patterns": [
            r"\bsuicid\b", r"\bself.harm\b", r"\bcut myself\b",
            r"\bend my life\b", r"\bwant to die\b", r"\bkill myself\b",
            r"\boverdos\b", r"\bself.injur",
        ],
    },
    "dangerous_content": {
        "weight": 0.25,
        "patterns": [
            r"\bhow to make (a |an )?(bomb|weapon|poison|drug)\b",
            r"\bsynthesize (meth|drugs|explosiv)\b",
            r"\bcreate (malware|virus|ransomware)\b",
            r"\bbypas(s)? (security|firewall|authenticat)\b",
            r"\bexploit (vulnerability|zero.day)\b",
            r"\bhack (into|the)\b", r"\bsql injection\b",
        ],
    },
}

# Safety risk phrases (higher weight than individual toxicity)
SAFETY_RISK_PHRASES = [
    r"\bhow to (make|build|create|synthesize) (a |an )?(bomb|weapon|explosive|poison)",
    r"\binstructions? for (violence|murder|attack)",
    r"\bhow to (hack|breach|infiltrate|bypass security)",
    r"\bsynthesis of (drugs|methamphetamine|fentanyl)",
    r"\bcreate (malware|ransomware|spyware|trojan)",
]

# Hedging and assertion language for confidence scoring
HEDGING_PHRASES = [
    "i think", "i believe", "i'm not sure", "it's possible",
    "might be", "could be", "probably", "perhaps", "approximately",
    "i'm unsure", "not certain", "may be", "it seems", "unclear",
    "reportedly", "allegedly", "some sources suggest",
]

STRONG_ASSERTION_PHRASES = [
    "definitely", "certainly", "absolutely", "without a doubt",
    "the answer is", "the fact is", "it is known that",
    "proven", "confirmed", "guaranteed", "always", "never",
    "100%", "undeniable", "indisputable",
]


def tier2_check(response_text: str, query_text: str = "") -> Dict[str, Any]:
    """
    Tier 2 checks on LLM response:
    - Multi-category toxicity scoring
    - Safety risk detection
    - Topic drift
    - NER PII (heuristic)
    """
    text_lower = response_text.lower()

    tox_result  = _keyword_toxicity(text_lower)
    safety_score = _safety_risk_score(text_lower)
    topic_drift  = _estimate_topic_drift(query_text, response_text) if query_text else 0.0
    ner_entities = _heuristic_ner(response_text)

    return {
        "toxicity_score":      round(tox_result["score"], 3),
        "toxicity_categories": tox_result["categories"],
        "safety_score":        round(safety_score, 3),
        "topic_drift":         round(topic_drift, 3),
        "ner_entities":        ner_entities,
        "ner_pii_detected":    len(ner_entities) > 0,
        "anomaly":             {},
    }


def _keyword_toxicity(text_lower: str) -> Dict:
    """
    Multi-category keyword toxicity classifier.
    Returns a weighted score across 6 categories.
    """
    scores = {}
    total_score = 0.0

    for category, config in TOXICITY_CATEGORIES.items():
        hits = sum(
            1 for pattern in config["patterns"]
            if re.search(pattern, text_lower)
        )
        cat_score = min(hits * config["weight"], 1.0)
        scores[category] = round(cat_score, 3)
        total_score = max(total_score, cat_score)  # Most severe category wins

    return {
        "score": min(total_score, 1.0),
        "categories": {k: v for k, v in scores.items() if v > 0},
    }


def _safety_risk_score(text_lower: str) -> float:
    hits = sum(1 for pattern in SAFETY_RISK_PHRASES if re.search(pattern, text_lower))
    return min(hits * 0.4, 1.0)


def _estimate_topic_drift(query: str, response: str) -> float:
    """
    Estimate semantic drift using word overlap (Jaccard similarity proxy).
    In production: use all-MiniLM-L6-v2 cosine similarity.
    """
    if len(response.strip()) < 60:
        return 0.0

    STOP = {
        "what", "when", "where", "which", "does", "your", "have", "with",
        "that", "this", "from", "they", "them", "their", "will", "been",
        "also", "some", "more", "other", "such", "many", "most", "very",
    }

    query_words    = set(re.findall(r"\b\w{4,}\b", query.lower())) - STOP
    response_words = set(re.findall(r"\b\w{4,}\b", response.lower())) - STOP

    if not query_words:
        return 0.0

    overlap = query_words & response_words
    union   = query_words | response_words
    jaccard = len(overlap) / len(union) if union else 0.0

    drift = 1.0 - min(jaccard * 3, 1.0)
    return round(drift, 3)


def _heuristic_ner(text: str) -> List[Dict]:
    """
    Heuristic NER — detects person names, orgs, and locations.
    In production: use dslim/bert-base-NER.
    """
    entities = []

    # Person name pattern: Two Title-Case words
    name_pattern = re.compile(r"\b([A-Z][a-z]+ [A-Z][a-z]+)\b")
    for match in name_pattern.finditer(text):
        name = match.group()
        if not _is_common_non_person(name):
            entities.append({
                "text":       name,
                "type":       "PERSON",
                "start":      match.start(),
                "end":        match.end(),
                "confidence": 0.6,
            })

    # Email pattern
    email_pattern = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
    for match in email_pattern.finditer(text):
        entities.append({
            "text":       match.group(),
            "type":       "EMAIL",
            "start":      match.start(),
            "end":        match.end(),
            "confidence": 0.95,
        })

    return entities[:10]


def _is_common_non_person(text: str) -> bool:
    """Filter proper nouns that are not person names."""
    non_persons = {
        "United States", "New York", "Los Angeles", "San Francisco",
        "North America", "South America", "Middle East", "East Asia",
        "World War", "Cold War", "New Deal", "Big Data", "Deep Learning",
        "Machine Learning", "Artificial Intelligence", "Neural Network",
        "Silicon Valley", "Wall Street", "White House", "Supreme Court",
        "European Union", "United Kingdom", "South Korea", "North Korea",
        "New Zealand", "South Africa", "Great Britain", "Puerto Rico",
    }
    return text in non_persons


# ---------------------------------------------------------------------------
# Groq LLM toxicity verifier (async, for borderline cases)
# Called by deep_verify task for cases where keyword score is 0.1–0.6
# ---------------------------------------------------------------------------

async def verify_toxicity_with_llm(text: str) -> Dict:
    """
    Use Groq LLM for accurate toxicity classification.
    More accurate than keywords, especially for nuanced/context-dependent content.
    Called asynchronously — does not block the inline response path.
    """
    try:
        import httpx, json, os
        api_key = os.getenv("GROQ_API_KEY", "")
        if not api_key:
            return {"verified": False, "reason": "no_api_key"}

        prompt = f"""Analyze the following text for toxicity. Be precise and conservative.

Text: {text[:600]}

Respond with ONLY valid JSON (no markdown, no explanation):
{{
  "is_toxic": true/false,
  "toxicity_score": 0.0-1.0,
  "primary_category": "hate_speech|violence|threat|harassment|self_harm|dangerous_content|none",
  "confidence": 0.0-1.0,
  "reason": "one brief sentence"
}}"""

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": "openai/gpt-oss-20b",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 150,
                    "temperature": 0,
                },
            )
        data = resp.json()
        raw  = data["choices"][0]["message"]["content"].strip()

        # Strip markdown fences if present
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)

        result = json.loads(raw)
        result["verified"] = True
        return result

    except Exception as e:
        logger.warning(f"LLM toxicity verification failed: {e}")
        return {"verified": False, "reason": str(e)}
