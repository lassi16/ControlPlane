"""Stub cost tracker for demo mode."""

from config.model_pricing import MODEL_PRICING

def calculate_cost(model_id: str, input_tokens: int, output_tokens: int, tool_calls: int = 0, retries: int = 0) -> float:
    pricing = MODEL_PRICING.get(model_id, MODEL_PRICING["_default"])
    return (
        input_tokens  * pricing["input_per_token"]
        + output_tokens * pricing["output_per_token"]
        + tool_calls    * pricing.get("tool_call", 0)
        + retries       * pricing.get("retry_overhead", 0)
    )
