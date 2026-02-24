"""DAQ (Data Acquisition) device driver base class.

Placeholder for NI DAQmx, LabJack, and similar analog/digital I/O devices.
Subclasses provide vendor-specific channel configuration and sampling.

Spec: docs/specs/L1-hardware.md
"""

from __future__ import annotations

import logging
from typing import Any

from labclaw.core.events import event_registry
from labclaw.core.schemas import DeviceStatus
from labclaw.hardware.schemas import HardwareCommand

logger = logging.getLogger(__name__)


class DAQDriver:
    """Base for GPIO/DAQ devices (NI DAQmx, LabJack, Arduino, etc.).

    Subclasses implement:
      - ``_open_device()`` / ``_close_device()`` for hardware init
      - ``_read_channels()`` to sample analog/digital inputs
      - ``_write_channels()`` to set analog/digital outputs
    """

    def __init__(
        self,
        device_id: str,
        device_type: str,
        device_address: str = "",
        sample_rate_hz: float = 1000.0,
    ) -> None:
        self._device_id = device_id
        self._device_type = device_type
        self._device_address = device_address
        self._sample_rate_hz = sample_rate_hz
        self._connected = False

    # ------------------------------------------------------------------
    # DeviceDriver protocol properties
    # ------------------------------------------------------------------

    @property
    def device_id(self) -> str:
        return self._device_id

    @property
    def device_type(self) -> str:
        return self._device_type

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> bool:
        """Open DAQ device. Subclasses call ``_open_device()``."""
        try:
            self._open_device()
            self._connected = True
            logger.info("DAQDriver %s connected (%s)", self._device_id, self._device_address)
            event_registry.emit(
                "hardware.driver.connected",
                payload={"device_id": self._device_id, "address": self._device_address},
            )
            return True
        except Exception as exc:
            logger.error("DAQDriver %s failed to connect: %s", self._device_id, exc)
            event_registry.emit(
                "hardware.driver.error",
                payload={"device_id": self._device_id, "error": str(exc)},
            )
            return False

    async def disconnect(self) -> None:
        """Close DAQ device."""
        try:
            self._close_device()
        except Exception:
            logger.exception("DAQDriver %s error during disconnect", self._device_id)
        self._connected = False
        event_registry.emit(
            "hardware.driver.disconnected",
            payload={"device_id": self._device_id},
        )

    # ------------------------------------------------------------------
    # I/O
    # ------------------------------------------------------------------

    async def read(self) -> dict[str, Any]:
        """Sample channels and return readings dict."""
        data = self._read_channels()
        event_registry.emit(
            "hardware.driver.data_read",
            payload={"device_id": self._device_id, "channels": list(data.keys())},
        )
        return data

    async def write(self, command: HardwareCommand) -> bool:
        """Apply output command to channels."""
        try:
            self._write_channels(command.action, command.parameters)
            event_registry.emit(
                "hardware.driver.command_sent",
                payload={"device_id": self._device_id, "action": command.action},
            )
            return True
        except Exception as exc:
            logger.error("DAQDriver %s write error: %s", self._device_id, exc)
            event_registry.emit(
                "hardware.driver.error",
                payload={"device_id": self._device_id, "error": str(exc)},
            )
            return False

    async def status(self) -> DeviceStatus:
        return DeviceStatus.ONLINE if self._connected else DeviceStatus.OFFLINE

    # ------------------------------------------------------------------
    # Subclass hooks (override in concrete implementations)
    # ------------------------------------------------------------------

    def _open_device(self) -> None:  # pragma: no cover
        """Open hardware connection. Raise on failure."""
        raise NotImplementedError

    def _close_device(self) -> None:  # pragma: no cover
        """Close hardware connection."""
        raise NotImplementedError

    def _read_channels(self) -> dict[str, Any]:  # pragma: no cover
        """Sample and return channel readings."""
        raise NotImplementedError

    def _write_channels(self, action: str, parameters: dict[str, Any]) -> None:  # pragma: no cover
        """Apply output values to channels."""
        raise NotImplementedError
