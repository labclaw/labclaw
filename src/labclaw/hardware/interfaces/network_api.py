"""Network API device driver base class.

Base for devices with REST API interfaces. Uses httpx AsyncClient.

Spec: docs/specs/L1-hardware.md
"""

from __future__ import annotations

import logging
from typing import Any

from labclaw.core.events import event_registry
from labclaw.core.schemas import DeviceStatus
from labclaw.hardware.schemas import HardwareCommand

logger = logging.getLogger(__name__)


class NetworkAPIDriver:
    """Base for devices with REST API interfaces."""

    def __init__(
        self,
        device_id: str,
        device_type: str,
        base_url: str,
        headers: dict[str, str] | None = None,
        timeout: float = 10.0,
        read_endpoint: str = "/status",
        write_endpoint: str = "/command",
    ) -> None:
        self._device_id = device_id
        self._device_type = device_type
        self._base_url = base_url.rstrip("/")
        self._headers = headers or {}
        self._timeout = timeout
        self._read_endpoint = read_endpoint
        self._write_endpoint = write_endpoint
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
        """Test API connectivity with a GET to the read endpoint."""
        try:
            import httpx
        except ImportError as exc:
            raise ImportError(
                "httpx is required for NetworkAPIDriver. Install with: pip install httpx"
            ) from exc

        url = self._base_url + self._read_endpoint
        try:
            async with httpx.AsyncClient(headers=self._headers, timeout=self._timeout) as client:
                resp = await client.get(url)
                resp.raise_for_status()
            self._connected = True
            logger.info("NetworkAPIDriver %s connected to %s", self._device_id, self._base_url)
            event_registry.emit(
                "hardware.driver.connected",
                payload={"device_id": self._device_id, "base_url": self._base_url},
            )
            return True
        except Exception as exc:
            logger.error(
                "NetworkAPIDriver %s failed to connect to %s: %s",
                self._device_id,
                self._base_url,
                exc,
            )
            event_registry.emit(
                "hardware.driver.error",
                payload={"device_id": self._device_id, "error": str(exc)},
            )
            return False

    async def disconnect(self) -> None:
        """Mark device as disconnected (no persistent connection to close)."""
        self._connected = False
        logger.info("NetworkAPIDriver %s disconnected", self._device_id)
        event_registry.emit(
            "hardware.driver.disconnected",
            payload={"device_id": self._device_id},
        )

    # ------------------------------------------------------------------
    # I/O
    # ------------------------------------------------------------------

    async def read(self) -> dict[str, Any]:
        """Call the GET read endpoint and return JSON response."""
        import httpx

        url = self._base_url + self._read_endpoint
        try:
            async with httpx.AsyncClient(headers=self._headers, timeout=self._timeout) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data: dict[str, Any] = resp.json()
            event_registry.emit(
                "hardware.driver.data_read",
                payload={"device_id": self._device_id, "url": url},
            )
            return data
        except Exception as exc:
            logger.error("NetworkAPIDriver %s read error: %s", self._device_id, exc)
            event_registry.emit(
                "hardware.driver.error",
                payload={"device_id": self._device_id, "error": str(exc)},
            )
            raise

    async def write(self, command: HardwareCommand) -> bool:
        """POST command to the write endpoint. Returns True on success."""
        import httpx

        url = self._base_url + self._write_endpoint
        body = {"action": command.action, "parameters": command.parameters}
        try:
            async with httpx.AsyncClient(headers=self._headers, timeout=self._timeout) as client:
                resp = await client.post(url, json=body)
                resp.raise_for_status()
            event_registry.emit(
                "hardware.driver.command_sent",
                payload={"device_id": self._device_id, "action": command.action, "url": url},
            )
            return True
        except Exception as exc:
            logger.error("NetworkAPIDriver %s write error: %s", self._device_id, exc)
            event_registry.emit(
                "hardware.driver.error",
                payload={"device_id": self._device_id, "error": str(exc)},
            )
            return False

    async def status(self) -> DeviceStatus:
        """Return ONLINE if last connect() succeeded, else OFFLINE."""
        if self._connected:
            return DeviceStatus.ONLINE
        return DeviceStatus.OFFLINE
