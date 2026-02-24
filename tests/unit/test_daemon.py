from __future__ import annotations

import io
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from labclaw.api.deps import get_data_dir, reset_all
from labclaw.core.events import event_registry
from labclaw.daemon import DataAccumulator, LabClawDaemon
from labclaw.memory.markdown import MemoryEntry, TierABackend


def test_data_accumulator_retries_after_initial_failure(tmp_path: Path) -> None:
    acc = DataAccumulator()
    csv_path = tmp_path / "input.csv"

    # First ingest fails because the file is not there yet.
    assert acc.ingest_file(csv_path) == 0
    assert acc.files_processed == 0

    csv_path.write_text("a,b\n1,2\n", encoding="utf-8")

    # Second ingest should now work (path was not permanently marked as processed).
    assert acc.ingest_file(csv_path) == 1
    assert acc.total_rows == 1
    assert acc.files_processed == 1


def test_data_accumulator_retries_after_zero_row_read(tmp_path: Path) -> None:
    acc = DataAccumulator()
    csv_path = tmp_path / "delayed.csv"
    csv_path.write_text("a,b\n", encoding="utf-8")

    # First read parses zero rows and should not permanently mark the file.
    assert acc.ingest_file(csv_path) == 0
    assert acc.files_processed == 0

    csv_path.write_text("a,b\n1,2\n", encoding="utf-8")

    # Second read after late write should now ingest successfully.
    assert acc.ingest_file(csv_path) == 1
    assert acc.total_rows == 1
    assert acc.files_processed == 1


def test_data_accumulator_ingests_appended_rows_once(tmp_path: Path) -> None:
    acc = DataAccumulator()
    csv_path = tmp_path / "append.csv"
    csv_path.write_text("a,b\n1,2\n", encoding="utf-8")

    assert acc.ingest_file(csv_path) == 1
    assert acc.ingest_file(csv_path) == 0

    with csv_path.open("a", encoding="utf-8") as f:
        f.write("3,4\n")

    assert acc.ingest_file(csv_path) == 1
    assert acc.total_rows == 2
    assert acc.files_processed == 1


def test_data_accumulator_resets_cursor_after_truncation(tmp_path: Path) -> None:
    acc = DataAccumulator()
    csv_path = tmp_path / "reuse.csv"
    csv_path.write_text("a,b\n1,2\n2,3\n", encoding="utf-8")
    assert acc.ingest_file(csv_path) == 2

    # Simulate instrument run restarting and rewriting the same path.
    csv_path.write_text("a,b\n9,10\n", encoding="utf-8")
    assert acc.ingest_file(csv_path) == 1
    assert acc.total_rows == 3
    assert acc.files_processed == 1


def test_daemon_ingests_detected_file_event(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    memory_root = tmp_path / "memory"
    data_dir.mkdir()
    memory_root.mkdir()

    csv_path = data_dir / "session.csv"
    csv_path.write_text("latency,accuracy\n10.5,0.89\n", encoding="utf-8")

    if not event_registry.is_registered("hardware.file.detected"):
        event_registry.register("hardware.file.detected")

    daemon = LabClawDaemon(data_dir=data_dir, memory_root=memory_root)
    daemon._start_watcher()
    try:
        event_registry.emit(
            "hardware.file.detected",
            payload={"path": str(csv_path), "device_id": "test-device"},
        )
        assert daemon._accumulator.files_processed == 1
        assert daemon._accumulator.total_rows == 1
    finally:
        if daemon._watcher is not None:
            daemon._watcher.stop_all()


def test_daemon_sets_api_data_dir_override(tmp_path: Path) -> None:
    reset_all()
    try:
        data_dir = tmp_path / "custom-data"
        memory_root = tmp_path / "memory"
        LabClawDaemon(data_dir=data_dir, memory_root=memory_root)
        assert get_data_dir() == data_dir.resolve()
    finally:
        reset_all()


def test_daemon_stop_kills_dashboard_after_timeout(tmp_path: Path) -> None:
    class SlowDashboardProcess:
        def __init__(self) -> None:
            self.terminated = False
            self.killed = False
            self._wait_calls = 0

        def poll(self) -> None:
            return None

        def terminate(self) -> None:
            self.terminated = True

        def wait(self, timeout: int) -> None:
            self._wait_calls += 1
            if self._wait_calls == 1:
                raise subprocess.TimeoutExpired(cmd="streamlit", timeout=timeout)

        def kill(self) -> None:
            self.killed = True

    daemon = LabClawDaemon(
        data_dir=tmp_path / "data",
        memory_root=tmp_path / "memory",
    )
    proc = SlowDashboardProcess()
    daemon._dashboard_proc = proc  # type: ignore[assignment]
    daemon._dashboard_log = io.StringIO()
    daemon._log_to_memory = lambda *args, **kwargs: None  # type: ignore[assignment]

    daemon.stop()

    assert proc.terminated is True
    assert proc.killed is True
    assert daemon._dashboard_proc is None
    assert daemon._dashboard_log is None


def test_tier_a_backend_rejects_path_traversal_entity_ids(tmp_path: Path) -> None:
    backend = TierABackend(root=tmp_path / "memory")
    entry = MemoryEntry(timestamp=datetime.now(UTC), category="note", detail="x")

    for bad_entity_id in ("../escape", "a/b", "..", ""):
        try:
            backend.append_memory(bad_entity_id, entry)
        except ValueError:
            continue
        raise AssertionError(f"Expected ValueError for entity_id {bad_entity_id!r}")
