"""
Telemetry: In-Memory Event Store
In production: replace with PostgreSQL + asyncpg.
Stores only real traffic events — no fake seeding in prototype mode.
"""
import uuid
import time
import threading
from typing import Any, Dict, List, Optional
from collections import deque

_lock = threading.Lock()

# In-memory stores
_events: Dict[str, Dict] = {}
_events_order: deque = deque(maxlen=10000)  # Keep last 10k events

def store_event(event_data: Dict[str, Any]) -> str:
    """Store an event and return its ID."""

    event_id = str(uuid.uuid4())
    event_data["id"] = event_id
    event_data["timestamp"] = time.time()

    with _lock:

        _events[event_id] = event_data
        _events_order.appendleft(event_id)

    return event_id


def update_event(event_id: str, updates: Dict[str, Any]) -> bool:
    """Update an existing event with deep-check results."""
    with _lock:
        if event_id in _events:
            _events[event_id].update(updates)
            return True
    return False


def get_event(event_id: str) -> Optional[Dict]:
    with _lock:
        return _events.get(event_id)


def get_events(
    limit: int = 50,
    offset: int = 0,
    application_id: Optional[str] = None,
    policy_action: Optional[str] = None,
) -> List[Dict]:
    """Get paginated events, most recent first."""
    with _lock:
        all_ids = list(_events_order)

    events = []
    for eid in all_ids:
        ev = _events.get(eid)
        if ev is None:
            continue
        if application_id and ev.get("application_id") != application_id:
            continue
        if policy_action and ev.get("policy_action") != policy_action:
            continue
        events.append(ev)

    return events[offset: offset + limit]


def get_overview_metrics() -> Dict[str, Any]:
    """Aggregate fleet-level summary metrics."""
    with _lock:
        all_events = list(_events.values())

    if not all_events:
        return _empty_overview()

    total = len(all_events)
    actions = [e.get("policy_action", "allow") for e in all_events]
    blocked = actions.count("block")
    redacted = actions.count("redact")
    annotated = actions.count("annotate")
    escalated = actions.count("escalate")

    # Cost
    costs = [e.get("actual_cost", 0) for e in all_events]
    total_cost = sum(costs)

    # Hallucination rate (from deep checks)
    deep_done = [e for e in all_events if e.get("deep_check_status") == "complete"]
    contradiction_rates = [e.get("contradiction_rate", 0) for e in deep_done if e.get("contradiction_rate") is not None]
    hallucination_rate = (
        sum(1 for r in contradiction_rates if r > 0) / len(contradiction_rates)
        if contradiction_rates else 0.0
    )

    # PII incidents
    pii_incidents = sum(1 for e in all_events if e.get("tier1_pii", {}).get("pii_detected"))

    # Impact distribution
    impacts = [e.get("impact_rescored", "medium") for e in all_events]
    impact_dist = {
        "low": impacts.count("low"),
        "medium": impacts.count("medium"),
        "high": impacts.count("high"),
        "critical": impacts.count("critical"),
    }

    # Alerts
    alerts = _get_active_alerts(all_events)

    # Time series (last 24 data points — hourly buckets)
    time_series = _compute_time_series(all_events)

    return {
        "total_requests": total,
        "blocked": blocked,
        "redacted": redacted,
        "annotated": annotated,
        "escalated": escalated,
        "allowed": total - blocked - redacted - annotated - escalated,
        "total_cost_usd": round(total_cost, 4),
        "avg_cost_per_request": round(total_cost / total, 6) if total > 0 else 0,
        "hallucination_rate": round(hallucination_rate, 3),
        "pii_incidents": pii_incidents,
        "impact_distribution": impact_dist,
        "alerts": alerts,
        "time_series": time_series,
        "deep_checks_complete": len(deep_done),
        "deep_checks_pending": sum(1 for e in all_events if e.get("deep_check_status") == "pending"),
    }


def _get_active_alerts(events: List[Dict]) -> List[Dict]:
    alerts = []
    recent = events[:20]
    blocked = [e for e in recent if e.get("policy_action") == "block"]
    if len(blocked) >= 3:
        alerts.append({
            "type": "HIGH_BLOCK_RATE",
            "severity": "high",
            "message": f"{len(blocked)} requests blocked in recent traffic",
            "timestamp": time.time(),
        })
    pii_recent = [e for e in recent if e.get("tier1_pii", {}).get("pii_detected")]
    if len(pii_recent) >= 2:
        alerts.append({
            "type": "PII_SPIKE",
            "severity": "medium",
            "message": f"{len(pii_recent)} PII incidents in recent traffic",
            "timestamp": time.time(),
        })
    return alerts


