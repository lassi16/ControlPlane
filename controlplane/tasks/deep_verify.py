"""
Celery Tasks — Deep Verification Worker
Runs asynchronously, off the critical path.
"""
import logging
from typing import Any, Dict, List, Optional

from deep_checks.claim_extractor import extract_claims
from deep_checks.evidence_retriever import retrieve_evidence, score_evidence_quality
from deep_checks.evidence_integrity import scan_all_evidence
from deep_checks.math_verifier import verify_math_claim
from deep_checks.nli_classifier import run_nli
from deep_checks.risk_model import compute_risk_score
from telemetry.event_store import update_event

logger = logging.getLogger("controlplane.tasks")

# Try to import Celery — fall back to synchronous execution if not available
try:
    from celery import Celery
    from config.settings import settings
    celery_app = Celery(
        "controlplane",
        broker=settings.CELERY_BROKER_URL,
        backend=settings.CELERY_RESULT_BACKEND,
    )
    CELERY_AVAILABLE = True
except Exception:
    CELERY_AVAILABLE = False
    celery_app = None
    logger.warning("Celery not available — deep checks will run synchronously")


def _run_deep_verify(event_id: str, response_text: str, query_text: str, query_labels: Dict):
    """Core deep verification logic (runs in worker or synchronously)."""
    logger.info(f"Deep verify starting | event_id={event_id}")

    try:
        # Update status to running
        update_event(event_id, {"deep_check_status": "running"})

        # 1. Extract claims
        claims = extract_claims(response_text)
        logger.info(f"Extracted {len(claims)} claims")

        # 2. Retrieve evidence and run NLI for each verifiable claim
        for claim in claims:
            if claim["status"] == "NOT_VERIFIABLE":
                continue

            # Math claims go to deterministic verifier (no LLM needed)
            if claim["type"] in ("numerical", "mathematical"):
                math_result = verify_math_claim(claim["text"])
                if math_result["status"] != "NOT_VERIFIABLE":
                    claim["status"] = math_result["status"]
                    claim["nli_result"] = math_result["status"]
                    claim["nli_confidence"] = math_result["confidence"]
                    claim["evidence"] = [{
                        "source_url": "internal://math_verifier",
                        "title": "Deterministic Math Verification",
                        "snippet": f"{math_result['expression']} = {math_result['computed_result']} (claimed: {math_result['claimed_result']})",
                        "authority": 1.0,
                        "method": math_result["method"],
                    }]
                    continue

            evidence_list = retrieve_evidence(claim["text"], claim["type"])

            # Score evidence quality
            scored_evidence = []
            for ev in evidence_list:
                quality = score_evidence_quality(ev, claim["text"], query_labels)
                scored_evidence.append({**ev, "quality_score": quality})

            # Scan evidence integrity (adversarial defence)
            scored_evidence = scan_all_evidence(scored_evidence)

            # Filter out unsafe evidence
            safe_evidence = [e for e in scored_evidence if e.get("integrity", {}).get("safe", True)]

            # Sort by quality, take best
            safe_evidence.sort(key=lambda x: x.get("quality_score", 0), reverse=True)
            claim["evidence"] = safe_evidence

            # Run NLI
            snippets = [e["snippet"] for e in safe_evidence if e.get("snippet")]
            if snippets:
                nli_result = run_nli(claim["text"], snippets)
                claim["status"] = nli_result["status"]
                claim["nli_result"] = nli_result["label"]
                claim["nli_confidence"] = nli_result["confidence"]
            else:
                claim["status"] = "UNKNOWN"

        # 3. Compute risk score
        # Get confidence score from event (use 0.5 if not available)
        risk_result = compute_risk_score(claims, confidence_score=0.5)

        # 4. Update event with deep check results
        update_event(event_id, {
            "deep_check_status": "complete",
            "claims": claims,
            "risk_score": risk_result["risk_score"],
            "detector_confidence": risk_result["detector_confidence"],
            "contradiction_rate": risk_result["contradiction_rate"],
            "verification_coverage": risk_result["verification_coverage"],
            "groundedness_score": risk_result["groundedness_score"],
            "claim_summary": risk_result["claim_summary"],
        })

        # 5. Retroactive action: escalate to human review if high risk
        _check_retroactive_action(event_id, risk_result, claims)

        logger.info(f"Deep verify complete | event_id={event_id} | risk={risk_result['risk_score']:.2f}")

    except Exception as e:
        logger.error(f"Deep verify failed | event_id={event_id} | error={e}")
        update_event(event_id, {"deep_check_status": "error", "deep_check_error": str(e)})


def _check_retroactive_action(event_id: str, risk_result: Dict, claims: List[Dict]):
    """If deep check reveals high risk, trigger retroactive alerts and queue for review."""
    contradicted = [c for c in claims if c.get("status") == "CONTRADICTED"]
    if risk_result["risk_score"] > 0.5 or len(contradicted) > 0:
        update_event(event_id, {
            "retroactive_alert": True,
            "retroactive_reason": f"Deep check found {len(contradicted)} contradicted claims, risk={risk_result['risk_score']:.2f}",
        })
        logger.warning(
            f"RETROACTIVE ALERT | event_id={event_id} | "
            f"contradicted={len(contradicted)} | risk={risk_result['risk_score']:.2f}"
        )

    # Route to human review queue
    try:
        from human_review.queue import enqueue_for_review
        enqueue_for_review(
            event_id=event_id,
            risk_score=risk_result["risk_score"],
            detector_confidence=risk_result["detector_confidence"],
            impact="medium",  # Could be passed from event data
            claims=claims,
        )
    except Exception as e:
        logger.warning(f"Review queue failed: {e}")


if CELERY_AVAILABLE:
    @celery_app.task(name="tasks.deep_verify", bind=True, max_retries=2)
    def deep_verify_task(self, event_id: str, response_text: str, query_text: str, query_labels: Dict):
        """Celery task wrapper for deep verification."""
        try:
            _run_deep_verify(event_id, response_text, query_text, query_labels)
        except Exception as exc:
            logger.error(f"Celery task failed: {exc}")
            self.retry(exc=exc, countdown=5)
else:
    class _FakeTask:
        """Synchronous fallback when Celery is not available."""
        def delay(self, event_id, response_text, query_text, query_labels):
            import threading
            t = threading.Thread(
                target=_run_deep_verify,
                args=(event_id, response_text, query_text, query_labels),
                daemon=True,
            )
            t.start()

    deep_verify_task = _FakeTask()
