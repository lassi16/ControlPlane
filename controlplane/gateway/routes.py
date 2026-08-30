"""
Gateway Routes — the main /v1/chat/completions endpoint
and supporting management endpoints.
"""
import time
import uuid
import logging
import random
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from config.settings import settings
from config.model_pricing import MODEL_PRICING
from gateway.proxy import simulate_llm_response, forward_to_llm
from precheck.pii_input import scan_input_pii
from precheck.injection import detect_injection
from precheck.classifier import classify_query
from precheck.impact import estimate_impact
from fast_checks.tier1 import tier1_check
from fast_checks.tier2 import tier2_check
from fast_checks.confidence import confidence_signals
from fast_checks.impact_rescore import rescore_impact
from policy.engine import evaluate_policy
from responsibility.redactor import redact_text
from responsibility.lineage import check_data_lineage
from telemetry.event_store import store_event, update_event

logger = logging.getLogger("controlplane.routes")

router = APIRouter()


# --------------------------------------------------------------------------- #
# Request / Response models
# --------------------------------------------------------------------------- #

class ControlPlaneConfig(BaseModel):
    application_id: str = "default"
    data_classification: str = "internal"
    impact_override: Optional[str] = None
    demo_mode: bool = False  # False = use real API if key available


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = settings.DEFAULT_MODEL
    messages: List[ChatMessage]
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = None
    stream: bool = False
    controlplane: Optional[ControlPlaneConfig] = Field(default_factory=ControlPlaneConfig)


# --------------------------------------------------------------------------- #
# Main proxy endpoint
# --------------------------------------------------------------------------- #

