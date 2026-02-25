"""Generic file-watching device driver using watchdog.

Extends FileBasedDriver with event-driven file detection instead of polling.
Wraps watchdog Observer to detect newly created/modified files.

Spec: docs/specs/L1-hardware.md
"""

from __future__ import annotations

import logging
import threading
from collections import deque
from pathlib import Path
from typing import Any

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer
from watchdog.observers.api import BaseObserver

from labclaw.core.events import event_registry
from labclaw.core.schemas import DeviceStatus
from labclaw.hardware.interfaces.file_based import FileBasedDriver

logger = logging.getLogger(__name__)

# Register file-watcher events at module import time
_FILE_WATCHER_EVENTS = [
    "hardware.file.detected",
]

for _evt in _FILE_WATCHER_EVENTS:
    if not event_registry.is_registered(_evt):
        event_registry.register(_evt)


class _FileEventHandler(FileSystemEventHandler):
    """Watchdog handler that queues newly detected file paths."""

    def __init__(self, file_patterns: list[str], device_id: str) -> None:
        super().__init__()
        self._file_patterns = file_patterns
        self._device_id = device_id
        self._queue: deque[Path] = deque(maxlen=10_000)
        self._lock = threading.Lock()

    def _matches(self, path: Path) -> bool:
        import fnmatch

        return any(fnmatch.fnmatch(path.name, pat) for pat in self._file_patterns)

    def _handle(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        src = event.src_path
        decoded = src.decode() if isinstance(src, bytes) else src
        path = Path(decoded)
        if not self._matches(path):
            return
        with self._lock:
            self._queue.append(path)
        event_registry.emit(
            "hardware.file.detected",
            payload={"device_id": self._device_id, "path": str(path)},
        )
        logger.debug("FileWatcherDriver detected: %s", path)

    def on_created(self, event: FileSystemEvent) -> None:
        self._handle(event)

    def on_modified(self, event: FileSystemEvent) -> None:
        self._handle(event)

    def drain(self) -> list[Path]:
        """Return and clear all queued paths."""
        with self._lock:
            paths = list(self._queue)
            self._queue.clear()
        return paths


class FileWatcherDriver(FileBasedDriver):
    """Generic file-watching device driver. Wraps watchdog Observer.

    Uses event-driven detection (watchdog) instead of polling.
    read() returns newly detected file paths since the last call.
    """

    def __init__(
        self,
        device_id: str,
        device_type: str,
        watch_path: Path,
        file_patterns: list[str] | None = None,
        recursive: bool = False,
    ) -> None:
        super().__init__(device_id, device_type, watch_path, file_patterns)
        self._recursive = recursive
        self._observer: BaseObserver | None = None
        self._handler: _FileEventHandler | None = None

    async def connect(self) -> bool:
        """Verify watch path exists, then start watchdog observer."""
        ok = await super().connect()
        if not ok:
            return False

        self._handler = _FileEventHandler(self._file_patterns, self._device_id)
        self._observer = Observer()
        self._observer.schedule(self._handler, str(self._watch_path), recursive=self._recursive)
        self._observer.start()
        logger.info(
            "FileWatcherDriver %s started observer on %s (recursive=%s)",
            self._device_id,
            self._watch_path,
            self._recursive,
        )
        return True

    async def disconnect(self) -> None:
        """Stop watchdog observer then call parent disconnect."""
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None
            self._handler = None
        await super().disconnect()

    async def read(self) -> dict[str, Any]:
        """Return newly detected files (event-driven) + parse latest."""
        if self._handler is None:
            return {"new_files": [], "data": None}

        new_files = self._handler.drain()
        result: dict[str, Any] = {
            "new_files": [str(p) for p in new_files],
            "data": None,
        }

        if new_files:
            latest = new_files[-1]
            try:
                result["data"] = self.parse_file(latest)
                result["parsed_file"] = str(latest)
            except Exception as exc:
                logger.exception("Failed to parse file %s", latest)
                event_registry.emit(
                    "hardware.driver.error",
                    payload={
                        "device_id": self._device_id,
                        "error": str(exc),
                        "file": str(latest),
                    },
                )

        event_registry.emit(
            "hardware.driver.data_read",
            payload={"device_id": self._device_id, "new_file_count": len(new_files)},
        )
        return result

    async def status(self) -> DeviceStatus:
        """Return ONLINE if observer is running, else OFFLINE."""
        if self._observer is not None and self._observer.is_alive():
            return DeviceStatus.ONLINE
        return DeviceStatus.OFFLINE
