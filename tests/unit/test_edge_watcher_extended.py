"""Extended tests for src/labclaw/edge/watcher.py.

Covers lines 68, 74-75, 105-106, 137, 140, 171-172, 176-177:
  - FileDetectedHandler: directory events (ignored), OSError on stat, callback exception
  - EdgeWatcher: duplicate watch guard, non-directory watch guard,
    get_detected_files, _on_file_detected aggregation
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from watchdog.events import (
    DirCreatedEvent,
    FileCreatedEvent,
    FileModifiedEvent,
)

from labclaw.core.events import event_registry
from labclaw.edge.watcher import EdgeWatcher, FileDetectedHandler

# Ensure the required event is registered for all tests in this module
if not event_registry.is_registered("hardware.file.detected"):
    event_registry.register("hardware.file.detected")


# ---------------------------------------------------------------------------
# FileDetectedHandler
# ---------------------------------------------------------------------------


class TestFileDetectedHandlerEdgeCases:
    def test_directory_event_is_ignored(self, tmp_path: Path) -> None:
        """on_created with a directory event must not add to detected_files."""
        handler = FileDetectedHandler(device_id="rig-01")
        dir_event = DirCreatedEvent(str(tmp_path))
        handler.on_created(dir_event)
        assert handler.detected_files == []

    def test_oserror_on_stat_sets_size_none(self, tmp_path: Path) -> None:
        """When path.stat() raises OSError (file disappeared), size_bytes is None."""
        nonexistent = tmp_path / "ghost.csv"
        handler = FileDetectedHandler(device_id="rig-01")
        event = FileCreatedEvent(str(nonexistent))
        # File does not exist, so stat() will raise OSError
        handler.on_created(event)
        detected = handler.detected_files
        assert len(detected) == 1
        assert detected[0].size_bytes is None

    def test_bytes_src_path_is_decoded(self, tmp_path: Path) -> None:
        """Event src_path as bytes must be decoded to str before constructing Path."""
        csv_path = tmp_path / "bytes.csv"
        csv_path.write_text("a,b\n1,2\n", encoding="utf-8")
        handler = FileDetectedHandler(device_id="rig-01")

        # Simulate a watchdog event where src_path is bytes
        event = MagicMock()
        event.is_directory = False
        event.src_path = str(csv_path).encode()
        handler._handle_file_event(event, change_type="created")

        detected = handler.detected_files
        assert len(detected) == 1
        assert detected[0].path == csv_path

    def test_callback_exception_does_not_propagate(self, tmp_path: Path) -> None:
        """If a callback raises, the handler must log it and continue."""
        csv_path = tmp_path / "data.csv"
        csv_path.write_text("a,b\n1,2\n", encoding="utf-8")

        def bad_callback(file_ref):  # noqa: ANN001
            raise RuntimeError("callback exploded")

        handler = FileDetectedHandler(device_id="rig-01", callbacks=[bad_callback])
        event = FileCreatedEvent(str(csv_path))
        # Must not raise despite the callback error
        handler.on_created(event)
        # File is still tracked
        assert len(handler.detected_files) == 1

    def test_multiple_callbacks_all_called(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "multi.csv"
        csv_path.write_text("a\n1\n", encoding="utf-8")

        calls: list[str] = []
        handler = FileDetectedHandler(
            device_id="rig-01",
            callbacks=[
                lambda ref: calls.append("cb1"),
                lambda ref: calls.append("cb2"),
            ],
        )
        handler.on_created(FileCreatedEvent(str(csv_path)))
        assert calls == ["cb1", "cb2"]

    def test_on_modified_event_tracked(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "mod.csv"
        csv_path.write_text("a\n5\n", encoding="utf-8")
        handler = FileDetectedHandler(device_id="rig-02")
        handler.on_modified(FileModifiedEvent(str(csv_path)))
        detected = handler.detected_files
        assert len(detected) == 1
        assert detected[0].path == csv_path


# ---------------------------------------------------------------------------
# EdgeWatcher
# ---------------------------------------------------------------------------


class TestEdgeWatcherEdgeCases:
    def test_duplicate_watch_raises(self, tmp_path: Path) -> None:
        """Registering the same device_id twice must raise ValueError."""
        watcher = EdgeWatcher()
        watcher.watch(tmp_path, device_id="rig-dup")
        try:
            with pytest.raises(ValueError, match="Already watching"):
                watcher.watch(tmp_path, device_id="rig-dup")
        finally:
            watcher.stop_all()

    def test_watch_nonexistent_path_raises(self, tmp_path: Path) -> None:
        """Watching a path that does not exist must raise FileNotFoundError."""
        watcher = EdgeWatcher()
        missing = tmp_path / "does_not_exist"
        with pytest.raises(FileNotFoundError):
            watcher.watch(missing, device_id="ghost-rig")

    def test_watch_file_path_raises(self, tmp_path: Path) -> None:
        """Watching a regular file (not directory) must raise FileNotFoundError."""
        file_path = tmp_path / "file.csv"
        file_path.write_text("a\n", encoding="utf-8")
        watcher = EdgeWatcher()
        with pytest.raises(FileNotFoundError):
            watcher.watch(file_path, device_id="file-rig")

    def test_get_detected_files_initially_empty(self) -> None:
        watcher = EdgeWatcher()
        assert watcher.get_detected_files() == []

    def test_on_file_detected_aggregates_into_watcher(self, tmp_path: Path) -> None:
        """_on_file_detected must append to the watcher-level deque."""
        from labclaw.core.schemas import FileReference

        watcher = EdgeWatcher()
        ref = FileReference(path=tmp_path / "out.csv", size_bytes=100)
        watcher._on_file_detected(ref)
        detected = watcher.get_detected_files()
        assert len(detected) == 1
        assert detected[0].path == ref.path

    def test_stop_unknown_device_is_noop(self) -> None:
        """Stopping a device that was never registered must not raise."""
        watcher = EdgeWatcher()
        watcher.stop("never-registered")  # should not raise

    def test_stop_all_clears_all_watchers(self, tmp_path: Path) -> None:
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        dir_a.mkdir()
        dir_b.mkdir()
        watcher = EdgeWatcher()
        watcher.watch(dir_a, device_id="rig-a")
        watcher.watch(dir_b, device_id="rig-b")
        watcher.stop_all()
        assert watcher._observers == {}
        assert watcher._handlers == {}
