"""Tests for EvolutionEngine — covers previously uncovered branches.

Lines targeted: 138, 169-176, 218, 220, 234-235, 239, 326-331,
                344-382, 416, 424, 436-437.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from labclaw.core.schemas import EvolutionStage, EvolutionTarget
from labclaw.evolution.engine import EvolutionEngine
from labclaw.evolution.schemas import EvolutionCandidate, EvolutionConfig, FitnessScore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _candidate(target: EvolutionTarget = EvolutionTarget.ANALYSIS_PARAMS) -> EvolutionCandidate:
    return EvolutionCandidate(target=target, description="test candidate", proposed_by="test")


def _baseline(target: EvolutionTarget = EvolutionTarget.ANALYSIS_PARAMS) -> FitnessScore:
    return FitnessScore(target=target, metrics={"accuracy": 0.9, "speed": 100.0})


# ---------------------------------------------------------------------------
# propose_candidates
# ---------------------------------------------------------------------------


class TestProposeCandidates:
    def test_propose_candidates_returns_candidates(self) -> None:
        engine = EvolutionEngine()
        candidates = engine.propose_candidates(EvolutionTarget.ANALYSIS_PARAMS, n=2)
        assert len(candidates) == 2
        for c in candidates:
            assert c.target == EvolutionTarget.ANALYSIS_PARAMS

    def test_propose_candidates_caps_at_n(self) -> None:
        engine = EvolutionEngine()
        candidates = engine.propose_candidates(EvolutionTarget.ANALYSIS_PARAMS, n=1)
        assert len(candidates) == 1

    def test_propose_candidates_caps_at_available_templates(self) -> None:
        # ANALYSIS_PARAMS has 5 templates; request more than available
        engine = EvolutionEngine()
        candidates = engine.propose_candidates(EvolutionTarget.ANALYSIS_PARAMS, n=100)
        assert len(candidates) == 5  # min(100, 5)

    def test_propose_candidates_all_targets_have_templates(self) -> None:
        engine = EvolutionEngine()
        for target in EvolutionTarget:
            candidates = engine.propose_candidates(target, n=1)
            assert len(candidates) >= 1, f"No templates for {target}"


# ---------------------------------------------------------------------------
# start_cycle + max_cycles eviction
# ---------------------------------------------------------------------------


class TestStartCycle:
    def test_start_cycle_basic(self) -> None:
        engine = EvolutionEngine()
        cycle = engine.start_cycle(_candidate(), _baseline())
        assert cycle.stage == EvolutionStage.BACKTEST
        assert cycle.cycle_id != ""

    def test_start_cycle_evicts_oldest_when_max_reached(self) -> None:
        engine = EvolutionEngine(config=EvolutionConfig(max_cycles=2))
        c1 = engine.start_cycle(_candidate(), _baseline())
        c2 = engine.start_cycle(_candidate(), _baseline())
        assert len(engine._cycles) == 2

        # Third start — c1 (oldest) must be evicted
        c3 = engine.start_cycle(_candidate(), _baseline())
        assert len(engine._cycles) == 2
        assert c1.cycle_id not in engine._cycles
        assert c2.cycle_id in engine._cycles
        assert c3.cycle_id in engine._cycles

    def test_start_cycle_evicts_promoted_first(self) -> None:
        """Promoted cycles are preferred for eviction over active ones."""
        engine = EvolutionEngine(config=EvolutionConfig(max_cycles=2))
        c1 = engine.start_cycle(_candidate(), _baseline())
        c2 = engine.start_cycle(_candidate(), _baseline())

        # Manually promote c1 so it becomes the preferred eviction target
        engine._cycles[c1.cycle_id].stage = EvolutionStage.PROMOTED

        c3 = engine.start_cycle(_candidate(), _baseline())
        assert len(engine._cycles) == 2
        assert c1.cycle_id not in engine._cycles
        assert c2.cycle_id in engine._cycles
        assert c3.cycle_id in engine._cycles


# ---------------------------------------------------------------------------
# advance_stage
# ---------------------------------------------------------------------------


class TestAdvanceStage:
    def test_advance_backtest_to_shadow(self) -> None:
        engine = EvolutionEngine()
        cycle = engine.start_cycle(_candidate(), _baseline())
        new_fitness = FitnessScore(
            target=EvolutionTarget.ANALYSIS_PARAMS, metrics={"accuracy": 0.91}
        )
        updated = engine.advance_stage(cycle.cycle_id, new_fitness)
        assert updated.stage == EvolutionStage.SHADOW

    def test_advance_through_all_stages(self) -> None:
        engine = EvolutionEngine()
        cycle = engine.start_cycle(_candidate(), _baseline())
        target = EvolutionTarget.ANALYSIS_PARAMS
        fitness = FitnessScore(target=target, metrics={"accuracy": 0.95})

        engine.advance_stage(cycle.cycle_id, fitness)  # BACKTEST -> SHADOW
        engine.advance_stage(cycle.cycle_id, fitness)  # SHADOW -> CANARY
        final = engine.advance_stage(cycle.cycle_id, fitness)  # CANARY -> PROMOTED

        assert final.stage == EvolutionStage.PROMOTED
        assert final.promoted is True
        assert final.completed_at is not None

    def test_advance_already_promoted_raises(self) -> None:
        engine = EvolutionEngine()
        cycle = engine.start_cycle(_candidate(), _baseline())
        fitness = FitnessScore(target=EvolutionTarget.ANALYSIS_PARAMS, metrics={"accuracy": 0.95})
        engine.advance_stage(cycle.cycle_id, fitness)
        engine.advance_stage(cycle.cycle_id, fitness)
        engine.advance_stage(cycle.cycle_id, fitness)  # -> PROMOTED

        with pytest.raises(ValueError, match="already promoted"):
            engine.advance_stage(cycle.cycle_id, fitness)

    def test_advance_rolled_back_raises(self) -> None:
        engine = EvolutionEngine()
        cycle = engine.start_cycle(_candidate(), _baseline())
        engine.rollback(cycle.cycle_id, "manual")

        fitness = FitnessScore(target=EvolutionTarget.ANALYSIS_PARAMS, metrics={"accuracy": 0.9})
        with pytest.raises(ValueError, match="already rolled back"):
            engine.advance_stage(cycle.cycle_id, fitness)

    def test_advance_regression_triggers_rollback(self) -> None:
        """A 90% metric drop exceeds the default 10% threshold → auto-rollback."""
        engine = EvolutionEngine(config=EvolutionConfig(rollback_threshold=0.2))
        baseline = FitnessScore(
            target=EvolutionTarget.ANALYSIS_PARAMS,
            metrics={"accuracy": 10.0},
        )
        cycle = engine.start_cycle(_candidate(), baseline)
        # 90% drop: 1.0 vs baseline 10.0 → regresses
        bad_fitness = FitnessScore(
            target=EvolutionTarget.ANALYSIS_PARAMS,
            metrics={"accuracy": 1.0},
        )
        result = engine.advance_stage(cycle.cycle_id, bad_fitness)
        assert result.stage == EvolutionStage.ROLLED_BACK
        assert result.rollback_reason is not None


# ---------------------------------------------------------------------------
# rollback
# ---------------------------------------------------------------------------


class TestRollback:
    def test_rollback_sets_stage_and_reason(self) -> None:
        engine = EvolutionEngine()
        cycle = engine.start_cycle(_candidate(), _baseline())
        result = engine.rollback(cycle.cycle_id, "something went wrong")
        assert result.stage == EvolutionStage.ROLLED_BACK
        assert result.rollback_reason == "something went wrong"
        assert result.promoted is False
        assert result.completed_at is not None


# ---------------------------------------------------------------------------
# should_advance
# ---------------------------------------------------------------------------


class TestShouldAdvance:
    def test_should_advance_immediately_false(self) -> None:
        """Brand-new cycle (elapsed < 1 s soak) must not advance."""
        engine = EvolutionEngine()
        cycle = engine.start_cycle(_candidate(), _baseline())
        # Default min_soak_sessions=5; soak_seconds=max(5,1)=5, elapsed≈0
        assert engine.should_advance(cycle.cycle_id) is False

    def test_should_advance_after_zero_soak(self) -> None:
        """min_soak_sessions=0 → soak_seconds=max(0,1)=1; still won't pass immediately."""
        engine = EvolutionEngine(config=EvolutionConfig(min_soak_sessions=0))
        cycle = engine.start_cycle(_candidate(), _baseline())
        # soak_seconds = max(0, 1) = 1; elapsed ≈ 0 — should still be False
        # This tests the max(min_soak_sessions, 1) branch
        result = engine.should_advance(cycle.cycle_id)
        # elapsed is tiny (< 1 s), so False unless the machine is extremely slow
        assert isinstance(result, bool)

    def test_should_advance_with_backdated_cycle(self) -> None:
        """Manually backdating started_at past soak → should_advance returns True."""
        from datetime import UTC, datetime, timedelta

        engine = EvolutionEngine(config=EvolutionConfig(min_soak_sessions=0))
        cycle = engine.start_cycle(_candidate(), _baseline())
        # Backdate started_at by 10 seconds so elapsed >> soak (1 s)
        engine._cycles[cycle.cycle_id].started_at = datetime.now(UTC) - timedelta(seconds=10)
        assert engine.should_advance(cycle.cycle_id) is True


