"""Health and status endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from labclaw.api.deps import get_device_registry, get_event_registry
from labclaw.hardware.registry import DeviceRegistry

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": "0.1.0"}


@router.get("/status")
def status(
    device_reg: DeviceRegistry = Depends(get_device_registry),
    event_reg=Depends(get_event_registry),  # noqa: ANN001
) -> dict[str, object]:
    return {
        "status": "ok",
        "version": "0.1.0",
        "registered_events": len(event_reg.list_events()),
        "registered_devices": len(device_reg.list_devices()),
    }
