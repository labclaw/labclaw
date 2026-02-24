"""Tests for _FileEventHandler and FileWatcherDriver.

Covers file_watcher.py lines: 39-40, 43-56, 59, 62, 66-69, 124-150.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from labclaw.hardware.drivers.file_watcher import FileWatcherDriver, _FileEventHandler

# ---------------------------------------------------------------------------
# _FileEventHandler — pattern matching
# ---------------------------------------------------------------------------


class TestFileEventHandlerMatches:
    def test_handler_matches_csv_pattern(self) -> None:
        handler = _FileEventHandler(["*.csv"], "dev-01")
        assert handler._matches(Path("data.csv")) is True

    def test_handler_rejects_non_matching_extension(self) -> None:
        handler = _FileEventHandler(["*.csv"], "dev-01")
        assert handler._matches(Path("data.json")) is False

    def test_handler_matches_multiple_patterns(self) -> None:
        handler = _FileEventHandler(["*.csv", "*.tsv"], "dev-01")
        assert handler._matches(Path("data.tsv")) is True

    def test_handler_empty_patterns_matches_nothing(self) -> None:
        handler = _FileEventHandler([], "dev-01")
        assert handler._matches(Path("data.csv")) is False


# ---------------------------------------------------------------------------
# _FileEventHandler — on_created queuing
# ---------------------------------------------------------------------------


class TestFileEventHandlerOnCreated:
    def _make_event(self, src_path: str | bytes, is_directory: bool = False) -> MagicMock:
        evt = MagicMock()
        evt.src_path = src_path
        evt.is_directory = is_directory
        return evt

    def test_on_created_queues_file(self) -> None:
        handler = _FileEventHandler(["*.csv"], "dev-01")
        handler.on_created(self._make_event("/tmp/data.csv"))
        paths = handler.drain()
        assert paths == [Path("/tmp/data.csv")]

    def test_on_created_skips_directory(self) -> None:
        handler = _FileEventHandler(["*.csv"], "dev-01")
        handler.on_created(self._make_event("/tmp/mydir", is_directory=True))
        assert handler.drain() == []

    def test_on_created_skips_non_matching_extension(self) -> None:
        handler = _FileEventHandler(["*.csv"], "dev-01")
        handler.on_created(self._make_event("/tmp/data.json"))
        assert handler.drain() == []

    def test_on_created_bytes_path_decoded(self) -> None:
        handler = _FileEventHandler(["*.csv"], "dev-01")
        handler.on_created(self._make_event(b"/tmp/data.csv"))
        paths = handler.drain()
        assert paths == [Path("/tmp/data.csv")]


# ---------------------------------------------------------------------------
# _FileEventHandler — on_modified queuing
# ---------------------------------------------------------------------------


class TestFileEventHandlerOnModified:
    def _make_event(self, src_path: str, is_directory: bool = False) -> MagicMock:
        evt = MagicMock()
        evt.src_path = src_path
        evt.is_directory = is_directory
        return evt

    def test_on_modified_queues_file(self) -> None:
        handler = _FileEventHandler(["*.csv"], "dev-01")
        evt = self._make_event("/tmp/updated.csv")
        handler.on_modified(evt)
        assert handler.drain() == [Path("/tmp/updated.csv")]

    def test_on_modified_skips_directory(self) -> None:
        handler = _FileEventHandler(["*.csv"], "dev-01")
        handler.on_modified(self._make_event("/tmp/dir", is_directory=True))
        assert handler.drain() == []


# ---------------------------------------------------------------------------
# _FileEventHandler — drain clears the queue
# ---------------------------------------------------------------------------


class TestFileEventHandlerDrain:
    def _make_event(self, src_path: str) -> MagicMock:
        evt = MagicMock()
        evt.src_path = src_path
        evt.is_directory = False
        return evt

    def test_drain_returns_all_queued_files(self) -> None:
        handler = _FileEventHandler(["*.csv"], "dev-01")
        handler.on_created(self._make_event("/tmp/a.csv"))
        handler.on_created(self._make_event("/tmp/b.csv"))
        paths = handler.drain()
        assert len(paths) == 2

    def test_drain_clears_queue(self) -> None:
        handler = _FileEventHandler(["*.csv"], "dev-01")
        handler.on_created(self._make_event("/tmp/a.csv"))
        handler.drain()
        assert handler.drain() == []


# ---------------------------------------------------------------------------
# FileWatcherDriver.read — no handler branch
# ---------------------------------------------------------------------------


class TestFileWatcherDriverRead:
    @pytest.mark.asyncio
    async def test_read_no_handler_returns_empty(self, tmp_path: Path) -> None:
        """Driver with _handler=None returns empty result."""
        driver = FileWatcherDriver(
            device_id="fw-01",
            device_type="camera",
            watch_path=tmp_path,
            file_patterns=["*.csv"],
        )
        # Do NOT call connect() — _handler stays None
        result = await driver.read()
        assert result == {"new_files": [], "data": None}

    @pytest.mark.asyncio
    async def test_read_with_handler_drains_queued_files(self, tmp_path: Path) -> None:
        """After injecting a handler with queued files, read() returns them."""
        driver = FileWatcherDriver(
            device_id="fw-02",
            device_type="camera",
            watch_path=tmp_path,
            file_patterns=["*.csv"],
        )
        # Inject a handler with a pre-queued file (no actual observer needed)
        handler = _FileEventHandler(["*.csv"], "fw-02")
        (tmp_path / "data.csv").touch()
        mock_evt = MagicMock()
        mock_evt.src_path = str(tmp_path / "data.csv")
        mock_evt.is_directory = False
        handler.on_created(mock_evt)
        driver._handler = handler

        result = await driver.read()
        assert len(result["new_files"]) == 1
        assert str(tmp_path / "data.csv") in result["new_files"][0]