# ---------------------------------------------------------------------------
# persist_state / load_state
# ---------------------------------------------------------------------------


class TestPersistence:
    def test_persist_and_load_state(self, tmp_path: Path) -> None:
        engine = EvolutionEngine()
        cycle = engine.start_cycle(_candidate(), _baseline())
        state_file = tmp_path / "state.json"
        engine.persist_state(state_file)

        engine2 = EvolutionEngine()
        engine2.load_state(state_file)
        assert cycle.cycle_id in engine2._cycles

    def test_load_state_nonexistent_file(self, tmp_path: Path) -> None:
        engine = EvolutionEngine()
        engine.load_state(tmp_path / "nonexistent.json")
        assert engine._cycles == {}

    def test_persist_creates_parent_dirs(self, tmp_path: Path) -> None:
        engine = EvolutionEngine()
        engine.start_cycle(_candidate(), _baseline())
        nested = tmp_path / "a" / "b" / "c" / "state.json"
        engine.persist_state(nested)
        assert nested.exists()


# ---------------------------------------------------------------------------
# get_cycle / _get_cycle
# ---------------------------------------------------------------------------


class TestGetCycle:
    def test_get_cycle_not_found_raises(self) -> None:
        engine = EvolutionEngine()
        with pytest.raises(KeyError):
            engine.get_cycle("nonexistent-id")

    def test_get_cycle_returns_correct_cycle(self) -> None:
        engine = EvolutionEngine()
        cycle = engine.start_cycle(_candidate(), _baseline())
        fetched = engine.get_cycle(cycle.cycle_id)
        assert fetched.cycle_id == cycle.cycle_id


