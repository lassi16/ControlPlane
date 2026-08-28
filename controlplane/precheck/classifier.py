"""
Pre-Check: Query Classifier
Classifies user queries into semantic categories for impact estimation
and routing decisions.
"""
import re
from typing import Dict

# Keyword lists per category (lightweight, no ML model needed for demo)
CATEGORY_KEYWORDS = {
    "factual": [
        "who", "what", "when", "where", "which", "is", "are", "was", "were",
        "invented", "created", "founded", "born", "died", "capital", "country",
        "population", "history", "definition", "explain",
    ],
    "analytical": [
        "why", "how", "analyze", "compare", "contrast", "evaluate", "assess",
        "pros", "cons", "advantages", "disadvantages", "impact", "effect",
        "difference", "between", "relationship",
    ],
    "mathematical": [
        "calculate", "compute", "solve", "equation", "formula", "math",
        "derivative", "integral", "probability", "statistics", "percentage",
        "average", "mean", "median", "mode", r"\d+\s*[+\-*/^]\s*\d+",
    ],
    "code": [
        "code", "program", "function", "script", "python", "javascript",
        "java", "debug", "error", "implement", "algorithm", "sql", "query",
        "api", "library", "class", "method",
    ],
    "creative": [
        "write", "story", "poem", "essay", "creative", "imagine", "fiction",
        "narrative", "character", "plot", "describe", "generate text",
    ],
    "medical": [
        "symptom", "disease", "medication", "drug", "dose", "treatment",
        "diagnosis", "health", "medical", "clinical", "patient", "therapy",
        "side effect", "interaction", "prescription",
    ],
    "financial": [
        "invest", "stock", "bond", "portfolio", "return", "risk", "finance",
        "market", "trading", "crypto", "fund", "asset", "income", "tax",
        "revenue", "profit",
    ],
    "legal": [
        "law", "legal", "rights", "contract", "liability", "regulation",
        "compliance", "court", "attorney", "lawsuit", "statute", "gdpr", "hipaa",
    ],
    "current_info": [
        "latest", "recent", "current", "now", "today", "this year", "2024",
        "2025", "2026", "news", "update", "breaking",
    ],
    "personal": [
        "my name", "i am", "my address", "my phone", "my email", "my password",
        "my account", "my card",
    ],
}

# High-risk domain labels that influence impact scoring
HIGH_RISK_LABELS = {"medical", "financial", "legal"}


def classify_query(text: str) -> Dict[str, float]:
    """
    Multi-label query classification using keyword heuristics.
    Returns probability vector per label.
    In production: replace with a fine-tuned zero-shot classifier.
    """
    text_lower = text.lower()
    scores: Dict[str, float] = {}

    for category, keywords in CATEGORY_KEYWORDS.items():
        hits = 0
        for kw in keywords:
            # Try as regex if it looks like a pattern
            try:
                if re.search(kw, text_lower):
                    hits += 1
            except re.error:
                if kw in text_lower:
                    hits += 1

        # Normalize: more hits = higher score, max at 1.0
        scores[category] = min(hits / max(len(keywords) * 0.15, 1), 1.0)

    # Threshold: keep categories above 0.15
    active = {k: round(v, 3) for k, v in scores.items() if v >= 0.05}

    # Ensure at least one category
    if not active:
        active["general"] = 0.5

    return active
