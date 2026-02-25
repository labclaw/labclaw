"""Device CRUD endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from labclaw.api.deps import get_device_registry
from labclaw.core.schemas import DeviceStatus
from labclaw.hardware.registry import DeviceRegistry
from labclaw.hardware.schemas import DeviceRecord

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class DeviceCreateRequest(BaseModel):
    name: str
    device_type: str
    model: str = ""
    manufacturer: str = ""
    location: str = ""


class DeviceStatusUpdate(BaseModel):
    status: DeviceStatus


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/")
def list_devices(
    registry: DeviceRegistry = Depends(get_device_registry),
) -> list[DeviceRecord]:
    return registry.list_devices()


@router.get("/{device_id}")
def get_device(
    device_id: str,
    registry: DeviceRegistry = Depends(get_device_registry),
) -> DeviceRecord:
    try:
        return registry.get(device_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Device {device_id!r} not found")


@router.post("/", status_code=201)
def register_device(
    body: DeviceCreateRequest,
    registry: DeviceRegistry = Depends(get_device_registry),
) -> DeviceRecord:
    record = DeviceRecord(
        name=body.name,
        device_type=body.device_type,
        model=body.model,
        manufacturer=body.manufacturer,
        location=body.location,
    )
    try:
        return registry.register(record)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.patch("/{device_id}/status")
def update_device_status(
    device_id: str,
    body: DeviceStatusUpdate,
    registry: DeviceRegistry = Depends(get_device_registry),
) -> dict[str, str]:
    try:
        registry.update_status(device_id, body.status)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Device {device_id!r} not found")
    return {"device_id": device_id, "status": body.status.value}


@router.delete("/{device_id}", status_code=200)
def unregister_device(
    device_id: str,
    registry: DeviceRegistry = Depends(get_device_registry),
) -> dict[str, str]:
    try:
        registry.unregister(device_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Device {device_id!r} not found")
    return {"device_id": device_id, "deleted": "true"}
