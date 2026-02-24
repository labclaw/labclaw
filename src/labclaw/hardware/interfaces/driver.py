"""Abstract DeviceDriver protocol — unified interface for all device drivers.

Spec: docs/specs/L1-hardware.md
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from labclaw.core.events import event_registry
from labclaw.core.schemas import DeviceStatus
from labclaw.hardware.schemas import HardwareCommand

# ---------------------------------------------------------------------------
# Register driver events at import time
# ---------------------------------------------------------------------------

_DRIVER_EVENTS = [
    "hardware.driver.connected",
    "hardware.driver.disconnected",
    "hardware.driver.data_read",
    "hardware.driver.command_sent",
    "hardware.driver.error",
]

for _evt in _DRIVER_EVENTS:
    if not event_registry.is_registered(_evt):
        event_registry.register(_evt)


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class DeviceDriver(Protocol):
    """Abstract interface for all device drivers."""

    @property
    def device_id(self) -> str: ...

    @property
    def device_type(self) -> str: ...

    async def connect(self) -> bool:
        """Connect to the device. Returns True on success."""
        ...

    async def disconnect(self) -> None:
        """Disconnect from the device."""
        ...

    async def read(self) -> dict[str, Any]:
        """Read latest data from device. Returns parsed data dict."""
        ...

    async def write(self, command: HardwareCommand) -> bool:
        """Send command to device. Returns True on success."""
        ...

    async def status(self) -> DeviceStatus:
        """Get current device status."""
        ...
