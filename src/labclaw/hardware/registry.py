"""Device registry — discovery, state tracking, and capability declaration.

Each device self-registers via the Gateway with:
  - Identity (type, model, location)
  - Capabilities (observe, control, data formats)
  - Current state (online/offline/error/calibrating/in-use/reserved)

Spec: docs/specs/L1-hardware.md
"""

from __future__ import annotations

import logging

from labclaw.core.events import event_registry
from labclaw.core.schemas import DeviceStatus
from labclaw.hardware.schemas import DeviceRecord

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Register hardware events at import time
# ---------------------------------------------------------------------------

_HARDWARE_EVENTS = [
    "hardware.device.registered",
    "hardware.device.status_changed",
    "hardware.device.unregistered",
]

for _evt in _HARDWARE_EVENTS:
    if not event_registry.is_registered(_evt):
        event_registry.register(_evt)


class DeviceRegistry:
    """In-memory registry of all lab devices."""

    def __init__(self) -> None:
        self._devices: dict[str, DeviceRecord] = {}

    def register(self, record: DeviceRecord) -> DeviceRecord:
        """Register a device. Raises ValueError if device_id already exists."""
        if record.device_id in self._devices:
            raise ValueError(f"Device {record.device_id!r} already registered")

        self._devices[record.device_id] = record
        logger.info("Registered device %s (%s)", record.name, record.device_id)

        event_registry.emit(
            "hardware.device.registered",
            payload={
                "device_id": record.device_id,
                "name": record.name,
                "device_type": record.device_type,
            },
        )
        return record

    def get(self, device_id: str) -> DeviceRecord:
        """Get device by ID. Raises KeyError if not found."""
        try:
            return self._devices[device_id]
        except KeyError:
            raise KeyError(f"Device {device_id!r} not found") from None

    def update_status(self, device_id: str, status: DeviceStatus) -> None:
        """Update device status. Raises KeyError if not found."""
        device = self.get(device_id)
        old_status = device.status
        self._devices[device_id] = device.model_copy(update={"status": status})
        logger.info("Device %s status: %s -> %s", device_id, old_status.value, status.value)

        event_registry.emit(
            "hardware.device.status_changed",
            payload={
                "device_id": device_id,
                "old_status": old_status.value,
                "new_status": status.value,
            },
        )

    def list_devices(self, status: DeviceStatus | None = None) -> list[DeviceRecord]:
        """List all devices, optionally filtered by status."""
        devices = list(self._devices.values())
        if status is not None:
            devices = [d for d in devices if d.status == status]
        return [d.model_copy() for d in devices]

    def unregister(self, device_id: str) -> None:
        """Remove device from registry. Raises KeyError if not found."""
        device = self.get(device_id)
        del self._devices[device_id]
        logger.info("Unregistered device %s (%s)", device.name, device_id)

        event_registry.emit(
            "hardware.device.unregistered",
            payload={
                "device_id": device_id,
                "name": device.name,
            },
        )
