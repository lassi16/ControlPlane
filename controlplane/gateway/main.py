"""
ControlPlane — FastAPI Application Entry Point
"""
import time
import uuid
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings import settings
from gateway.routes import router as gateway_router
from telemetry.dashboard_api import router as dashboard_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("controlplane")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle hooks."""
    logger.info("ControlPlane starting up...")
    # Initialise database (SQLite locally, PostgreSQL in Docker)
    from telemetry.db import init_db, USE_POSTGRES
    await init_db()
    logger.info(f"Database ready | backend={'postgresql' if USE_POSTGRES else 'sqlite'}")
    yield
    logger.info("ControlPlane shutting down...")


app = FastAPI(
    title="ControlPlane — Responsible AI Gateway",
    description=(
        "Model-agnostic LLM proxy that intercepts every request-response pair "
        "and evaluates it across bias, hallucination, and privacy risk dimensions."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# CORS for dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.DASHBOARD_ORIGIN, "http://localhost:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(gateway_router, prefix="")
app.include_router(dashboard_router, prefix="/api")


@app.get("/health")
async def health():
    from telemetry.db import USE_POSTGRES, _DB_PATH
    return {
        "status": "healthy",
        "service": "ControlPlane",
        "db_backend": "postgresql" if USE_POSTGRES else "sqlite",
        "db_location": "postgres" if USE_POSTGRES else str(_DB_PATH),
        "timestamp": time.time(),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
