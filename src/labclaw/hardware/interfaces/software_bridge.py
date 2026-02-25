"""Software bridge device driver base class.

Placeholder for external software integrations: DeepLabCut-live, Bonsai,
PsychoPy, MATLAB, and similar systems that expose ZMQ/socket or IPC APIs.

Spec: docs/specs/L1-hardware.md
"""

from __future__ import annotations

import logging
from typing import Any

from labclaw.core.events import event_registry
from labclaw.core.schemas import DeviceStatus
from labclaw.hardware.schemas import HardwareCommand

logger = logging.getLogger(__name__)


class SoftwareBridgeDriver:
    """Base for external software integrations via ZMQ/socket/IPC.

    Subclasses implement:
      - ``_open_connection()`` / ``_close_connection()``
      - ``_recv()`` to pull data from the external process
      - ``_send()`` to push commands to the external process

    Examples: DeepLabCut-live (ZMQ PUB/SUB), Bonsai (named pipe),
    PsychoPy (TCP), MATLAB engine (matlab.engine API).
    """

    def __init__(
        self,
        device_id: str,
        device_type: str,
        endpoint: str = "",
    ) -> None:
        self._device_id = device_id
        self._device_type = device_type
        self._endpoint = endpoint
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
        """Open connection to the external software process."""
        try:
            self._open_connection()
            self._connected = True
            logger.info("SoftwareBridgeDriver %s connected to %s", self._device_id, self._endpoint)
            event_registry.emit(
                "hardware.driver.connected",
                payload={"device_id": self._device_id, "endpoint": self._endpoint},
            )
            return True
        except Exception as exc:
            logger.error("SoftwareBridgeDriver %s failed to connect: %s", self._device_id, exc)
            event_registry.emit(
                "hardware.driver.error",
                payload={"device_id": self._device_id, "error": str(exc)},
            )
            return False

    async def disconnect(self) -> None:
        """Close connection to the external software process."""
        try:
            self._close_connection()
        except Exception:
            logger.exception("SoftwareBridgeDriver %s error during disconnect", self._device_id)
        self._connected = False
        event_registry.emit(
            "hardware.driver.disconnected",
            payload={"device_id": self._device_id},
        )

    # ------------------------------------------------------------------
    # I/O
    # ------------------------------------------------------------------

    async def read(self) -> dict[str, Any]:
        """Receive a data frame from the external software."""
        data = self._recv()
        event_registry.emit(
            "hardware.driver.data_read",
            payload={"device_id": self._device_id},
        )
        return data

    async def write(self, command: HardwareCommand) -> bool:
        """Send a command to the external software."""
        try:
            self._send(command.action, command.parameters)
            event_registry.emit(
                "hardware.driver.command_sent",
                payload={"device_id": self._device_id, "action": command.action},
            )
            return True
        except Exception as exc:
            logger.error("SoftwareBridgeDriver %s send error: %s", self._device_id, exc)
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

    def _open_connection(self) -> None:  # pragma: no cover
        """Open the socket/ZMQ/IPC connection. Raise on failure."""
        raise NotImplementedError

    def _close_connection(self) -> None:  # pragma: no cover
        """Close the connection."""
        raise NotImplementedError

    def _recv(self) -> dict[str, Any]:  # pragma: no cover
        """Receive latest data frame from external process."""
        raise NotImplementedError

    def _send(self, action: str, parameters: dict[str, Any]) -> None:  # pragma: no cover
        """Send command to external process."""
        raise NotImplementedError
