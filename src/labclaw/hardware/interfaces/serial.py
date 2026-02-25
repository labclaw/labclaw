"""Serial/USB device driver base class.

Requires pyserial: pip install pyserial

Spec: docs/specs/L1-hardware.md
"""

from __future__ import annotations

import logging
from typing import Any

from labclaw.core.events import event_registry
from labclaw.core.schemas import DeviceStatus
from labclaw.hardware.schemas import HardwareCommand

logger = logging.getLogger(__name__)


class SerialDriver:
    """Base for serial/USB devices. Requires pyserial."""

    def __init__(
        self,
        device_id: str,
        device_type: str,
        port: str,
        baudrate: int = 9600,
        timeout: float = 1.0,
    ) -> None:
        self._device_id = device_id
        self._device_type = device_type
        self._port = port
        self._baudrate = baudrate
        self._timeout = timeout
        self._serial: Any = None  # serial.Serial instance when connected

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
        """Open the serial port. Returns True on success."""
        try:
            import serial  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError(
                "pyserial is required for SerialDriver. Install with: pip install pyserial"
            ) from exc

        try:
            self._serial = serial.Serial(
                port=self._port,
                baudrate=self._baudrate,
                timeout=self._timeout,
            )
            logger.info(
                "SerialDriver %s connected on %s @ %d baud",
                self._device_id,
                self._port,
                self._baudrate,
            )
            event_registry.emit(
                "hardware.driver.connected",
                payload={
                    "device_id": self._device_id,
                    "port": self._port,
                    "baudrate": self._baudrate,
                },
            )
            return True
        except Exception as exc:
            logger.error("SerialDriver %s failed to connect: %s", self._device_id, exc)
            event_registry.emit(
                "hardware.driver.error",
                payload={"device_id": self._device_id, "error": str(exc)},
            )
            return False

    async def disconnect(self) -> None:
        """Close the serial port."""
        if self._serial is not None and self._serial.is_open:
            self._serial.close()
            logger.info("SerialDriver %s disconnected from %s", self._device_id, self._port)
        self._serial = None
        event_registry.emit(
            "hardware.driver.disconnected",
            payload={"device_id": self._device_id},
        )

    # ------------------------------------------------------------------
    # I/O
    # ------------------------------------------------------------------

    async def read(self) -> dict[str, Any]:
        """Read a line from the serial port and return parsed response."""
        if self._serial is None or not self._serial.is_open:
            raise RuntimeError(f"SerialDriver {self._device_id!r} is not connected")

        raw = self._serial.readline()
        decoded = raw.decode("utf-8", errors="replace").strip()
        result = self.parse_response(decoded)
        event_registry.emit(
            "hardware.driver.data_read",
            payload={"device_id": self._device_id, "raw": decoded},
        )
        return result

    async def write(self, command: HardwareCommand) -> bool:
        """Send a command over the serial port. Returns True on success."""
        if self._serial is None or not self._serial.is_open:
            logger.error("SerialDriver %s is not connected", self._device_id)
            return False

        payload_str = command.action
        if command.parameters:
            import json

            payload_str = f"{command.action} {json.dumps(command.parameters)}"

        try:
            self._serial.write((payload_str + "\n").encode("utf-8"))
            event_registry.emit(
                "hardware.driver.command_sent",
                payload={"device_id": self._device_id, "action": command.action},
            )
            return True
        except Exception as exc:
            logger.error("SerialDriver %s write error: %s", self._device_id, exc)
            event_registry.emit(
                "hardware.driver.error",
                payload={"device_id": self._device_id, "error": str(exc)},
            )
            return False

    async def status(self) -> DeviceStatus:
        """Return ONLINE if the serial port is open, else OFFLINE."""
        if self._serial is not None and self._serial.is_open:
            return DeviceStatus.ONLINE
        return DeviceStatus.OFFLINE

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def parse_response(self, raw: str) -> dict[str, Any]:
        """Parse a raw serial response. Override in subclasses.

        Default: return raw string under 'response' key.
        """
        return {"response": raw}
