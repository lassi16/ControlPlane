"""
Telemetry: Baselines & Anomaly Detection

Computes behavioral baselines from historical traffic and detects anomalies
in cost, token usage, and hallucination rates.

Two types of anomaly:
  1. Per-request anomaly: "This single request costs 5x the P90"
  2. Fleet trend anomaly: "Hallucination rate this hour is 3x the 24h average"
"""
import logging
import math
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("controlplane.baselines")


# ---------------------------------------------------------------------------
# Per-request cost anomaly
# ---------------------------------------------------------------------------

def compute_cost_baseline(events: List[Dict]) -> Dict[str, Any]:
    """
    Compute P50, P90, P95 cost baselines from historical events.
    Returns baseline stats and a threshold for anomaly flagging.
    """
    costs = [e.get("actual_cost", 0) for e in events if e.get("actual_cost", 0) > 0]
    tokens = [
        e.get("input_tokens", 0) + e.get("output_tokens", 0)
        for e in events
        if (e.get("input_tokens", 0) + e.get("output_tokens", 0)) > 0
    ]

    if len(costs) < 5:
        return {
            "sufficient_data": False,
            "sample_size": len(costs),
            "message": "Insufficient data for baselines (need 5+ requests)",
        }

    costs_sorted = sorted(costs)
    tokens_sorted = sorted(tokens) if tokens else [0]

    p50_cost = costs_sorted[len(costs_sorted) // 2]
    p90_cost = costs_sorted[int(len(costs_sorted) * 0.9)]
    p95_cost = costs_sorted[int(len(costs_sorted) * 0.95)]
    mean_cost = sum(costs) / len(costs)

    p50_tokens = tokens_sorted[len(tokens_sorted) // 2] if tokens_sorted else 0
    p90_tokens = tokens_sorted[int(len(tokens_sorted) * 0.9)] if tokens_sorted else 0

    return {
        "sufficient_data": True,
        "sample_size": len(costs),
        "cost": {
            "p50": round(p50_cost, 6),
            "p90": round(p90_cost, 6),
            "p95": round(p95_cost, 6),
            "mean": round(mean_cost, 6),
            "anomaly_threshold": round(p90_cost * 3, 6),  # 3x P90
        },
        "tokens": {
            "p50": p50_tokens,
            "p90": p90_tokens,
            "anomaly_threshold": int(p90_tokens * 3),
        },
    }


def check_cost_anomaly(
    actual_cost: float,
    total_tokens: int,
    baseline: Dict,
) -> Dict[str, Any]:
    """
    Check if a single request's cost/tokens are anomalous relative to baseline.
    """
    if not baseline.get("sufficient_data"):
        return {"is_anomaly": False, "reason": "insufficient_baseline_data"}

    cost_threshold = baseline["cost"]["anomaly_threshold"]
    token_threshold = baseline["tokens"]["anomaly_threshold"]

    cost_anomaly = actual_cost > cost_threshold
    token_anomaly = total_tokens > token_threshold

    if cost_anomaly or token_anomaly:
        reasons = []
        if cost_anomaly:
            ratio = actual_cost / baseline["cost"]["p90"] if baseline["cost"]["p90"] > 0 else 0
            reasons.append(f"cost=${actual_cost:.4f} is {ratio:.1f}x the P90 (${baseline['cost']['p90']:.4f})")
        if token_anomaly:
            ratio = total_tokens / baseline["tokens"]["p90"] if baseline["tokens"]["p90"] > 0 else 0
            reasons.append(f"tokens={total_tokens} is {ratio:.1f}x the P90 ({baseline['tokens']['p90']})")

        return {
            "is_anomaly": True,
            "cost_anomaly": cost_anomaly,
            "token_anomaly": token_anomaly,
            "reasons": reasons,
        }

    return {"is_anomaly": False}


# ---------------------------------------------------------------------------
# Fleet trend detection
# ---------------------------------------------------------------------------

def detect_fleet_trends(events: List[Dict]) -> List[Dict]:
    """
    Detect fleet-level trends by comparing recent metrics against
    historical baselines. Returns a list of trend alerts.

    Compares the last 1 hour against the previous 24 hours.
    Requires minimum sample sizes to avoid false alerts.
    """
    if len(events) < 10:
        return []

    now = time.time()
    one_hour_ago = now - 3600
    twenty_four_hours_ago = now - 86400

    recent = [e for e in events if e.get("timestamp", 0) >= one_hour_ago]
    historical = [e for e in events if twenty_four_hours_ago <= e.get("timestamp", 0) < one_hour_ago]

    alerts = []

    # --- Hallucination rate trend ---
    alerts.extend(_check_rate_trend(
        recent, historical,
        metric_name="Hallucination Rate",
        extract_fn=lambda e: e.get("deep_check_status") == "complete",
        rate_fn=lambda e: (e.get("contradiction_rate", 0) or 0) > 0,
        min_sample=3,
        severity_threshold=2.0,  # 2x increase triggers alert
    ))

    # --- Cost trend ---
    recent_costs = [e.get("actual_cost", 0) for e in recent]
    hist_costs = [e.get("actual_cost", 0) for e in historical]

    if len(recent_costs) >= 3 and len(hist_costs) >= 5:
        recent_avg = sum(recent_costs) / len(recent_costs)
        hist_avg = sum(hist_costs) / len(hist_costs) if hist_costs else 0

        if hist_avg > 0 and recent_avg > hist_avg * 2.5:
            ratio = recent_avg / hist_avg
            alerts.append({
                "type": "COST_SPIKE",
                "severity": "high" if ratio > 5 else "medium",
                "message": (
                    f"Avg cost per request increased {ratio:.1f}x "
                    f"(${recent_avg:.4f} vs ${hist_avg:.4f} baseline)"
                ),
                "metric": "cost",
                "current_value": round(recent_avg, 6),
                "baseline_value": round(hist_avg, 6),
                "ratio": round(ratio, 1),
                "timestamp": now,
            })

    # --- PII leakage trend ---
    alerts.extend(_check_rate_trend(
        recent, historical,
        metric_name="PII Leakage",
        extract_fn=lambda e: True,  # all events qualify
        rate_fn=lambda e: bool(e.get("lineage", {}).get("leaked")),
        min_sample=3,
        severity_threshold=2.0,
    ))

    # --- Block rate trend ---
    alerts.extend(_check_rate_trend(
        recent, historical,
        metric_name="Block Rate",
        extract_fn=lambda e: True,
        rate_fn=lambda e: e.get("policy_action") == "block",
        min_sample=3,
        severity_threshold=2.5,
    ))

    return alerts


def _check_rate_trend(
    recent: List[Dict],
    historical: List[Dict],
    metric_name: str,
    extract_fn,
    rate_fn,
    min_sample: int = 3,
    severity_threshold: float = 2.0,
) -> List[Dict]:
    """Check if a rate metric has spiked compared to historical baseline."""
    recent_qualifying = [e for e in recent if extract_fn(e)]
    hist_qualifying = [e for e in historical if extract_fn(e)]

    if len(recent_qualifying) < min_sample or len(hist_qualifying) < min_sample:
        return []

    recent_rate = sum(1 for e in recent_qualifying if rate_fn(e)) / len(recent_qualifying)
    hist_rate = sum(1 for e in hist_qualifying if rate_fn(e)) / len(hist_qualifying)

    # Avoid division by zero — only alert if historical rate was non-zero
    if hist_rate == 0:
        if recent_rate > 0.1:  # More than 10% in recent window with 0% historical
            return [{
                "type": f"{metric_name.upper().replace(' ', '_')}_SPIKE",
                "severity": "high",
                "message": f"{metric_name} emerged at {recent_rate:.0%} (was 0% in baseline)",
                "metric": metric_name.lower().replace(" ", "_"),
                "current_value": round(recent_rate, 3),
                "baseline_value": 0,
                "ratio": None,
                "timestamp": time.time(),
            }]
        return []

    ratio = recent_rate / hist_rate
    if ratio >= severity_threshold:
        return [{
            "type": f"{metric_name.upper().replace(' ', '_')}_SPIKE",
            "severity": "high" if ratio > 3.0 else "medium",
            "message": (
                f"{metric_name} increased {ratio:.1f}x "
                f"({recent_rate:.0%} vs {hist_rate:.0%} baseline)"
            ),
            "metric": metric_name.lower().replace(" ", "_"),
            "current_value": round(recent_rate, 3),
            "baseline_value": round(hist_rate, 3),
            "ratio": round(ratio, 1),
            "timestamp": time.time(),
        }]

    return []
