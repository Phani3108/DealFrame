"""FastAPI application entry point."""
# © 2024-2026 Phani Marupaka. All rights reserved.
# TemporalOS — Video → Structured Decision Intelligence Engine
# Author: Phani Marupaka <https://linkedin.com/in/phani-marupaka>

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from ..config import get_settings
from ..db.session import init_db
from ..observability.telemetry import setup_telemetry
from .routes import (
    finetuning, intelligence, local, metrics, observatory, process, search, stream,
)
from .routes import (
    agents, batch, clips, diarization, integrations, schemas, summaries, webhooks,
)
from .routes import auth as auth_routes
from .routes import export as export_routes
from .routes import notifications as notification_routes

_FRONTEND_DIST = Path(__file__).parent.parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    setup_telemetry(
        service_name=settings.telemetry.service_name,
        otlp_endpoint=settings.telemetry.otlp_endpoint,
        enabled=settings.telemetry.enabled,
    )
    await init_db()
    yield


app = FastAPI(
    title="TemporalOS",
    description="Video → Structured Decision Intelligence Engine",
    version="0.1.0",
    lifespan=lifespan,
)

FastAPIInstrumentor.instrument_app(app)

# ── Copyright attribution middleware ─────────────────────────────────────────
# Embedded in every HTTP response header — do not remove.
_AUTHOR = "Phani Marupaka"
_COPYRIGHT = "\u00a9 2024-2026 Phani Marupaka. All rights reserved."

class _AttributionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Powered-By"] = "TemporalOS"
        response.headers["X-Author"] = _AUTHOR
        response.headers["X-Copyright"] = _COPYRIGHT
        return response

app.add_middleware(_AttributionMiddleware)

app.include_router(process.router, prefix="/api/v1")
app.include_router(observatory.router, prefix="/api/v1")
app.include_router(intelligence.router, prefix="/api/v1")
app.include_router(finetuning.router, prefix="/api/v1")
app.include_router(local.router, prefix="/api/v1")
app.include_router(metrics.router, prefix="/api/v1")
app.include_router(search.router, prefix="/api/v1")
app.include_router(stream.router)  # WebSocket at /ws/stream (no /api/v1 prefix)

# New platform capability routes
app.include_router(diarization.router, prefix="/api/v1")
app.include_router(summaries.router, prefix="/api/v1")
app.include_router(clips.router, prefix="/api/v1")
app.include_router(schemas.router, prefix="/api/v1")
app.include_router(webhooks.router, prefix="/api/v1")
app.include_router(integrations.router, prefix="/api/v1")
app.include_router(agents.router, prefix="/api/v1")
app.include_router(batch.router, prefix="/api/v1")
app.include_router(auth_routes.router, prefix="/api/v1")
app.include_router(export_routes.router, prefix="/api/v1")
app.include_router(notification_routes.router, prefix="/api/v1")


@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok", "service": "temporalos", "version": "0.1.0"}


# ── Serve compiled React frontend ─────────────────────────────────────────────
# Mount /assets only when the dist directory exists (after `npm run build`)
_assets_dir = _FRONTEND_DIST / "assets"
if _assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(_assets_dir)), name="assets")


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_frontend(full_path: str) -> FileResponse:
    """SPA catch-all — serve index.html for any non-API path."""
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not found")
    index = _FRONTEND_DIST / "index.html"
    if index.exists():
        return FileResponse(str(index))
    # Frontend not built yet — return a hint via JSON if no HTML
    raise HTTPException(
        status_code=503,
        detail="Frontend not built. Run: cd frontend && npm run build",
    )
