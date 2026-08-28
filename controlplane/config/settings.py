"""
ControlPlane — Application Settings
Reads from environment variables / .env file.
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "ControlPlane"
    APP_ENV: str = "development"
    DEBUG: bool = True

    # Gateway
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # LLM Backend (OpenAI-compatible)
    OPENAI_API_KEY: str = "sk-placeholder"
    OPENAI_API_BASE: str = "https://api.openai.com/v1"
    ANTHROPIC_API_KEY: Optional[str] = None

    # Groq (free tier — recommended for local testing)
    GROQ_API_KEY: Optional[str] = None
    GROQ_API_BASE: str = "https://api.groq.com/openai/v1"

    # Default model — use current Groq model when GROQ_API_KEY is set
    DEFAULT_MODEL: str = "groq/llama3-8b-8192"

    # PostgreSQL
    DATABASE_URL: str = "postgresql+asyncpg://controlplane:controlplane@localhost:5432/controlplane"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # Search API (for evidence retrieval)
    GOOGLE_SEARCH_API_KEY: Optional[str] = None
    GOOGLE_SEARCH_CX: Optional[str] = None
    BING_SEARCH_API_KEY: Optional[str] = None

    # ML Models (local paths or HuggingFace model IDs)
    NER_MODEL: str = "dslim/bert-base-NER"
    TOXICITY_MODEL: str = "unitary/toxic-bert"
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    NLI_MODEL: str = "cross-encoder/nli-deberta-v3-base"
    CLAIM_EXTRACTOR_MODEL: str = "google/flan-t5-small"

    # Budget Limits (USD)
    DEFAULT_SESSION_BUDGET: float = 1.0
    DEFAULT_DAILY_BUDGET: float = 50.0

    # Sampling Rates for Deep Checks
    SAMPLE_RATE_LOW: float = 0.05
    SAMPLE_RATE_MEDIUM: float = 0.25
    SAMPLE_RATE_HIGH: float = 1.0
    SAMPLE_RATE_CRITICAL: float = 1.0

    # Dashboard CORS
    DASHBOARD_ORIGIN: str = "http://localhost:3000"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
