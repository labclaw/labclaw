"""Health and status endpoints."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from labclaw import __version__
from labclaw.api.deps import (
    get_data_dir,
    get_device_registry,
    get_event_registry,
    get_evolution_engine,
)
from labclaw.hardware.registry import DeviceRegistry

router = APIRouter()

_START_TIME = time.monotonic()


def _check_memory(memory_root_path: str | None = None) -> dict[str, str]:
    """Check if memory_root exists and is writable."""
    from labclaw.api.deps import _default_memory_root

    root = _default_memory_root()
    if not root.exists():
        return {"status": "degraded", "detail": "memory_root does not exist"}
    try:
        probe = root / ".health_probe"
        probe.write_text("ok")
        probe.unlink()
    except OSError:
        return {"status": "degraded", "detail": "memory_root not writable"}
    return {"status": "healthy"}


def _check_data() -> dict[str, str]:
    """Check if data_dir exists."""
    data_dir = get_data_dir()
    if not data_dir.exists():
        return {"status": "degraded", "detail": "data_dir does not exist"}
    return {"status": "healthy"}


def _check_event_bus() -> dict[str, str]:
    """Check event_registry is functional."""
    try:
        reg = get_event_registry()
        reg.list_events()
        return {"status": "healthy"}
    except Exception as exc:
        return {"status": "unhealthy", "detail": str(exc)}


def _check_evolution() -> dict[str, str]:
    """Check evolution engine state."""
    try:
        engine = get_evolution_engine()
        active = engine.get_active_cycles()
        return {
            "status": "healthy",
            "active_cycles": str(len(active)),
        }
    except Exception as exc:
        return {"status": "unhealthy", "detail": str(exc)}


@router.get("/health")
def health() -> JSONResponse:
    components = {
        "memory": _check_memory(),
        "data": _check_data(),
        "event_bus": _check_event_bus(),
        "evolution": _check_evolution(),
    }

    statuses = [c["status"] for c in components.values()]
    if any(s == "unhealthy" for s in statuses):
        overall = "unhealthy"
    elif any(s == "degraded" for s in statuses):
        overall = "degraded"
    else:
        overall = "healthy"

    status_code = 503 if overall == "unhealthy" else 200

    return JSONResponse(
        content={
            "status": overall,
            "components": components,
            "version": __version__,
            "uptime_seconds": round(time.monotonic() - _START_TIME, 2),
        },
        status_code=status_code,
    )


@router.get("/status")
def status(
    device_reg: DeviceRegistry = Depends(get_device_registry),
    event_reg=Depends(get_event_registry),  # noqa: ANN001
) -> dict[str, object]:
    return {
        "status": "ok",
        "version": __version__,
        "registered_events": len(event_reg.list_events()),
        "registered_devices": len(device_reg.list_devices()),
    }
