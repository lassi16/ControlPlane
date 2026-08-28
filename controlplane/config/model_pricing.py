"""
Model Pricing Table — per token (USD)
Used by cost/tracker.py to calculate actual spend.
"""

MODEL_PRICING = {
    # OpenAI
    "gpt-4": {
        "input_per_token": 30e-6,   # $30 / 1M tokens
        "output_per_token": 60e-6,  # $60 / 1M tokens
        "tool_call": 0.001,
        "retry_overhead": 0.0,
    },
    "gpt-4-turbo": {
        "input_per_token": 10e-6,
        "output_per_token": 30e-6,
        "tool_call": 0.001,
        "retry_overhead": 0.0,
    },
    "gpt-3.5-turbo": {
        "input_per_token": 0.5e-6,
        "output_per_token": 1.5e-6,
        "tool_call": 0.0005,
        "retry_overhead": 0.0,
    },
    # Anthropic
    "claude-3-opus": {
        "input_per_token": 15e-6,
        "output_per_token": 75e-6,
        "tool_call": 0.001,
        "retry_overhead": 0.0,
    },
    "claude-3-sonnet": {
        "input_per_token": 3e-6,
        "output_per_token": 15e-6,
        "tool_call": 0.0005,
        "retry_overhead": 0.0,
    },
    "claude-3-haiku": {
        "input_per_token": 0.25e-6,
        "output_per_token": 1.25e-6,
        "tool_call": 0.0001,
        "retry_overhead": 0.0,
    },
    # Google
    "gemini-1.5-pro": {
        "input_per_token": 3.5e-6,
        "output_per_token": 10.5e-6,
        "tool_call": 0.0005,
        "retry_overhead": 0.0,
    },
    "gemini-1.5-flash": {
        "input_per_token": 0.075e-6,
        "output_per_token": 0.3e-6,
        "tool_call": 0.0001,
        "retry_overhead": 0.0,
    },
    # ------------------------------------------------------------------ #
    # Groq (FREE tier — extremely fast inference)
    # https://console.groq.com/docs/models
    # ------------------------------------------------------------------ #
    "llama-3.1-8b-instant": {
        "input_per_token": 0.05e-6,   # $0.05 / 1M tokens
        "output_per_token": 0.08e-6,  # $0.08 / 1M tokens
        "tool_call": 0.0,
        "retry_overhead": 0.0,
    },
    "llama-3.3-70b-versatile": {
        "input_per_token": 0.59e-6,
        "output_per_token": 0.79e-6,
        "tool_call": 0.0,
        "retry_overhead": 0.0,
    },
    "llama3-8b-8192": {
        "input_per_token": 0.05e-6,
        "output_per_token": 0.08e-6,
        "tool_call": 0.0,
        "retry_overhead": 0.0,
    },
    "llama3-70b-8192": {
        "input_per_token": 0.59e-6,
        "output_per_token": 0.79e-6,
        "tool_call": 0.0,
        "retry_overhead": 0.0,
    },
    "mixtral-8x7b-32768": {
        "input_per_token": 0.24e-6,
        "output_per_token": 0.24e-6,
        "tool_call": 0.0,
        "retry_overhead": 0.0,
    },
    "gemma2-9b-it": {
        "input_per_token": 0.20e-6,
        "output_per_token": 0.20e-6,
        "tool_call": 0.0,
        "retry_overhead": 0.0,
    },
    # Default fallback
    "_default": {
        "input_per_token": 1e-6,
        "output_per_token": 2e-6,
        "tool_call": 0.0,
        "retry_overhead": 0.0,
    },
    # ── Groq (free tier — effectively $0 at current free usage) ──
    "openai/gpt-oss-20b": {
        "input_per_token": 0.0,
        "output_per_token": 0.0,
        "tool_call": 0.0,
        "retry_overhead": 0.0,
    },
    "openai/gpt-oss-120b": {
        "input_per_token": 0.0,
        "output_per_token": 0.0,
        "tool_call": 0.0,
        "retry_overhead": 0.0,
    },
    "llama3-8b-8192": {
        "input_per_token": 0.05e-6,
        "output_per_token": 0.08e-6,
        "tool_call": 0.0,
        "retry_overhead": 0.0,
    },
    "llama3-70b-8192": {
        "input_per_token": 0.59e-6,
        "output_per_token": 0.79e-6,
        "tool_call": 0.0,
        "retry_overhead": 0.0,
    },
    "llama-3.1-8b-instant": {
        "input_per_token": 0.05e-6,
        "output_per_token": 0.08e-6,
        "tool_call": 0.0,
        "retry_overhead": 0.0,
    },
    "llama-3.3-70b-versatile": {
        "input_per_token": 0.59e-6,
        "output_per_token": 0.79e-6,
        "tool_call": 0.0,
        "retry_overhead": 0.0,
    },
    "mixtral-8x7b-32768": {
        "input_per_token": 0.24e-6,
        "output_per_token": 0.24e-6,
        "tool_call": 0.0,
        "retry_overhead": 0.0,
    },
    "gemma2-9b-it": {
        "input_per_token": 0.20e-6,
        "output_per_token": 0.20e-6,
        "tool_call": 0.0,
        "retry_overhead": 0.0,
    },
    "qwen/qwen3.6-27b": {
        "input_per_token": 0.0,
        "output_per_token": 0.0,
        "tool_call": 0.0,
        "retry_overhead": 0.0,
    },
}
