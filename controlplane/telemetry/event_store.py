"""
Telemetry: Event Store
Wraps the async DB layer with a sync-compatible interface so existing
gateway code (routes.py) needs zero changes.

Storage backends (auto-selected):
  - No Docker / local dev  → SQLite  (data/events.db)
  - Docker / production    → PostgreSQL
"""
import asyncio
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from telemetry.db import (
    db_count_events, db_get_event, db_get_events,
    db_store_event, db_update_event, init_db,
)

logger = logging.getLogger("controlplane.event_store")

# ── Initialise DB on first use ────────────────────────────────────────────────
_DB_READY = False

def _ensure_db():
    """Run DB init synchronously if not yet done (called lazily on first use)."""
    global _DB_READY
    if _DB_READY:
        return
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Inside async context (FastAPI startup) — schedule init
            asyncio.ensure_future(init_db())
        else:
            loop.run_until_complete(init_db())
        _DB_READY = True
    except Exception as e:
        logger.error(f"DB init failed: {e}")


def _run(coro):
    """Run an async coroutine from sync code safely."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result(timeout=10)
        return loop.run_until_complete(coro)
    except Exception as e:
        logger.error(f"DB operation failed: {e}")
        return None


# ── Public API ────────────────────────────────────────────────────────────────

def store_event(event_data: Dict[str, Any]) -> str:
    """Store an event and return its ID."""
    _ensure_db()
    event_id = str(uuid.uuid4())
    event_data["id"] = event_id
    event_data.setdefault("timestamp", time.time())
    _run(db_store_event(event_data))
    return event_id


def update_event(event_id: str, updates: Dict[str, Any]) -> bool:
    """Update an existing event (deep-check results, policy updates)."""
    _ensure_db()
    result = _run(db_update_event(event_id, updates))
    return bool(result)


def get_event(event_id: str) -> Optional[Dict]:
    """Fetch a single event by ID."""
    _ensure_db()
    return _run(db_get_event(event_id))


def get_events(
    limit: int = 50,
    offset: int = 0,
    application_id: Optional[str] = None,
    policy_action: Optional[str] = None,
) -> List[Dict]:
    """Get paginated events, most recent first."""
    _ensure_db()
    return _run(db_get_events(limit, offset, application_id, policy_action)) or []


def get_overview_metrics() -> Dict[str, Any]:
    """Aggregate fleet-level summary metrics from DB."""
    _ensure_db()
    all_events = _run(db_get_events(limit=5000, offset=0)) or []

    if not all_events:
        return _empty_overview()

    total   = len(all_events)
    actions = [e.get("policy_action", "allow") for e in all_events]
    blocked   = actions.count("block")
    redacted  = actions.count("redact")
    annotated = actions.count("annotate")
    escalated = actions.count("escalate")

    costs      = [e.get("actual_cost", 0) for e in all_events]
    total_cost = sum(costs)

    deep_done = [e for e in all_events if e.get("deep_check_status") == "complete"]
    contradiction_rates = [
        e.get("contradiction_rate", 0)
        for e in deep_done
        if e.get("contradiction_rate") is not None
    ]
    hallucination_rate = (
        sum(1 for r in contradiction_rates if r > 0) / len(contradiction_rates)
        if contradiction_rates else 0.0
    )

    pii_incidents = sum(1 for e in all_events if e.get("tier1_pii", {}).get("pii_detected"))
    impacts = [e.get("impact_rescored", "medium") for e in all_events]
    impact_dist = {
        "low":      impacts.count("low"),
        "medium":   impacts.count("medium"),
        "high":     impacts.count("high"),
        "critical": impacts.count("critical"),
    }

    alerts     = _get_active_alerts(all_events)
    time_series = _compute_time_series(all_events)

    return {
        "total_requests":       total,
        "blocked":              blocked,
        "redacted":             redacted,
        "annotated":            annotated,
        "escalated":            escalated,
        "allowed":              total - blocked - redacted - annotated - escalated,
        "total_cost_usd":       round(total_cost, 4),
        "avg_cost_per_request": round(total_cost / total, 6) if total else 0,
        "hallucination_rate":   round(hallucination_rate, 3),
        "pii_incidents":        pii_incidents,
        "impact_distribution":  impact_dist,
        "alerts":               alerts,
        "time_series":          time_series,
        "deep_checks_complete": len(deep_done),
        "deep_checks_pending":  sum(1 for e in all_events if e.get("deep_check_status") == "pending"),
    }


# ── Internal helpers ─────────────────────────────────────────────────────────

def _get_active_alerts(events: List[Dict]) -> List[Dict]:
    alerts  = []
    recent  = events[:20]
    blocked = [e for e in recent if e.get("policy_action") == "block"]
    if len(blocked) >= 3:
        alerts.append({
            "type": "HIGH_BLOCK_RATE", "severity": "high",
            "message": f"{len(blocked)} requests blocked in recent traffic",
            "timestamp": time.time(),
        })
    pii_recent = [e for e in recent if e.get("tier1_pii", {}).get("pii_detected")]
    if len(pii_recent) >= 2:
        alerts.append({
            "type": "PII_SPIKE", "severity": "medium",
            "message": f"{len(pii_recent)} PII incidents in recent traffic",
            "timestamp": time.time(),
        })
    return alerts


def _compute_time_series(events: List[Dict]) -> List[Dict]:
    now = time.time()
    buckets = []
    for i in range(23, -1, -1):
        start = now - (i + 1) * 3600
        end   = now - i * 3600
        bkt   = [e for e in events if start <= e.get("timestamp", 0) < end]
        buckets.append({
            "hour":        23 - i,
            "timestamp":   int(end),
            "requests":    len(bkt),
            "blocked":     sum(1 for e in bkt if e.get("policy_action") == "block"),
            "pii_incidents": sum(1 for e in bkt if e.get("tier1_pii", {}).get("pii_detected")),
            "cost_usd":    round(sum(e.get("actual_cost", 0) for e in bkt), 4),
        })
    return buckets


def _empty_overview() -> Dict:
    return {
        "total_requests": 0, "blocked": 0, "redacted": 0,
        "annotated": 0, "escalated": 0, "allowed": 0,
        "total_cost_usd": 0, "avg_cost_per_request": 0,
        "hallucination_rate": 0, "pii_incidents": 0,
        "impact_distribution": {"low":0,"medium":0,"high":0,"critical":0},
        "alerts": [], "time_series": [],
        "deep_checks_complete": 0, "deep_checks_pending": 0,
    }