def _compute_time_series(events: List[Dict]) -> List[Dict]:
    """Compute hourly aggregates for the last 24 hours."""
    now = time.time()
    buckets = []
    for i in range(23, -1, -1):
        bucket_start = now - (i + 1) * 3600
        bucket_end = now - i * 3600
        bucket_events = [
            e for e in events
            if bucket_start <= e.get("timestamp", 0) < bucket_end
        ]
        blocked_count = sum(1 for e in bucket_events if e.get("policy_action") == "block")
        pii_count = sum(1 for e in bucket_events if e.get("tier1_pii", {}).get("pii_detected"))
        cost = sum(e.get("actual_cost", 0) for e in bucket_events)
        buckets.append({
            "hour": 23 - i,
            "timestamp": int(bucket_end),
            "requests": len(bucket_events),
            "blocked": blocked_count,
            "pii_incidents": pii_count,
            "cost_usd": round(cost, 4),
        })
    return buckets


def _empty_overview() -> Dict:
    return {
        "total_requests": 0,
        "blocked": 0,
        "redacted": 0,
        "annotated": 0,
        "escalated": 0,
        "allowed": 0,
        "total_cost_usd": 0,
        "avg_cost_per_request": 0,
        "hallucination_rate": 0,
        "pii_incidents": 0,
        "impact_distribution": {"low": 0, "medium": 0, "high": 0, "critical": 0},
        "alerts": [],
        "time_series": [],
        "deep_checks_complete": 0,
        "deep_checks_pending": 0,
    }


def _seed_demo_data():
    """Seed realistic demo events for a compelling dashboard presentation."""
    import random
    random.seed(42)

    models = ["gpt-4", "gpt-3.5-turbo", "claude-3-sonnet", "gemini-1.5-flash"]
    apps = ["customer_support", "internal_kb", "decision_support"]
    actions = ["allow", "allow", "allow", "allow", "annotate", "annotate", "redact", "block", "warn", "escalate"]
    impacts = ["low", "low", "medium", "medium", "medium", "high", "high", "critical"]

    sample_queries = [
        "Who invented the telephone?",
        "What are the side effects of aspirin?",
        "Calculate the ROI on a $10,000 investment at 8% over 5 years",
        "My email is john.smith@example.com, help me draft a response",
        "Explain quantum entanglement",
        "What herbs help with stress?",
        "Write me a Python function to sort a list",
        "What is the capital of France?",
        "Explain the GDPR data retention rules",
        "Help me analyze this financial report",
    ]

    sample_responses = [
        "Thomas Edison invented the telephone in 1876, revolutionizing communication.",
        "Aspirin can cause stomach irritation, bleeding risk, and allergic reactions.",
        "At 8% annual return, $10,000 grows to $14,693.28 over 5 years.",
        "Dear colleague, thank you for your inquiry. sk-abc123testkey456789xyzabc",
        "Quantum entanglement is a phenomenon where particles become correlated...",
        "St. John's Wort should not be combined with SSRIs due to serotonin syndrome risk.",
        "def sort_list(lst): return sorted(lst)",
        "The capital of France is Paris.",
        "GDPR requires data to be kept no longer than necessary for its purpose.",
        "Based on the financial report, revenue grew 12% YoY with strong margins.",
    ]

    now = time.time()

    for i in range(150):
        qi = i % len(sample_queries)
        hours_ago = random.uniform(0, 23)
        ts = now - hours_ago * 3600

        action = random.choice(actions)
        impact = random.choice(impacts)
        model = random.choice(models)
        app = random.choice(apps)
        cost = random.uniform(0.0001, 0.05)
        input_tokens = random.randint(20, 200)
        output_tokens = random.randint(30, 400)
        tox = random.uniform(0, 0.15) if action != "block" else random.uniform(0.5, 0.9)
        pii = action in ("redact", "block") and random.random() > 0.5

        event_id = str(uuid.uuid4())
        _events[event_id] = {
            "id": event_id,
            "timestamp": ts,
            "request_id": f"req_{uuid.uuid4().hex[:12]}",
            "application_id": app,
            "model_id": model,
            "user_query": sample_queries[qi],
            "llm_response": sample_responses[qi],
            "impact_rescored": impact,
            "impact_preliminary": impact,
            "policy_action": action,
            "actual_cost": round(cost, 6),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "tier1_pii": {"pii_detected": pii, "credentials_detected": pii and random.random() > 0.7},
            "tier2_toxicity": round(tox, 3),
            "tier2_safety": round(random.uniform(0, 0.1), 3),
            "injection_score": round(random.uniform(0, 0.1), 3),
            "confidence_score": round(random.uniform(0.3, 0.9), 3),
            "deep_check_status": random.choice(["complete", "complete", "pending", "skipped"]),
            "contradiction_rate": round(random.uniform(0, 0.4), 3) if action in ("annotate", "block") else 0,
            "risk_score": round(random.uniform(0.1, 0.8), 3) if action != "allow" else round(random.uniform(0, 0.2), 3),
            "verification_coverage": round(random.uniform(0.5, 1.0), 3),
            "claims": _sample_claims(action),
        }
        _events_order.appendleft(event_id)


def _sample_claims(action: str):
    base = [
        {"text": "The telephone was invented in 1876", "status": "SUPPORTED", "type": "factual"},
        {"text": "Thomas Edison invented it", "status": "CONTRADICTED" if action in ("block", "annotate") else "SUPPORTED", "type": "factual"},
    ]
    return base
