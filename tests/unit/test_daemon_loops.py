"""Tests for LabClawDaemon._run_discovery and _run_evolution daemon loops.

Covers lines 337-387 and 403-478 in src/labclaw/daemon.py.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from labclaw.daemon import MIN_ROWS_FOR_MINING, LabClawDaemon

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_daemon(tmp_path: Path) -> LabClawDaemon:
    data_dir = tmp_path / "data"
    memory_root = tmp_path / "memory"
    data_dir.mkdir(parents=True, exist_ok=True)
    memory_root.mkdir(parents=True, exist_ok=True)
    with patch("labclaw.daemon.set_memory_root"), patch("labclaw.daemon.set_data_dir"):
        daemon = LabClawDaemon(data_dir=data_dir, memory_root=memory_root)
    # Silence memory writes in all tests
    daemon._log_to_memory = MagicMock()  # type: ignore[method-assign]
    return daemon


def _inject_rows(daemon: LabClawDaemon, n: int) -> None:
    """Push n synthetic rows into the accumulator without touching the filesystem."""
    rows = [{"x": float(i), "y": float(i * 2)} for i in range(n)]
    with daemon._accumulator._lock:
        daemon._accumulator._rows.extend(rows)


# ---------------------------------------------------------------------------
# _run_discovery
# ---------------------------------------------------------------------------


class TestRunDiscovery:
    def test_skips_when_too_few_rows(self, tmp_path: Path) -> None:
        daemon = _make_daemon(tmp_path)
        assert daemon._accumulator.total_rows < MIN_ROWS_FOR_MINING
        # Must not raise and discovery count must remain 0
        daemon._run_discovery()
        assert daemon._discovery_count == 0

    def test_does_not_crash_when_orchestrator_raises(self, tmp_path: Path) -> None:
        """If the orchestrator import or run fails, the daemon must swallow the error."""
        daemon = _make_daemon(tmp_path)
        _inject_rows(daemon, MIN_ROWS_FOR_MINING + 5)

        # get_llm_provider is imported inside _run_discovery from labclaw.api.deps
        with patch("labclaw.api.deps.get_llm_provider", side_effect=RuntimeError("no llm")):
            daemon._run_discovery()  # must not raise

        # discovery_count stays 0 because the error happened before the increment
        assert daemon._discovery_count == 0

    def test_increments_count_on_success(self, tmp_path: Path) -> None:
        daemon = _make_daemon(tmp_path)
        _inject_rows(daemon, MIN_ROWS_FOR_MINING + 5)

        mock_result = SimpleNamespace(
            patterns_found=3,
            hypotheses_generated=2,
            total_duration=1.0,
            cycle_id="abc12345-abcd-abcd-abcd-abcdefabcdef",
        )
        mock_loop = MagicMock()
        mock_loop_cls = MagicMock(return_value=mock_loop)

        # asyncio.run is called inside _run_discovery; return the mock result directly
        with (
            patch("labclaw.api.deps.get_llm_provider", return_value=MagicMock()),
            patch("labclaw.orchestrator.loop.ScientificLoop", mock_loop_cls),
            patch("asyncio.run", return_value=mock_result),
        ):
            daemon._run_discovery()

        # If the orchestrator succeeded, count increments
        assert daemon._discovery_count == 1


# ---------------------------------------------------------------------------
# _run_evolution
# ---------------------------------------------------------------------------


class TestRunEvolution:
    def test_skips_when_too_few_rows(self, tmp_path: Path) -> None:
        daemon = _make_daemon(tmp_path)
        assert daemon._accumulator.total_rows < MIN_ROWS_FOR_MINING
        daemon._run_evolution()
        assert daemon._evolution_count == 0

    def test_does_not_crash_when_engine_raises(self, tmp_path: Path) -> None:
        daemon = _make_daemon(tmp_path)
        _inject_rows(daemon, MIN_ROWS_FOR_MINING + 5)

        with patch(
            "labclaw.daemon.get_evolution_engine", side_effect=RuntimeError("engine broken")
        ):
            daemon._run_evolution()  # must not raise

        assert daemon._evolution_count == 0

    def test_starts_new_cycle_when_no_active_cycles(self, tmp_path: Path) -> None:
        daemon = _make_daemon(tmp_path)
        _inject_rows(daemon, MIN_ROWS_FOR_MINING + 5)

        # Build minimal mock objects
        mock_candidate = MagicMock()
        mock_candidate.config_diff = {}

        mock_cycle = MagicMock()
        mock_cycle.cycle_id = "cycle-0001-0000-0000-000000000001"

        mock_engine = MagicMock()
        mock_engine.measure_fitness.return_value = 0.5
        mock_engine.get_active_cycles.return_value = []  # no active cycles
        mock_engine.propose_candidates.return_value = [mock_candidate]
        mock_engine.start_cycle.return_value = mock_cycle

        mock_mining_result = MagicMock()
        mock_mining_result.patterns = []

        mock_miner = MagicMock()
        mock_miner.mine.return_value = mock_mining_result

        with (
            patch("labclaw.daemon.get_evolution_engine", return_value=mock_engine),
            patch("labclaw.daemon.get_pattern_miner", return_value=mock_miner),
        ):
            daemon._run_evolution()

        mock_engine.start_cycle.assert_called_once_with(mock_candidate, 0.5)
        assert daemon._evolution_count == 1

    def test_advances_existing_active_cycle(self, tmp_path: Path) -> None:
        daemon = _make_daemon(tmp_path)
        _inject_rows(daemon, MIN_ROWS_FOR_MINING + 5)

        mock_candidate = MagicMock()
        mock_candidate.config_diff = {}

        mock_active_cycle = MagicMock()
        mock_active_cycle.cycle_id = "cycle-active-000-0000-000000000002"
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
            daemon._run_evolution()

        mock_engine.advance_stage.assert_called_once()
        assert daemon._evolution_count == 1

    def test_skips_advance_when_should_advance_false(self, tmp_path: Path) -> None:
        daemon = _make_daemon(tmp_path)
        _inject_rows(daemon, MIN_ROWS_FOR_MINING + 5)

        mock_active_cycle = MagicMock()
        mock_active_cycle.cycle_id = "cycle-noadv-000-0000-000000000003"

        mock_engine = MagicMock()
        mock_engine.measure_fitness.return_value = 0.4
        mock_engine.get_active_cycles.return_value = [mock_active_cycle]
        mock_engine.should_advance.return_value = False  # no advance

        mock_mining_result = MagicMock()
        mock_mining_result.patterns = []
        mock_miner = MagicMock()
        mock_miner.mine.return_value = mock_mining_result

        with (
            patch("labclaw.daemon.get_evolution_engine", return_value=mock_engine),
            patch("labclaw.daemon.get_pattern_miner", return_value=mock_miner),
        ):
            daemon._run_evolution()

        mock_engine.advance_stage.assert_not_called()
        assert daemon._evolution_count == 0

    def test_persists_state_after_run(self, tmp_path: Path) -> None:
        daemon = _make_daemon(tmp_path)
        _inject_rows(daemon, MIN_ROWS_FOR_MINING + 5)

        mock_engine = MagicMock()
        mock_engine.measure_fitness.return_value = 0.5
        mock_engine.get_active_cycles.return_value = []
        mock_engine.propose_candidates.return_value = []  # nothing to start

        mock_mining_result = MagicMock()
        mock_mining_result.patterns = []
        mock_miner = MagicMock()
        mock_miner.mine.return_value = mock_mining_result

        with (
            patch("labclaw.daemon.get_evolution_engine", return_value=mock_engine),
            patch("labclaw.daemon.get_pattern_miner", return_value=mock_miner),
        ):
            daemon._run_evolution()

        mock_engine.persist_state.assert_called_once()
        expected_path = daemon.memory_root / "evolution_state.json"
        mock_engine.persist_state.assert_called_once_with(expected_path)
