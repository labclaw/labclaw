"""LabClaw — FastAPI application.

Assembles all routers and mounts them under ``/api``.
"""

from __future__ import annotations

import logging
import os

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from labclaw import __version__
from labclaw.api.deps import enforce_request_security
from labclaw.api.middleware import RequestLoggingMiddleware
from labclaw.api.routers.agents import router as agents_router
from labclaw.api.routers.devices import router as devices_router
from labclaw.api.routers.discovery import router as discovery_router
from labclaw.api.routers.events import router as events_router
from labclaw.api.routers.evolution import router as evolution_router
from labclaw.api.routers.health import router as health_router
from labclaw.api.routers.memory import router as memory_router
from labclaw.api.routers.metrics import router as metrics_router
from labclaw.api.routers.orchestrator import router as orchestrator_router
from labclaw.api.routers.plugins import router as plugins_router
from labclaw.api.routers.provenance import router as provenance_router
from labclaw.api.routers.sessions import router as sessions_router

logger = logging.getLogger("labclaw.api")

app = FastAPI(
    title="LabClaw",
    description="Self-evolving agentic lab intelligence API",
    version=__version__,
)

app.add_middleware(RequestLoggingMiddleware)

cors_origins = [
    origin.strip()
    for origin in os.environ.get("LABCLAW_CORS_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-API-Key",
        "X-Labclaw-Actor",
        "X-Labclaw-Role",
    ],
)

_secure_dep = [Depends(enforce_request_security)]

app.include_router(health_router, prefix="/api")
app.include_router(metrics_router, prefix="/api")
app.include_router(
    devices_router,
    prefix="/api/devices",
    tags=["devices"],
    dependencies=_secure_dep,
)
app.include_router(
    memory_router,
    prefix="/api/memory",
    tags=["memory"],
    dependencies=_secure_dep,
)
app.include_router(
    sessions_router,
    prefix="/api/sessions",
    tags=["sessions"],
    dependencies=_secure_dep,
)
app.include_router(
    discovery_router,
    prefix="/api/discovery",
    tags=["discovery"],
    dependencies=_secure_dep,
)
app.include_router(
    evolution_router,
    prefix="/api/evolution",
    tags=["evolution"],
    dependencies=_secure_dep,
)
app.include_router(
    events_router,
    prefix="/api/events",
    tags=["events"],
    dependencies=_secure_dep,
)
app.include_router(
    agents_router,
    prefix="/api/agents",
    tags=["agents"],
    dependencies=_secure_dep,
)
app.include_router(
    plugins_router,
    prefix="/api/plugins",
    tags=["plugins"],
    dependencies=_secure_dep,
)
app.include_router(
    orchestrator_router,
    prefix="/api/orchestrator",
    tags=["orchestrator"],
    dependencies=_secure_dep,
)
# Provenance endpoints — both versioned and legacy prefixes
app.include_router(
    provenance_router,
    prefix="/api/v0/provenance",
    tags=["provenance"],
    dependencies=_secure_dep,
)
app.include_router(
    provenance_router,
    prefix="/api/provenance",
    tags=["provenance"],
    dependencies=_secure_dep,
)


@app.exception_handler(Exception)
async def handle_unexpected_error(_request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "Unhandled API error",
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
