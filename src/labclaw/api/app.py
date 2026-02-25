"""LabClaw — FastAPI application.

Assembles all routers and mounts them under ``/api``.
"""

from __future__ import annotations

from fastapi import FastAPI

from labclaw import __version__
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

app = FastAPI(
    title="LabClaw",
    description="Self-evolving agentic lab intelligence API",
    version=__version__,
)

app.add_middleware(RequestLoggingMiddleware)

app.include_router(health_router, prefix="/api")
app.include_router(metrics_router, prefix="/api")
app.include_router(devices_router, prefix="/api/devices", tags=["devices"])
app.include_router(memory_router, prefix="/api/memory", tags=["memory"])
app.include_router(sessions_router, prefix="/api/sessions", tags=["sessions"])
app.include_router(discovery_router, prefix="/api/discovery", tags=["discovery"])
app.include_router(evolution_router, prefix="/api/evolution", tags=["evolution"])
app.include_router(events_router, prefix="/api/events", tags=["events"])
app.include_router(agents_router, prefix="/api/agents", tags=["agents"])
app.include_router(plugins_router, prefix="/api/plugins", tags=["plugins"])
app.include_router(orchestrator_router, prefix="/api/orchestrator", tags=["orchestrator"])
# Provenance endpoints — both versioned and legacy prefixes
app.include_router(provenance_router, prefix="/api/v0/provenance", tags=["provenance"])
app.include_router(provenance_router, prefix="/api/provenance", tags=["provenance"])
