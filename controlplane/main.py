# Render entry point — auto-detection requires app at root
# Render looks for FastAPI app in main.py at the root of rootDir
from gateway.main import app  # noqa: F401

__all__ = ["app"]
