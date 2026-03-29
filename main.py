"""Root-level ASGI entrypoint — required by most deployment platforms.

Platforms like Railway, Render, Fly.io, and Replit scan for a root-level
file that exposes a FastAPI/Starlette ``app`` object.  This module simply
re-exports the application from its canonical location so that the platform
can discover it via standard entrypoint conventions.

Usage (uvicorn):
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload

Usage (gunicorn + uvicorn workers):
    gunicorn main:app -k uvicorn.workers.UvicornWorker
"""
from temporalos.api.main import app  # noqa: F401  — re-exported for platform discovery

__all__ = ["app"]
