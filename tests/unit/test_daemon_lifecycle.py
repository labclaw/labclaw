"""Tests for LabClawDaemon lifecycle methods.

Covers: daemon init, stop, _ingest_existing_files, _log_to_memory, dashboard shutdown.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from labclaw.daemon import LabClawDaemon


def _make_daemon(tmp_path: Path, **kwargs) -> LabClawDaemon:
    """Helper: create a LabClawDaemon with patched API deps."""
    data_dir = tmp_path / "data"
    memory_root = tmp_path / "memory"
    data_dir.mkdir(parents=True, exist_ok=True)
    memory_root.mkdir(parents=True, exist_ok=True)
    with patch("labclaw.daemon.set_memory_root"), patch("labclaw.daemon.set_data_dir"):
        return LabClawDaemon(data_dir=data_dir, memory_root=memory_root, **kwargs)


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------


def test_init_stores_config(tmp_path: Path) -> None:
    data_dir = tmp_path / "mydata"
    memory_root = tmp_path / "mymemory"
    with patch("labclaw.daemon.set_memory_root"), patch("labclaw.daemon.set_data_dir"):
        daemon = LabClawDaemon(
            data_dir=data_dir,
            memory_root=memory_root,
            api_port=19900,
            dashboard_port=19901,
        )
    assert daemon.data_dir == data_dir
    assert daemon.memory_root == memory_root
    assert daemon.api_port == 19900
    assert daemon.dashboard_port == 19901


# ---------------------------------------------------------------------------
# Stop
# ---------------------------------------------------------------------------


def test_stop_sets_event(tmp_path: Path) -> None:
    daemon = _make_daemon(tmp_path)
    daemon._log_to_memory = MagicMock()  # type: ignore[assignment]
    daemon.stop()
    assert daemon._stop_event.is_set()


def test_stop_without_watcher(tmp_path: Path) -> None:
    daemon = _make_daemon(tmp_path)
    daemon._log_to_memory = MagicMock()  # type: ignore[assignment]
    assert daemon._watcher is None
    daemon.stop()  # must not raise


def test_stop_terminates_dashboard_proc(tmp_path: Path) -> None:
    daemon = _make_daemon(tmp_path)
    daemon._log_to_memory = MagicMock()  # type: ignore[assignment]

    mock_proc = MagicMock()
    mock_proc.poll.return_value = None  # still running
    daemon._dashboard_proc = mock_proc

    daemon.stop()

    mock_proc.terminate.assert_called_once()
    assert daemon._dashboard_proc is None


def test_stop_dashboard_already_exited(tmp_path: Path) -> None:
    daemon = _make_daemon(tmp_path)
    daemon._log_to_memory = MagicMock()  # type: ignore[assignment]

    mock_proc = MagicMock()
    mock_proc.poll.return_value = 0  # already exited
    daemon._dashboard_proc = mock_proc

    daemon.stop()

    mock_proc.terminate.assert_not_called()


def test_stop_closes_dashboard_log(tmp_path: Path) -> None:
    daemon = _make_daemon(tmp_path)
    daemon._log_to_memory = MagicMock()  # type: ignore[assignment]

    mock_log = MagicMock()
    daemon._dashboard_log = mock_log

    daemon.stop()

    mock_log.close.assert_called_once()
    assert daemon._dashboard_log is None


# ---------------------------------------------------------------------------
# _ingest_existing_files
# ---------------------------------------------------------------------------


def test_ingest_existing_files_finds_csvs(tmp_path: Path) -> None:
    daemon = _make_daemon(tmp_path)
    (daemon.data_dir / "run1.csv").write_text("x,y\n1.0,2.0\n3.0,4.0\n", encoding="utf-8")
    (daemon.data_dir / "run2.csv").write_text("x,y\n5.0,6.0\n", encoding="utf-8")

    daemon._ingest_existing_files()

    assert daemon._accumulator.total_rows == 3


def test_ingest_existing_files_empty_dir(tmp_path: Path) -> None:
    daemon = _make_daemon(tmp_path)
    daemon._ingest_existing_files()
    assert daemon._accumulator.total_rows == 0


def test_ingest_existing_files_ignores_non_tabular(tmp_path: Path) -> None:
    daemon = _make_daemon(tmp_path)
    (daemon.data_dir / "notes.md").write_text("# hello\n", encoding="utf-8")
    (daemon.data_dir / "data.csv").write_text("a,b\n1,2\n", encoding="utf-8")

    daemon._ingest_existing_files()

    assert daemon._accumulator.total_rows == 1


# ---------------------------------------------------------------------------
# _log_to_memory
# ---------------------------------------------------------------------------


def test_log_to_memory_success(tmp_path: Path) -> None:
    daemon = _make_daemon(tmp_path)

    mock_backend = MagicMock()
    with patch("labclaw.daemon.get_tier_a_backend", return_value=mock_backend):
        daemon._log_to_memory("system", "test_event", "detail text")

    mock_backend.append_memory.assert_called_once()
    call_args = mock_backend.append_memory.call_args
    assert call_args[0][0] == "system"


def test_log_to_memory_failure_does_not_raise(tmp_path: Path) -> None:
    daemon = _make_daemon(tmp_path)

    with patch("labclaw.daemon.get_tier_a_backend", side_effect=RuntimeError("backend down")):
        # must not propagate
        daemon._log_to_memory("system", "test_event", "detail text")
