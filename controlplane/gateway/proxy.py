"""
Gateway Proxy — forwards requests to the actual LLM API,
intercepts the response, and returns it with ControlPlane metadata.
"""
import time
import uuid
import json
import logging
from typing import Any, Dict, Optional

import httpx

from config.settings import settings

logger = logging.getLogger("controlplane.proxy")

# Map model prefix to backend base URL
# Current Groq available models (namespaced): openai/gpt-oss-*, qwen/*, groq/compound*
MODEL_BACKENDS: Dict[str, str] = {
    "gpt-":        settings.OPENAI_API_BASE,
    "claude-":     "https://api.anthropic.com/v1",
    "gemini-":     "https://generativelanguage.googleapis.com/v1beta/openai",
    "_groq":       settings.GROQ_API_BASE,
    "_default":    settings.GROQ_API_BASE if settings.GROQ_API_KEY else settings.OPENAI_API_BASE,
}

# Models confirmed available on this Groq account
GROQ_MODELS = {
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
    "groq/compound",
    "groq/compound-mini",
    "qwen/qwen3.6-27b",
    "qwen/qwen3.8-27b",
    "allam-2-7b",
}


def get_backend_url(model: str) -> str:
    if model in GROQ_MODELS:
        return settings.GROQ_API_BASE
    for prefix, url in MODEL_BACKENDS.items():
        if prefix.startswith("_"):
            continue
        if model.startswith(prefix):
            return url
    # Default: use Groq if key available, else OpenAI
    return settings.GROQ_API_BASE if settings.GROQ_API_KEY else settings.OPENAI_API_BASE


def get_api_key(model: str) -> str:
    """Return the correct API key for the given model."""
    if model.startswith("claude-") and settings.ANTHROPIC_API_KEY:
        return settings.ANTHROPIC_API_KEY
    # Default: Groq key if set, else OpenAI key
    if settings.GROQ_API_KEY:
        return settings.GROQ_API_KEY
    return settings.OPENAI_API_KEY


async def forward_to_llm(
    request_body: Dict[str, Any],
    model: str,
) -> Dict[str, Any]:
    """
    Forward the cleaned request to the target LLM API and return the raw response dict.
    Strips the 'controlplane' field before forwarding.
    """
    # Remove ControlPlane-specific fields before forwarding
    forwarded = {k: v for k, v in request_body.items() if k != "controlplane"}

    base_url = get_backend_url(model)
    api_key = get_api_key(model)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    target_url = f"{base_url}/chat/completions"
    logger.info(f"Forwarding to {target_url} | model={model}")

    start = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(target_url, json=forwarded, headers=headers)
            resp.raise_for_status()
            latency_ms = (time.perf_counter() - start) * 1000
            data = resp.json()
            data["_latency_ms"] = latency_ms
            return data
    except httpx.HTTPStatusError as e:
        logger.error(f"LLM API error: {e.response.status_code} — {e.response.text}")
        raise
    except Exception as e:
        logger.error(f"LLM proxy error: {e}")
        raise


async def simulate_llm_response(request_body: Dict[str, Any], model: str) -> Dict[str, Any]:
    """
    Demo-mode simulation — returns a deterministic response without hitting a real API.
    Used for hackathon demo when no API key is available.
    """
    import random

    messages = request_body.get("messages", [])
    user_content = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            user_content = msg.get("content", "")
            break

    # Pre-scripted demo scenarios
    simulated_responses = {
        "telephone": (
            "Thomas Edison invented the telephone in 1876, "
            "revolutionizing long-distance communication."
        ),
        "stress": (
            "Several herbs may help with stress: Ashwagandha, Valerian root, and "
            "St. John's Wort. Note: Do not combine St. John's Wort with SSRIs — "
            "there is a risk of serotonin syndrome."
        ),
        "api key": (
            "Here is how you would use your API key sk-abc123testkey456789xyzabc in Python: "
            "`client = OpenAI(api_key='sk-abc123testkey456789xyzabc')`"
        ),
        "capital": "The capital of France is Paris.",
        "python": (
            "Here is a Python function to calculate factorial:\n"
            "```python\ndef factorial(n):\n    if n == 0:\n        return 1\n"
            "    return n * factorial(n-1)\n```\nThis is a recursive implementation."
        ),
    }

    response_text = "I can help you with that question. Based on my training data, the answer involves multiple considerations that I'll address systematically."
    for key, val in simulated_responses.items():
        if key.lower() in user_content.lower():
            response_text = val
            break

    input_tokens = len(user_content.split()) * 2
    output_tokens = len(response_text.split()) * 2

    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response_text,
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": input_tokens,
            "completion_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        },
        "_latency_ms": random.uniform(200, 800),
        "_simulated": True,
    }
