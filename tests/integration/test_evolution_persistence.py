"""Integration tests for evolution state persistence across restarts."""

from __future__ import annotations

from pathlib import Path

import pytest

from labclaw.core.schemas import EvolutionStage, EvolutionTarget
from labclaw.evolution.engine import EvolutionEngine
from labclaw.evolution.schemas import EvolutionCandidate, FitnessScore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_candidate(
    target: EvolutionTarget = EvolutionTarget.ANALYSIS_PARAMS,
) -> EvolutionCandidate:
    return EvolutionCandidate(
        target=target,
        description="Test candidate",
        config_diff={"correlation_threshold": 0.4},
        proposed_by="test",
    )


def _make_fitness(
    target: EvolutionTarget = EvolutionTarget.ANALYSIS_PARAMS,
    pattern_count: float = 5.0,
) -> FitnessScore:
    return FitnessScore(
        target=target,
        metrics={"pattern_count": pattern_count, "coverage": 0.5},
        data_points=100,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestEvolutionPersistence:
    def test_persist_and_reload_cycles(self, tmp_path: Path) -> None:
        state_path = tmp_path / "evo_state.json"
        engine = EvolutionEngine()

        baseline = _make_fitness()
        candidate = _make_candidate()
        cycle = engine.start_cycle(candidate, baseline)
        cycle_id = cycle.cycle_id

        engine.persist_state(state_path)
        assert state_path.exists()

        engine2 = EvolutionEngine()
        engine2.load_state(state_path)

        restored = engine2.get_cycle(cycle_id)
        assert restored.cycle_id == cycle_id
        assert restored.stage == EvolutionStage.BACKTEST
        assert restored.candidate.description == "Test candidate"
        assert restored.baseline_fitness.metrics["pattern_count"] == 5.0

    def test_full_cycle_persist_reload(self, tmp_path: Path) -> None:
        state_path = tmp_path / "evo_state.json"
        engine = EvolutionEngine()

        baseline = _make_fitness()
        candidate = _make_candidate()
        cycle = engine.start_cycle(candidate, baseline)
        cid = cycle.cycle_id

        fitness = _make_fitness(pattern_count=6.0)

        # BACKTEST -> SHADOW
        engine.advance_stage(cid, fitness)
        assert engine.get_cycle(cid).stage == EvolutionStage.SHADOW

        # SHADOW -> CANARY
        engine.advance_stage(cid, fitness)
        assert engine.get_cycle(cid).stage == EvolutionStage.CANARY

        # CANARY -> PROMOTED
        engine.advance_stage(cid, fitness)
        promoted_cycle = engine.get_cycle(cid)
        assert promoted_cycle.stage == EvolutionStage.PROMOTED
        assert promoted_cycle.promoted is True

        engine.persist_state(state_path)

        engine2 = EvolutionEngine()
        engine2.load_state(state_path)

        restored = engine2.get_cycle(cid)
        assert restored.stage == EvolutionStage.PROMOTED
        assert restored.promoted is True
        assert restored.completed_at is not None

    def test_persist_load_empty_state(self, tmp_path: Path) -> None:
        state_path = tmp_path / "evo_state.json"
        engine = EvolutionEngine()
        engine.persist_state(state_path)

        engine2 = EvolutionEngine()
        engine2.load_state(state_path)
        assert engine2.get_history() == []

    def test_load_nonexistent_file(self, tmp_path: Path) -> None:
        state_path = tmp_path / "does_not_exist.json"
        engine = EvolutionEngine()
        # Should not raise
        engine.load_state(state_path)
        assert engine.get_history() == []

    def test_load_corrupt_file(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        state_path = tmp_path / "corrupt.json"
        state_path.write_text("{invalid json!!!")

        engine = EvolutionEngine()
        engine.load_state(state_path)
        # Should not crash, should log a warning/error
        assert engine.get_history() == []

    def test_fitness_history_persisted(self, tmp_path: Path) -> None:
        state_path = tmp_path / "evo_state.json"
        engine = EvolutionEngine()

        target = EvolutionTarget.ANALYSIS_PARAMS
        engine.measure_fitness(target, {"pattern_count": 3.0}, data_points=50)
        engine.measure_fitness(target, {"pattern_count": 5.0}, data_points=100)

        engine.persist_state(state_path)

        engine2 = EvolutionEngine()
        engine2.load_state(state_path)

        history = engine2.fitness_tracker.get_history(target)
        assert len(history) == 2
        assert history[0].metrics["pattern_count"] == 3.0
        assert history[1].metrics["pattern_count"] == 5.0
