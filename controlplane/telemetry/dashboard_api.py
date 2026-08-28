"""
Dashboard API — REST endpoints for the operator frontend.
"""
import time
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from telemetry.event_store import (
    get_event,
    get_events,
    get_overview_metrics,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/overview")
async def overview():
    """Fleet-level summary metrics."""
    metrics = get_overview_metrics()
    return JSONResponse(content=metrics)


@router.get("/events")
async def events(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    application_id: Optional[str] = None,
    policy_action: Optional[str] = None,
):
    """Paginated event log, most recent first."""
    evts = get_events(
        limit=limit,
        offset=offset,
        application_id=application_id,
        policy_action=policy_action,
    )
    return JSONResponse(content={"events": evts, "count": len(evts)})


@router.get("/events/{event_id}")
async def event_detail(event_id: str):
    """Single event detail with claims and policy decision."""
    ev = get_event(event_id)
    if not ev:
        raise HTTPException(status_code=404, detail="Event not found")
    return JSONResponse(content=ev)


@router.get("/metrics/hallucination")
async def hallucination_metrics():
    """Hallucination / contradiction rate time series."""
    evts = get_events(limit=500)
    # Group by hour
    now = time.time()
    series = []
    for i in range(23, -1, -1):
        bucket_start = now - (i + 1) * 3600
        bucket_end = now - i * 3600
        bucket = [
            e for e in evts
            if bucket_start <= e.get("timestamp", 0) < bucket_end
            and e.get("deep_check_status") == "complete"
        ]
        if bucket:
            avg_contradiction = sum(e.get("contradiction_rate", 0) for e in bucket) / len(bucket)
            avg_risk = sum(e.get("risk_score", 0) for e in bucket) / len(bucket)
        else:
            avg_contradiction = 0
            avg_risk = 0
        series.append({
            "hour": 23 - i,
            "timestamp": int(bucket_end),
            "contradiction_rate": round(avg_contradiction, 3),
            "risk_score": round(avg_risk, 3),
            "sample_count": len(bucket),
        })
    return JSONResponse(content={"series": series})


@router.get("/metrics/cost")
async def cost_metrics():
    """Cost trends and model breakdown."""
    evts = get_events(limit=500)
    # Model breakdown
    model_costs = {}
    for e in evts:
        model = e.get("model_id", "unknown")
        cost = e.get("actual_cost", 0)
        if model not in model_costs:
            model_costs[model] = {"model": model, "total_cost": 0, "request_count": 0}
        model_costs[model]["total_cost"] += cost
        model_costs[model]["request_count"] += 1

    for v in model_costs.values():
        v["total_cost"] = round(v["total_cost"], 4)
        v["avg_cost"] = round(v["total_cost"] / v["request_count"], 6) if v["request_count"] else 0

    # Time series
    now = time.time()
    series = []
    for i in range(23, -1, -1):
        bucket_start = now - (i + 1) * 3600
        bucket_end = now - i * 3600
        bucket = [
            e for e in evts
            if bucket_start <= e.get("timestamp", 0) < bucket_end
        ]
        total_cost = sum(e.get("actual_cost", 0) for e in bucket)
        series.append({
            "hour": 23 - i,
            "timestamp": int(bucket_end),
            "cost_usd": round(total_cost, 4),
            "request_count": len(bucket),
        })

    return JSONResponse(content={
        "model_breakdown": list(model_costs.values()),
        "time_series": series,
    })


@router.get("/metrics/pii")
async def pii_metrics():
    """PII incident rate over time."""
    evts = get_events(limit=500)
    now = time.time()
    series = []
    for i in range(23, -1, -1):
        bucket_start = now - (i + 1) * 3600
        bucket_end = now - i * 3600
        bucket = [e for e in evts if bucket_start <= e.get("timestamp", 0) < bucket_end]
        pii_count = sum(1 for e in bucket if e.get("tier1_pii", {}).get("pii_detected"))
        cred_count = sum(1 for e in bucket if e.get("tier1_pii", {}).get("credentials_detected"))
        series.append({
            "hour": 23 - i,
            "timestamp": int(bucket_end),
            "pii_incidents": pii_count,
            "credential_incidents": cred_count,
            "total_requests": len(bucket),
        })
    return JSONResponse(content={"series": series})


@router.get("/alerts")
async def alerts():
    """Active system alerts."""
    metrics = get_overview_metrics()
    return JSONResponse(content={"alerts": metrics.get("alerts", [])})
