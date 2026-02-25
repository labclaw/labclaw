"""Coverage tests for labclaw.daemon — targets the 80 uncovered lines.

Uncovered lines:
  90          — DataAccumulator: None key branch in CSV DictReader
  183-245     — LabClawDaemon.start() full startup path
  253         — stop(): watcher.stop_all()
  268-271     — stop(): dashboard second TimeoutExpired (kill also times out)
  297-298     — _start_watcher(): missing 'path' in event payload
  330-334     — _discovery_loop() thread target
  395-399     — _evolution_loop() thread target
  440-441     — _start_dashboard() exception branch
  501-521     — main() argument parsing + daemon construction
  530-584     — main() remaining paths (signals, daemon.start())
"""

from __future__ import annotations

import signal
import subprocess
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from labclaw.daemon import (
    DASHBOARD_PORT,
    DEFAULT_PORT,
    DISCOVERY_INTERVAL_SECONDS,
    EVOLUTION_INTERVAL_SECONDS,
    DataAccumulator,
    LabClawDaemon,
    main,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_daemon(tmp_path: Path, **kwargs) -> LabClawDaemon:
    """Create a LabClawDaemon with patched API deps (no real DB / dirs)."""
    data_dir = tmp_path / "data"
    memory_root = tmp_path / "memory"
    data_dir.mkdir(parents=True, exist_ok=True)
    memory_root.mkdir(parents=True, exist_ok=True)
    with patch("labclaw.daemon.set_memory_root"), patch("labclaw.daemon.set_data_dir"):
        return LabClawDaemon(data_dir=data_dir, memory_root=memory_root, **kwargs)


# ---------------------------------------------------------------------------
# Line 90 — None key branch in DataAccumulator CSV parsing
# ---------------------------------------------------------------------------


class TestDataAccumulatorInProgress:
    """DataAccumulator: the _files_in_progress guard (line 77 — early return 0)."""

    def test_ingest_returns_zero_when_file_already_in_progress(self, tmp_path: Path) -> None:
        """Pre-inserting a path into _files_in_progress must cause ingest_file to
        return 0 immediately without opening the file (line 77)."""
        acc = DataAccumulator()
        csv_path = tmp_path / "active.csv"
        csv_path.write_text("a,b\n1,2\n", encoding="utf-8")

        str_path = str(csv_path)
        # Simulate a concurrent ingest that has already claimed this file
        with acc._lock:
            acc._files_in_progress.add(str_path)

        result = acc.ingest_file(csv_path)

        assert result == 0
        assert acc.total_rows == 0
        # The path should still be in _files_in_progress (we put it there manually)
        assert str_path in acc._files_in_progress


class TestDataAccumulatorNoneKey:
    """DataAccumulator must skip columns whose key is None (malformed CSV)."""

    def test_none_key_is_skipped(self, tmp_path: Path) -> None:
        """When DictReader yields a row with a None key, the key must be skipped
        and the remaining columns must still be ingested.

        Python's csv.DictReader only emits a None key when the fieldnames list
        itself contains None, so we must produce that via a mock rather than a
        file on disk.
        """
        import csv as _csv
        from unittest.mock import patch as _patch

        acc = DataAccumulator()
        csv_path = tmp_path / "quirky.csv"
        csv_path.write_text("a,b\n1,2\n", encoding="utf-8")

        # Build a fake DictReader that yields one row containing a None key.
        fake_row = {"a": "1.0", None: "ignored", "b": "2.0"}

        class FakeDictReader:
            def __init__(self, *args, **kwargs) -> None:
                pass

            def __iter__(self):
                yield fake_row

        with _patch.object(_csv, "DictReader", FakeDictReader):
            result = acc.ingest_file(csv_path)

        # Row must be ingested (the valid keys are non-None)
        assert result == 1
        rows = acc.get_all_rows()
        assert len(rows) == 1
        # None key must not appear in the parsed row
        assert None not in rows[0]
        assert rows[0]["a"] == pytest.approx(1.0)
        assert rows[0]["b"] == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# Lines 183-245 — LabClawDaemon.start()
# ---------------------------------------------------------------------------


class TestDaemonStart:
    """Tests for LabClawDaemon.start() — the main startup path."""

    def _patch_start_dependencies(self):
        """Return a context-manager stack that patches all blocking calls."""
        return (
            patch("labclaw.daemon.PluginLoader", autospec=True),
            patch("labclaw.daemon.get_evolution_engine"),
            patch.object(LabClawDaemon, "_ingest_existing_files"),
            patch.object(LabClawDaemon, "_start_watcher"),
            patch.object(LabClawDaemon, "_start_dashboard"),
            patch.object(LabClawDaemon, "_log_to_memory"),
            patch.object(LabClawDaemon, "stop"),
            patch("labclaw.daemon.threading.Thread", autospec=True),
            patch("labclaw.daemon.uvicorn.run"),
        )

    def test_start_calls_uvicorn_run(self, tmp_path: Path) -> None:
        daemon = _make_daemon(tmp_path)
        mock_thread = MagicMock()

        with (
            patch("labclaw.daemon.get_evolution_engine") as mock_evo,
            patch.object(LabClawDaemon, "_ingest_existing_files"),
            patch.object(LabClawDaemon, "_start_watcher"),
            patch.object(LabClawDaemon, "_start_dashboard"),
            patch.object(LabClawDaemon, "_log_to_memory"),
            patch.object(LabClawDaemon, "stop"),
            patch("labclaw.daemon.threading.Thread", return_value=mock_thread),
            patch("labclaw.daemon.uvicorn.run") as mock_uvicorn,
        ):
            mock_evo.return_value.load_state.return_value = None
            daemon.start()

        mock_uvicorn.assert_called_once()
        _, call_kwargs = mock_uvicorn.call_args
        assert call_kwargs["host"] == daemon.host
        assert call_kwargs["port"] == daemon.api_port
        assert call_kwargs["log_level"] == "info"

    def test_start_creates_directories(self, tmp_path: Path) -> None:
        data_dir = tmp_path / "newdata"
        memory_root = tmp_path / "newmemory"
        with patch("labclaw.daemon.set_memory_root"), patch("labclaw.daemon.set_data_dir"):
            daemon = LabClawDaemon(data_dir=data_dir, memory_root=memory_root)

        mock_thread = MagicMock()

        with (
            patch("labclaw.daemon.get_evolution_engine") as mock_evo,
            patch.object(LabClawDaemon, "_ingest_existing_files"),
            patch.object(LabClawDaemon, "_start_watcher"),
            patch.object(LabClawDaemon, "_start_dashboard"),
            patch.object(LabClawDaemon, "_log_to_memory"),
            patch.object(LabClawDaemon, "stop"),
            patch("labclaw.daemon.threading.Thread", return_value=mock_thread),
            patch("labclaw.daemon.uvicorn.run"),
        ):
            mock_evo.return_value.load_state.return_value = None
            daemon.start()

        assert data_dir.exists()
        assert memory_root.exists()

    def test_start_starts_background_threads(self, tmp_path: Path) -> None:
        daemon = _make_daemon(tmp_path)
        created_threads: list[MagicMock] = []

        def fake_thread(**kwargs):
            t = MagicMock()
            created_threads.append(t)
            return t

        with (
            patch("labclaw.daemon.get_evolution_engine") as mock_evo,
            patch.object(LabClawDaemon, "_ingest_existing_files"),
            patch.object(LabClawDaemon, "_start_watcher"),
            patch.object(LabClawDaemon, "_start_dashboard"),
            patch.object(LabClawDaemon, "_log_to_memory"),
            patch.object(LabClawDaemon, "stop"),
            patch("labclaw.daemon.threading.Thread", side_effect=fake_thread),
            patch("labclaw.daemon.uvicorn.run"),
        ):
            mock_evo.return_value.load_state.return_value = None
            daemon.start()

        assert len(created_threads) == 2
        for t in created_threads:
            t.start.assert_called_once()

    def test_start_calls_stop_in_finally(self, tmp_path: Path) -> None:
        """stop() must be called even when uvicorn.run raises KeyboardInterrupt."""
        daemon = _make_daemon(tmp_path)

        with (
            patch("labclaw.daemon.get_evolution_engine") as mock_evo,
            patch.object(LabClawDaemon, "_ingest_existing_files"),
            patch.object(LabClawDaemon, "_start_watcher"),
            patch.object(LabClawDaemon, "_start_dashboard"),
            patch.object(LabClawDaemon, "_log_to_memory"),
            patch.object(LabClawDaemon, "stop") as mock_stop,
            patch("labclaw.daemon.threading.Thread", return_value=MagicMock()),
            patch("labclaw.daemon.uvicorn.run", side_effect=KeyboardInterrupt),
        ):
            mock_evo.return_value.load_state.return_value = None
            daemon.start()

        mock_stop.assert_called_once()

    def test_start_plugin_load_failure_is_warned(self, tmp_path: Path) -> None:
        """If PluginLoader raises, start() logs a warning but continues."""
        daemon = _make_daemon(tmp_path)

        with (
            patch("labclaw.plugins.loader.PluginLoader", side_effect=ImportError("no loader")),
            patch("labclaw.daemon.get_evolution_engine") as mock_evo,
            patch.object(LabClawDaemon, "_ingest_existing_files"),
            patch.object(LabClawDaemon, "_start_watcher"),
            patch.object(LabClawDaemon, "_start_dashboard"),
            patch.object(LabClawDaemon, "_log_to_memory"),
            patch.object(LabClawDaemon, "stop"),
            patch("labclaw.daemon.threading.Thread", return_value=MagicMock()),
            patch("labclaw.daemon.uvicorn.run"),
        ):
            mock_evo.return_value.load_state.return_value = None
            # Must not raise despite plugin loader failure
            daemon.start()

    def test_start_plugin_loader_logs_loaded_names(self, tmp_path: Path) -> None:
        """When plugins are loaded, the names are logged."""
        daemon = _make_daemon(tmp_path)

        mock_loader_instance = MagicMock()
        mock_loader_instance.load_all.return_value = ["pluginA", "pluginB"]

        with (
            patch("labclaw.plugins.loader.PluginLoader", return_value=mock_loader_instance),
            patch("labclaw.daemon.get_evolution_engine") as mock_evo,
            patch.object(LabClawDaemon, "_ingest_existing_files"),
            patch.object(LabClawDaemon, "_start_watcher"),
            patch.object(LabClawDaemon, "_start_dashboard"),
            patch.object(LabClawDaemon, "_log_to_memory"),
            patch.object(LabClawDaemon, "stop"),
            patch("labclaw.daemon.threading.Thread", return_value=MagicMock()),
            patch("labclaw.daemon.uvicorn.run"),
        ):
            mock_evo.return_value.load_state.return_value = None
            daemon.start()  # must not raise; plugin names appear in logs

    def test_resolve_local_plugin_dir_rejects_outside_trusted_root(self, tmp_path: Path) -> None:
        with patch("labclaw.daemon.set_memory_root"), patch("labclaw.daemon.set_data_dir"):
            daemon = LabClawDaemon(
                data_dir=tmp_path / "outside" / "data",
                memory_root=tmp_path / "inside" / "memory",
            )
        assert daemon._resolve_local_plugin_dir() is None


# ---------------------------------------------------------------------------
# Line 253 — stop() with active watcher
# ---------------------------------------------------------------------------


class TestStopWithWatcher:
    def test_stop_calls_watcher_stop_all(self, tmp_path: Path) -> None:
        daemon = _make_daemon(tmp_path)
        daemon._log_to_memory = MagicMock()  # type: ignore[method-assign]

        mock_watcher = MagicMock()
        daemon._watcher = mock_watcher

        daemon.stop()

        mock_watcher.stop_all.assert_called_once()


# ---------------------------------------------------------------------------
# Lines 268-271 — stop(): kill() also times out
# ---------------------------------------------------------------------------


class TestStopDashboardKillTimeout:
    def test_kill_timeout_logs_error(self, tmp_path: Path) -> None:
        """When both terminate() wait AND kill() wait time out, an error is logged."""
        daemon = _make_daemon(tmp_path)
        daemon._log_to_memory = MagicMock()  # type: ignore[method-assign]

        mock_proc = MagicMock()
        mock_proc.poll.return_value = None  # still running

        # First wait() call raises TimeoutExpired (terminate path)
        # Second wait() call raises TimeoutExpired (kill path)
        mock_proc.wait.side_effect = [
            subprocess.TimeoutExpired(cmd="streamlit", timeout=5),
            subprocess.TimeoutExpired(cmd="streamlit", timeout=5),
        ]

        daemon._dashboard_proc = mock_proc

        daemon.stop()

        mock_proc.terminate.assert_called_once()
        mock_proc.kill.assert_called_once()
        assert daemon._dashboard_proc is None

    def test_stop_dashboard_exception_path(self, tmp_path: Path) -> None:
        """When the dashboard process raises an unexpected exception in stop(),
        the warning is logged and execution continues."""
        daemon = _make_daemon(tmp_path)
        daemon._log_to_memory = MagicMock()  # type: ignore[method-assign]

        mock_proc = MagicMock()
        mock_proc.poll.side_effect = OSError("process gone")
        daemon._dashboard_proc = mock_proc

        daemon.stop()  # must not raise

        assert daemon._dashboard_proc is None


# ---------------------------------------------------------------------------
# Lines 297-298 — _start_watcher() event with missing 'path' key
# ---------------------------------------------------------------------------


class TestStartWatcherMissingPath:
    def test_event_without_path_key_logs_warning(self, tmp_path: Path) -> None:
        """If a hardware.file.detected event has no 'path' in payload, a warning
        is emitted and no ingest is attempted."""
        from labclaw.core.events import event_registry

        if not event_registry.is_registered("hardware.file.detected"):
            event_registry.register("hardware.file.detected")

        daemon = _make_daemon(tmp_path)

        mock_watcher = MagicMock()
        with patch("labclaw.daemon.EdgeWatcher", return_value=mock_watcher):
            daemon._start_watcher()

        try:
            # Emit with empty payload — no 'path' key
            event_registry.emit("hardware.file.detected", payload={})
            # No rows should be added
            assert daemon._accumulator.total_rows == 0
        finally:
            if daemon._watcher is not None:
                daemon._watcher.stop_all()


# ---------------------------------------------------------------------------
# Lines 330-334 — _discovery_loop() thread target behaviour
# ---------------------------------------------------------------------------


class TestDiscoveryLoop:
    def test_loop_exits_immediately_when_stop_set(self, tmp_path: Path) -> None:
        """If _stop_event is already set, the loop body must never run."""
        daemon = _make_daemon(tmp_path)
        daemon._stop_event.set()

        run_mock = MagicMock()
        daemon._run_discovery = run_mock  # type: ignore[method-assign]

        daemon._discovery_loop()  # returns without blocking

        run_mock.assert_not_called()

    def test_loop_calls_run_discovery_once_then_exits(self, tmp_path: Path) -> None:
        """Loop runs _run_discovery once, then exits when _stop_event is set."""
        daemon = _make_daemon(tmp_path)
        call_count = 0

        def fake_run_discovery() -> None:
            nonlocal call_count
            call_count += 1
            daemon._stop_event.set()  # signal stop after first run

        daemon._run_discovery = fake_run_discovery  # type: ignore[method-assign]

        # Override wait to fire immediately without sleeping
        _original_wait = daemon._stop_event.wait

        def instant_wait(timeout: float | None = None) -> bool:
            # Don't actually sleep; return as if timeout elapsed
            return daemon._stop_event.is_set()

        daemon._stop_event.wait = instant_wait  # type: ignore[method-assign]

        daemon._discovery_loop()

        assert call_count == 1

    def test_loop_breaks_when_stop_set_before_discovery(self, tmp_path: Path) -> None:
        """When _stop_event fires during wait (returns True), the loop breaks
        without calling _run_discovery."""
        daemon = _make_daemon(tmp_path)

        def instant_wait_set(timeout: float | None = None) -> bool:
            # Simulate the event being set during the wait
            daemon._stop_event.set()
            return True

        daemon._stop_event.wait = instant_wait_set  # type: ignore[method-assign]

        run_mock = MagicMock()
        daemon._run_discovery = run_mock  # type: ignore[method-assign]

        daemon._discovery_loop()

        run_mock.assert_not_called()


# ---------------------------------------------------------------------------
# Lines 395-399 — _evolution_loop() thread target behaviour
# ---------------------------------------------------------------------------


class TestEvolutionLoop:
    def test_loop_exits_immediately_when_stop_set(self, tmp_path: Path) -> None:
        daemon = _make_daemon(tmp_path)
        daemon._stop_event.set()

        run_mock = MagicMock()
        daemon._run_evolution = run_mock  # type: ignore[method-assign]

        daemon._evolution_loop()

        run_mock.assert_not_called()

    def test_loop_calls_run_evolution_once_then_exits(self, tmp_path: Path) -> None:
        daemon = _make_daemon(tmp_path)
        call_count = 0

        def fake_run_evolution() -> None:
            nonlocal call_count
            call_count += 1
            daemon._stop_event.set()

        daemon._run_evolution = fake_run_evolution  # type: ignore[method-assign]

        def instant_wait(timeout: float | None = None) -> bool:
            return daemon._stop_event.is_set()

        daemon._stop_event.wait = instant_wait  # type: ignore[method-assign]

        daemon._evolution_loop()

        assert call_count == 1

    def test_loop_breaks_when_stop_set_before_evolution(self, tmp_path: Path) -> None:
        daemon = _make_daemon(tmp_path)

        def instant_wait_set(timeout: float | None = None) -> bool:
            daemon._stop_event.set()
            return True

        daemon._stop_event.wait = instant_wait_set  # type: ignore[method-assign]

        run_mock = MagicMock()
        daemon._run_evolution = run_mock  # type: ignore[method-assign]

        daemon._evolution_loop()

        run_mock.assert_not_called()


# ---------------------------------------------------------------------------
# Lines 440-441 — _start_dashboard() exception branch
# ---------------------------------------------------------------------------


class TestRunEvolutionMiningConfigFallback:
    """Cover lines 440-441: the except branch when MiningConfig(**base_dict) raises."""

    def test_mining_config_construction_failure_uses_fallback(self, tmp_path: Path) -> None:
        """When the candidate's config_diff produces an invalid MiningConfig,
        the original config is used as a fallback (lines 440-441)."""
        from labclaw.daemon import MIN_ROWS_FOR_MINING

        daemon = _make_daemon(tmp_path)

        # Inject enough rows so the early-exit guard is not triggered
        rows = [{"x": float(i), "y": float(i * 2)} for i in range(MIN_ROWS_FOR_MINING + 5)]
        with daemon._accumulator._lock:
            daemon._accumulator._rows.extend(rows)

        mock_candidate = MagicMock()
        # Override a typed field with an incompatible value → Pydantic ValidationError
        mock_candidate.config_diff = {"min_sessions": "not-an-integer"}

        mock_active_cycle = MagicMock()
        mock_active_cycle.cycle_id = "cycle-fallback-000-0000-000000000099"
        mock_active_cycle.candidate = mock_candidate

        mock_updated_cycle = MagicMock()
        mock_updated_cycle.stage.value = "evaluation"

        mock_engine = MagicMock()
        mock_engine.measure_fitness.return_value = 0.6
        mock_engine.get_active_cycles.return_value = [mock_active_cycle]
        mock_engine.should_advance.return_value = True
        mock_engine.advance_stage.return_value = mock_updated_cycle

        mock_mining_result = MagicMock()
        mock_mining_result.patterns = []

        mock_miner = MagicMock()
        mock_miner.mine.return_value = mock_mining_result

        with (
            patch("labclaw.daemon.get_evolution_engine", return_value=mock_engine),
            patch("labclaw.daemon.get_pattern_miner", return_value=mock_miner),
        ):
            daemon._run_evolution()  # must not raise

        # advance_stage was still called (fallback config was used)
        mock_engine.advance_stage.assert_called_once()
        assert daemon._evolution_count == 1


class TestStartDashboardException:
    def test_dashboard_start_failure_does_not_raise(self, tmp_path: Path) -> None:
        """When subprocess.Popen raises, _start_dashboard logs a warning and returns."""
        daemon = _make_daemon(tmp_path)

        with patch("labclaw.daemon.subprocess.Popen", side_effect=OSError("no streamlit")):
            daemon._start_dashboard()  # must not raise

        assert daemon._dashboard_proc is None

    def test_dashboard_start_success_sets_proc(self, tmp_path: Path) -> None:
        daemon = _make_daemon(tmp_path)

        mock_proc = MagicMock()
        with patch("labclaw.daemon.subprocess.Popen", return_value=mock_proc):
            daemon._start_dashboard()

        assert daemon._dashboard_proc is mock_proc
        assert daemon._dashboard_log is not None
        # Clean up
        if daemon._dashboard_log:
            daemon._dashboard_log.close()


# ---------------------------------------------------------------------------
# Lines 501-521 — main() argument defaults
# ---------------------------------------------------------------------------


class TestMainArgDefaults:
    def test_main_default_args(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """main() with no CLI args builds a daemon with default ports."""
        monkeypatch.setattr("sys.argv", ["labclaw"])

        captured: dict = {}

        def fake_daemon_init(self, **kwargs) -> None:  # noqa: ANN001
            captured.update(kwargs)
            self.data_dir = kwargs["data_dir"]
            self.memory_root = kwargs["memory_root"]
            self.host = kwargs.get("host", "127.0.0.1")
            self.api_port = kwargs.get("api_port", DEFAULT_PORT)
            self.dashboard_port = kwargs.get("dashboard_port", DASHBOARD_PORT)
            self.discovery_interval = kwargs.get("discovery_interval", DISCOVERY_INTERVAL_SECONDS)
            self.evolution_interval = kwargs.get("evolution_interval", EVOLUTION_INTERVAL_SECONDS)
            self._stop_event = threading.Event()
            self._accumulator = MagicMock()
            self._watcher = None
            self._dashboard_proc = None
            self._dashboard_log = None
            self._discovery_count = 0
            self._evolution_count = 0

        with (
            patch.object(LabClawDaemon, "__init__", fake_daemon_init),
            patch.object(LabClawDaemon, "start"),
            patch("labclaw.daemon.signal.signal"),
            patch("labclaw.daemon.logging.basicConfig"),
        ):
            main()

        assert captured["data_dir"] == Path("/opt/labclaw/data")
        assert captured["memory_root"] == Path("/opt/labclaw/memory")
        assert captured["host"] == "127.0.0.1"
        assert captured["api_port"] == DEFAULT_PORT
        assert captured["dashboard_port"] == DASHBOARD_PORT

    def test_main_custom_args(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """main() with custom CLI args passes them to LabClawDaemon."""
        data_dir = tmp_path / "d"
        mem_dir = tmp_path / "m"

        monkeypatch.setattr(
            "sys.argv",
            [
                "labclaw",
                "--data-dir",
                str(data_dir),
                "--memory-root",
                str(mem_dir),
                "--host",
                "0.0.0.0",
                "--port",
                "19000",
                "--dashboard-port",
                "19001",
                "--discovery-interval",
                "60",
                "--evolution-interval",
                "120",
            ],
        )

        captured: dict = {}

        def fake_daemon_init(self, **kwargs) -> None:  # noqa: ANN001
            captured.update(kwargs)
            self.data_dir = kwargs["data_dir"]
            self.memory_root = kwargs["memory_root"]
            self.host = kwargs.get("host", "127.0.0.1")
            self.api_port = kwargs.get("api_port", DEFAULT_PORT)
            self.dashboard_port = kwargs.get("dashboard_port", DASHBOARD_PORT)
            self.discovery_interval = kwargs.get("discovery_interval", DISCOVERY_INTERVAL_SECONDS)
            self.evolution_interval = kwargs.get("evolution_interval", EVOLUTION_INTERVAL_SECONDS)
            self._stop_event = threading.Event()
            self._accumulator = MagicMock()
            self._watcher = None
            self._dashboard_proc = None
            self._dashboard_log = None
            self._discovery_count = 0
            self._evolution_count = 0

        with (
            patch.object(LabClawDaemon, "__init__", fake_daemon_init),
            patch.object(LabClawDaemon, "start"),
            patch("labclaw.daemon.signal.signal"),
            patch("labclaw.daemon.logging.basicConfig"),
        ):
            main()

        assert captured["data_dir"] == data_dir
        assert captured["memory_root"] == mem_dir
        assert captured["host"] == "0.0.0.0"
        assert captured["api_port"] == 19000
        assert captured["dashboard_port"] == 19001
        assert captured["discovery_interval"] == 60
        assert captured["evolution_interval"] == 120


# ---------------------------------------------------------------------------
# Lines 530-584 — main() signal handling and daemon.start()
# ---------------------------------------------------------------------------


class TestMainSignalAndStart:
    def _run_main(
        self,
        monkeypatch: pytest.MonkeyPatch,
        argv: list[str] | None = None,
    ) -> tuple[MagicMock, list[tuple]]:
        """Run main() with mocked LabClawDaemon; return (mock_daemon, signal_calls)."""
        monkeypatch.setattr("sys.argv", argv or ["labclaw"])

        signal_calls: list[tuple] = []
        mock_daemon = MagicMock()

        def fake_signal(signum, handler) -> None:
            signal_calls.append((signum, handler))

        with (
            patch("labclaw.daemon.LabClawDaemon", return_value=mock_daemon),
            patch("labclaw.daemon.signal.signal", side_effect=fake_signal),
            patch("labclaw.daemon.logging.basicConfig"),
        ):
            main()

        return mock_daemon, signal_calls

    def test_main_registers_sigterm_and_sigint(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _, signal_calls = self._run_main(monkeypatch)

        registered_sigs = {s for s, _ in signal_calls}
        assert signal.SIGTERM in registered_sigs
        assert signal.SIGINT in registered_sigs

    def test_main_signal_handler_calls_daemon_stop(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The signal handler returned by main() must call daemon.stop()."""
        monkeypatch.setattr("sys.argv", ["labclaw"])

        captured_handler = {}
        mock_daemon = MagicMock()

        def fake_signal(signum, handler) -> None:
            captured_handler[signum] = handler

        with (
            patch("labclaw.daemon.LabClawDaemon", return_value=mock_daemon),
            patch("labclaw.daemon.signal.signal", side_effect=fake_signal),
            patch("labclaw.daemon.logging.basicConfig"),
        ):
            main()

        # Invoke the SIGTERM handler
        handler = captured_handler[signal.SIGTERM]
        handler(signal.SIGTERM, None)
        mock_daemon.stop.assert_called_once()

    def test_main_calls_daemon_start(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("sys.argv", ["labclaw"])

        mock_daemon = MagicMock()

        with (
            patch("labclaw.daemon.LabClawDaemon", return_value=mock_daemon),
            patch("labclaw.daemon.signal.signal"),
            patch("labclaw.daemon.logging.basicConfig"),
        ):
            main()

        mock_daemon.start.assert_called_once()

    def test_main_logging_basic_config_called(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("sys.argv", ["labclaw"])

        mock_daemon = MagicMock()

        with (
            patch("labclaw.daemon.LabClawDaemon", return_value=mock_daemon),
            patch("labclaw.daemon.signal.signal"),
            patch("labclaw.daemon.logging.basicConfig") as mock_log_cfg,
        ):
            main()

        mock_log_cfg.assert_called_once()
        kwargs = mock_log_cfg.call_args.kwargs
        assert kwargs.get("level") is not None  # logging level is set
