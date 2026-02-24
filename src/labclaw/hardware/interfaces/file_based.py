"""File-based device driver base class.

Base for devices that produce output files (CSV, TSV, TIFF, etc.).
Subclasses override parse_file() for device-specific format handling.

Spec: docs/specs/L1-hardware.md
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any

from labclaw.core.events import event_registry
from labclaw.core.schemas import DeviceStatus
from labclaw.hardware.schemas import HardwareCommand

logger = logging.getLogger(__name__)

# Ensure hardware driver events are registered regardless of import path
_DRIVER_EVENTS = [
    "hardware.driver.connected",
    "hardware.driver.disconnected",
    "hardware.driver.error",
    "hardware.driver.data_received",
]
for _evt in _DRIVER_EVENTS:
    if not event_registry.is_registered(_evt):
        event_registry.register(_evt)


class FileBasedDriver:
    """Base for devices that produce output files (CSV, TSV, TIFF, etc.)."""

    def __init__(
        self,
        device_id: str,
        device_type: str,
        watch_path: Path,
        file_patterns: list[str] | None = None,
    ) -> None:
        self._device_id = device_id
        self._device_type = device_type
        self._watch_path = watch_path
        self._file_patterns = file_patterns or ["*.csv", "*.tsv"]
        self._connected = False
        self._seen_paths: set[Path] = set()

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
        """Verify watch_path exists and is accessible."""
        if not self._watch_path.exists():
            logger.error("Watch path does not exist: %s", self._watch_path)
            event_registry.emit(
                "hardware.driver.error",
                payload={
                    "device_id": self._device_id,
                    "error": f"Watch path does not exist: {self._watch_path}",
                },
            )
            return False
        if not self._watch_path.is_dir():
            logger.error("Watch path is not a directory: %s", self._watch_path)
            event_registry.emit(
                "hardware.driver.error",
                payload={
                    "device_id": self._device_id,
                    "error": f"Watch path is not a directory: {self._watch_path}",
                },
            )
            return False

        self._connected = True
        # Snapshot existing files so first read() only returns truly new ones
        self._seen_paths = set(self._scan_files())
        logger.info("Connected FileBasedDriver %s -> %s", self._device_id, self._watch_path)
        event_registry.emit(
            "hardware.driver.connected",
            payload={"device_id": self._device_id, "watch_path": str(self._watch_path)},
        )
        return True

    async def disconnect(self) -> None:
        """Mark device as disconnected."""
        self._connected = False
        logger.info("Disconnected FileBasedDriver %s", self._device_id)
        event_registry.emit(
            "hardware.driver.disconnected",
            payload={"device_id": self._device_id},
        )

    # ------------------------------------------------------------------
    # I/O
    # ------------------------------------------------------------------

    async def read(self) -> dict[str, Any]:
        """Scan for new files matching patterns, parse the latest one."""
        current = set(self._scan_files())
        new_files = sorted(current - self._seen_paths)
        self._seen_paths = current

        result: dict[str, Any] = {"new_files": [str(p) for p in new_files], "data": None}

        if new_files:
            latest = new_files[-1]
            try:
                result["data"] = self.parse_file(latest)
                result["parsed_file"] = str(latest)
            except Exception as exc:
                logger.exception("Failed to parse file %s", latest)
                event_registry.emit(
                    "hardware.driver.error",
                    payload={"device_id": self._device_id, "error": str(exc), "file": str(latest)},
                )

        event_registry.emit(
            "hardware.driver.data_read",
            payload={"device_id": self._device_id, "new_file_count": len(new_files)},
        )
        return result

    async def write(self, command: HardwareCommand) -> bool:
        """File-based devices are read-only; write() always returns False."""
        logger.warning(
            "FileBasedDriver %s does not support write commands (action=%s)",
            self._device_id,
            command.action,
        )
        return False

    async def status(self) -> DeviceStatus:
        """Return ONLINE if connected and path accessible, else OFFLINE."""
        if self._connected and self._watch_path.exists():
            return DeviceStatus.ONLINE
        return DeviceStatus.OFFLINE

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _scan_files(self) -> list[Path]:
        """Return all files under watch_path matching any pattern."""
        matches: list[Path] = []
        for pattern in self._file_patterns:
            matches.extend(self._watch_path.glob(pattern))
        return matches

    def parse_file(self, path: Path) -> dict[str, Any]:
        """Parse a file. Override in subclasses for device-specific formats.

        Default: reads CSV/TSV and returns list of row dicts.
        """
        delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
        rows: list[dict[str, str]] = []
        with path.open(newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh, delimiter=delimiter)
            for row in reader:
                rows.append(dict(row))
        return {"rows": rows, "row_count": len(rows), "file": str(path)}