@router.post("/v1/chat/completions")
async def chat_completions(req: ChatCompletionRequest, raw_request: Request):
    request_id = f"req_{uuid.uuid4().hex[:16]}"
    start_time = time.perf_counter()
    cp_config = req.controlplane or ControlPlaneConfig()

    logger.info(f"[{request_id}] Received request | model={req.model} | app={cp_config.application_id}")

    # ------------------------------------------------------------------ #
    # LAYER 0: Pre-checks on INPUT
    # ------------------------------------------------------------------ #
    user_content = " ".join(m.content for m in req.messages if m.role == "user")

    input_pii = scan_input_pii(user_content)
    injection = detect_injection(user_content)
    query_labels = classify_query(user_content)
    impact_prelim = cp_config.impact_override or estimate_impact(
        query_labels, cp_config.application_id
    )

    logger.info(
        f"[{request_id}] Pre-check | pii={len(input_pii)} | "
        f"injection={injection['score']:.2f} | impact={impact_prelim}"
    )

    # Block on injection score — 3+ matched patterns triggers block
    if injection["score"] >= 0.55:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "prompt_injection_detected",
                "message": "Request blocked: high-confidence prompt injection attempt.",
                "injection_score": injection["score"],
                "request_id": request_id,
            },
        )


    # ------------------------------------------------------------------ #
    # FORWARD to LLM
    # ------------------------------------------------------------------ #
    request_dict = req.model_dump()

    # Use real API if any key is configured; fall back to simulation
    has_real_key = bool(settings.GROQ_API_KEY) or (
        settings.OPENAI_API_KEY and not settings.OPENAI_API_KEY.startswith("sk-placeholder")
    )
    use_simulation = cp_config.demo_mode or not has_real_key

    try:
        if use_simulation:
            logger.info(f"[{request_id}] Using simulation mode (no real API key found)")
            llm_response = await simulate_llm_response(request_dict, req.model)
        else:
            logger.info(f"[{request_id}] Calling real API | model={req.model}")
            llm_response = await forward_to_llm(request_dict, req.model)
    except Exception as e:
        logger.warning(f"[{request_id}] Real API failed, falling back to simulation: {e}")
        llm_response = await simulate_llm_response(request_dict, req.model)

    llm_text = ""
    if llm_response.get("choices"):
        llm_text = llm_response["choices"][0].get("message", {}).get("content", "")

    usage = llm_response.get("usage", {})
    input_tokens = usage.get("prompt_tokens", 0)
    output_tokens = usage.get("completion_tokens", 0)
    latency_ms = llm_response.get("_latency_ms", 0)

    # Calculate cost
    pricing = MODEL_PRICING.get(req.model, MODEL_PRICING["_default"])
    actual_cost = (
        input_tokens * pricing["input_per_token"]
        + output_tokens * pricing["output_per_token"]
    )

    # ------------------------------------------------------------------ #
    # LAYER 1: Fast checks on OUTPUT (inline)
    # ------------------------------------------------------------------ #
    tier1_results = tier1_check(llm_text)
    tier2_results = tier2_check(llm_text, user_content)
    confidence = confidence_signals(llm_text)
    impact_rescored = rescore_impact(llm_text, impact_prelim)

    logger.info(
        f"[{request_id}] Fast checks | "
        f"pii={tier1_results['pii_detected']} | "
        f"credentials={tier1_results['credentials_detected']} | "
        f"impact={impact_prelim}→{impact_rescored}"
    )

    # ------------------------------------------------------------------ #
    # DATA LINEAGE CHECK
    # ------------------------------------------------------------------ #
    lineage_result = check_data_lineage(user_content, llm_text, input_pii)
    if lineage_result["leaked"]:
        logger.warning(
            f"[{request_id}] Data lineage: LEAKAGE | "
            f"severity={lineage_result['severity']} | "
            f"items={len(lineage_result['leaked_items'])}"
        )

    # ------------------------------------------------------------------ #
    # POLICY DECISION (inline)
    # ------------------------------------------------------------------ #
    policy_result = evaluate_policy(
        tier1_results=tier1_results,
        tier2_results=tier2_results,
        impact=impact_rescored,
        application_id=cp_config.application_id,
        actual_cost=actual_cost,
        lineage=lineage_result,
    )

    # Apply redaction if needed
    final_text = llm_text
    if policy_result["action"] in ("redact", "block") and tier1_results["detections"]:
        final_text = redact_text(llm_text, tier1_results["detections"])

    if policy_result["action"] == "block":
        final_text = "[RESPONSE BLOCKED BY CONTROLPLANE POLICY]"

    # ------------------------------------------------------------------ #
    # STORE EVENT (async — don't block response)
    # ------------------------------------------------------------------ #
    event_data = {
        "request_id": request_id,
        "application_id": cp_config.application_id,
        "model_id": req.model,
        "user_query": user_content,
        "llm_response": llm_text,
        "query_labels": query_labels,
        "impact_preliminary": impact_prelim,
        "impact_rescored": impact_rescored,
        "tier1_pii": tier1_results,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "actual_cost": actual_cost,
        "policy_action": policy_result["action"],
        "action_details": policy_result,
        "latency_ms": latency_ms,
        "input_pii": input_pii,
        "injection_score": injection["score"],
        "confidence_score": confidence["score"],
        "lineage": lineage_result,
        "deep_check_status": "pending",
    }
    event_id = store_event(event_data)

    # ------------------------------------------------------------------ #
    # DISPATCH DEEP CHECK (async, based on sampling policy)
    # ------------------------------------------------------------------ #
    should_deep_check = _should_deep_check(impact_rescored, tier2_results)
    if should_deep_check:
        try:
            from tasks.deep_verify import deep_verify_task
            deep_verify_task.delay(event_id, llm_text, user_content, query_labels)
        except Exception as e:
            logger.warning(f"[{request_id}] Could not dispatch deep check: {e}")

    # ------------------------------------------------------------------ #
    # BUILD RESPONSE
    # ------------------------------------------------------------------ #
    total_latency = (time.perf_counter() - start_time) * 1000

    response_body = {
        "id": llm_response.get("id", request_id),
        "object": "chat.completion",
        "created": llm_response.get("created", int(time.time())),
        "model": req.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": final_text},
                "finish_reason": "stop",
            }
        ],
        "usage": usage,
        "controlplane": {
            "request_id": request_id,
            "event_id": event_id,
            "policy_action": policy_result["action"],
            "impact": impact_rescored,
            "impact_preliminary": impact_prelim,
            "fast_checks": {
                "pii_detected": tier1_results["pii_detected"],
                "credentials_detected": tier1_results["credentials_detected"],
                "topic_drift": tier2_results.get("topic_drift", 0),
                "confidence": confidence["score"],
                "injection_score": injection["score"],
            },
            "deep_check_status": "queued" if should_deep_check else "skipped",
            "annotations": policy_result.get("annotations", []),
            "cost_usd": actual_cost,
            "latency_ms": total_latency,
        },
    }

    return JSONResponse(content=response_body)


def _should_deep_check(impact: str, tier2_results: Dict) -> bool:
    """Sampling-based gate for deep verification."""
    # Always check if risk signals present
    if tier2_results.get("toxicity_score", 0) > 0.3:
        return True
    if tier2_results.get("topic_drift", 0) > 0.4:
        return True

    # Impact-based sampling
    rates = {
        "critical": settings.SAMPLE_RATE_CRITICAL,
        "high": settings.SAMPLE_RATE_HIGH,
        "medium": settings.SAMPLE_RATE_MEDIUM,
        "low": settings.SAMPLE_RATE_LOW,
    }
    rate = rates.get(impact, settings.SAMPLE_RATE_LOW)
    return random.random() < rate
