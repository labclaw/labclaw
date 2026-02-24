"""Edge file watcher — monitors directories for new data files from lab instruments.

Spec: docs/specs/L2-edge.md (File Watcher section)
Design doc: section 5.1 (Session Chronicle — edge nodes detect new data files)
"""

from __future__ import annotations

import logging
import threading
from collections import deque
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer
from watchdog.observers.api import BaseObserver

from labclaw.core.events import event_registry
from labclaw.core.schemas import FileReference

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Register events at module import time
# ---------------------------------------------------------------------------

_EVENTS = [
    "hardware.file.detected",
]

for _evt in _EVENTS:
    if not event_registry.is_registered(_evt):
        event_registry.register(_evt)


# ---------------------------------------------------------------------------
# Watchdog handler
# ---------------------------------------------------------------------------


class FileDetectedHandler(FileSystemEventHandler):
    """Watchdog handler that emits events when new files appear."""

    def __init__(
        self,
        device_id: str,
        callbacks: list[Callable[[FileReference], None]] | None = None,
    ) -> None:
        super().__init__()
        self._device_id = device_id
        self._callbacks = callbacks or []
        self._detected_files: deque[FileReference] = deque(maxlen=10_000)
        self._lock = threading.Lock()

    def on_created(self, event: FileSystemEvent) -> None:
        """Handle a newly created file."""
        self._handle_file_event(event, change_type="created")

    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle a modified file so late writes can be ingested."""
        self._handle_file_event(event, change_type="modified")

    def _handle_file_event(self, event: FileSystemEvent, change_type: str) -> None:
        """Emit a hardware.file.detected event for relevant file changes."""
        if event.is_directory:
            return

        src_path = event.src_path.decode() if isinstance(event.src_path, bytes) else event.src_path
        path = Path(src_path)
        try:
            size = path.stat().st_size
        except OSError:
            size = None

        file_ref = FileReference(
            path=path,
            size_bytes=size,
        )

        with self._lock:
            self._detected_files.append(file_ref)

        payload = {
            "device_id": self._device_id,
            "path": str(path),
            "size_bytes": size,
            "detected_at": datetime.now(UTC).isoformat(),
            "change_type": change_type,
        }

        event_registry.emit("hardware.file.detected", payload=payload)
        logger.info(
            "File %s: %s (device=%s, size=%s)",
            change_type,
            path,
            self._device_id,
            size,
        )

        for cb in self._callbacks:
            try:
                cb(file_ref)
            except Exception:
                logger.exception("Callback error for file %s", path)

    @property
    def detected_files(self) -> list[FileReference]:
        with self._lock:
            return list(self._detected_files)


# ---------------------------------------------------------------------------
# Edge watcher
# ---------------------------------------------------------------------------


class EdgeWatcher:
    """Monitors directories for new data files from lab instruments."""

    def __init__(self) -> None:
        self._observers: dict[str, BaseObserver] = {}
        self._handlers: dict[str, FileDetectedHandler] = {}
        self._detected_files: deque[FileReference] = deque(maxlen=10_000)
        self._lock = threading.Lock()

    def watch(self, path: Path, device_id: str, recursive: bool = False) -> None:
        """Start watching a directory for new files.

        Args:
            path: Directory to watch.
            device_id: Identifier for the device producing files.
            recursive: Whether to watch subdirectories.
        """
        if device_id in self._observers:
            raise ValueError(f"Already watching device {device_id!r}")

        if not path.is_dir():
            raise FileNotFoundError(f"Watch path does not exist or is not a directory: {path}")

        handler = FileDetectedHandler(
            device_id=device_id,
            callbacks=[self._on_file_detected],
        )
        self._handlers[device_id] = handler

        observer = Observer()
        observer.schedule(handler, str(path), recursive=recursive)
        observer.start()
        self._observers[device_id] = observer

        logger.info("Started watching %s for device %s (recursive=%s)", path, device_id, recursive)

    def stop(self, device_id: str) -> None:
        """Stop watching a specific device's directory."""
        observer = self._observers.pop(device_id, None)
        if observer is not None:
            observer.stop()
            observer.join(timeout=5)
            self._handlers.pop(device_id, None)
            logger.info("Stopped watching device %s", device_id)

    def stop_all(self) -> None:
        """Stop all watchers."""
        for device_id in list(self._observers):
            self.stop(device_id)

    def get_detected_files(self) -> list[FileReference]:
        """Return all detected files since start."""
        with self._lock:
            return list(self._detected_files)

    def _on_file_detected(self, file_ref: FileReference) -> None:
        """Internal callback to aggregate detected files."""
        with self._lock:
            self._detected_files.append(file_ref)