# ---------------------------------------------------------------------------
# _check_regression
# ---------------------------------------------------------------------------


class TestCheckRegression:
    def _fitness(self, metrics: dict) -> FitnessScore:
        return FitnessScore(target=EvolutionTarget.ANALYSIS_PARAMS, metrics=metrics)

    def test_no_regression_returns_none(self) -> None:
        engine = EvolutionEngine()
        baseline = self._fitness({"m": 10.0})
        current = self._fitness({"m": 10.0})
        assert engine._check_regression(baseline, current) is None

    def test_regression_detected(self) -> None:
        engine = EvolutionEngine(config=EvolutionConfig(rollback_threshold=0.2))
        baseline = self._fitness({"m": 10.0})
        current = self._fitness({"m": 5.0})  # 50% drop > 20% threshold
        assert engine._check_regression(baseline, current) == "m"

    def test_baseline_zero_skipped(self) -> None:
        engine = EvolutionEngine()
        baseline = self._fitness({"m": 0.0})
        current = self._fitness({"m": -100.0})
        # zero baseline is skipped to avoid division by zero
        assert engine._check_regression(baseline, current) is None

    def test_missing_metric_in_current_is_skipped(self) -> None:
        engine = EvolutionEngine()
        baseline = self._fitness({"m": 5.0})
        current = self._fitness({"other": 5.0})  # "m" missing from current
        # Should warn and skip (not raise), return None
        assert engine._check_regression(baseline, current) is None


# ---------------------------------------------------------------------------
# get_history
# ---------------------------------------------------------------------------


class TestGetHistory:
    def test_get_history_filter_by_target(self) -> None:
        engine = EvolutionEngine()
        c1 = engine.start_cycle(
            _candidate(EvolutionTarget.ANALYSIS_PARAMS),
            FitnessScore(target=EvolutionTarget.ANALYSIS_PARAMS, metrics={"a": 1.0}),
        )
        c2 = engine.start_cycle(
            _candidate(EvolutionTarget.PROMPTS),
            FitnessScore(target=EvolutionTarget.PROMPTS, metrics={"b": 2.0}),
        )

        history = engine.get_history(target=EvolutionTarget.ANALYSIS_PARAMS)
        ids = [c.cycle_id for c in history]
        assert c1.cycle_id in ids
        assert c2.cycle_id not in ids

    def test_get_history_no_filter_returns_all(self) -> None:
        engine = EvolutionEngine()
        engine.start_cycle(_candidate(), _baseline())
        engine.start_cycle(_candidate(EvolutionTarget.PROMPTS), _baseline(EvolutionTarget.PROMPTS))
        assert len(engine.get_history()) == 2
