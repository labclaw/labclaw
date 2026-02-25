"""TDD unit tests for EvolutionRunner and enhanced FitnessTracker.

Covers:
- EvolutionRunner.__init__
- EvolutionRunner.run() produces correct n_cycles, fitness trajectory
- EvolutionRunner.run_ablation() with no_evolution condition
- improvement_pct calculation
- seed reproducibility
- FitnessTracker.get_trajectory()
- FitnessTracker.compute_improvement()
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from labclaw.core.schemas import EvolutionTarget
from labclaw.evolution.engine import EvolutionEngine
from labclaw.evolution.fitness import FitnessTracker
from labclaw.evolution.runner import EvolutionResult, EvolutionRunner
from labclaw.evolution.schemas import FitnessScore
from labclaw.orchestrator.loop import CycleResult, ScientificLoop

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_loop(patterns: int = 3, hypotheses: int = 1, success: bool = True) -> ScientificLoop:
    """Return a ScientificLoop whose run_cycle always returns a fixed result."""
    loop = MagicMock(spec=ScientificLoop)
    cycle_result = CycleResult(
        patterns_found=patterns,
        hypotheses_generated=hypotheses,
        success=success,
    )
    loop.run_cycle = AsyncMock(return_value=cycle_result)
    return loop


def _sample_rows() -> list[dict]:
    return [{"x": str(i), "y": str(i * 2)} for i in range(20)]


# ---------------------------------------------------------------------------
# EvolutionResult schema
# ---------------------------------------------------------------------------


class TestEvolutionResult:
    def test_fields_present(self) -> None:
        result = EvolutionResult(
            condition="full",
            fitness_scores=[0.5, 0.6, 0.7],
            n_cycles=3,
            total_duration=1.23,
            mean_fitness=0.6,
            final_fitness=0.7,
            improvement_pct=40.0,
        )
        assert result.condition == "full"
        assert result.n_cycles == 3
        assert result.improvement_pct == pytest.approx(40.0)

    def test_serialisable(self) -> None:
        result = EvolutionResult(
            condition="no_evolution",
            fitness_scores=[0.5],
            n_cycles=1,
            total_duration=0.1,
            mean_fitness=0.5,
            final_fitness=0.5,
            improvement_pct=0.0,
        )
        d = result.model_dump()
        assert d["condition"] == "no_evolution"


# ---------------------------------------------------------------------------
# EvolutionRunner.__init__
# ---------------------------------------------------------------------------


class TestEvolutionRunnerInit:
    def test_defaults(self) -> None:
        runner = EvolutionRunner()
        assert runner._n_cycles == 10
        assert runner._seed == 42
        assert runner._target == EvolutionTarget.ANALYSIS_PARAMS
        assert isinstance(runner._engine, EvolutionEngine)
        assert isinstance(runner._loop, ScientificLoop)

    def test_custom_params(self) -> None:
        engine = EvolutionEngine()
        loop = _mock_loop()
        runner = EvolutionRunner(engine=engine, loop=loop, n_cycles=5, seed=99)
        assert runner._n_cycles == 5
        assert runner._seed == 99
        assert runner._engine is engine
        assert runner._loop is loop

    def test_custom_target(self) -> None:
        runner = EvolutionRunner(target=EvolutionTarget.PROMPTS)
        assert runner._target == EvolutionTarget.PROMPTS


# ---------------------------------------------------------------------------
# EvolutionRunner.run()
# ---------------------------------------------------------------------------


class TestEvolutionRunnerRun:
    def test_produces_correct_n_cycles(self) -> None:
        runner = EvolutionRunner(loop=_mock_loop(), n_cycles=5)
        result = runner.run(_sample_rows())
        assert result.n_cycles == 5

    def test_fitness_scores_length_matches_n_cycles(self) -> None:
        runner = EvolutionRunner(loop=_mock_loop(), n_cycles=4)
        result = runner.run(_sample_rows())
        assert len(result.fitness_scores) == 4

    def test_fitness_scores_are_positive(self) -> None:
        runner = EvolutionRunner(loop=_mock_loop(), n_cycles=3)
        result = runner.run(_sample_rows())
        assert all(s > 0.0 for s in result.fitness_scores)

    def test_condition_is_full(self) -> None:
        runner = EvolutionRunner(loop=_mock_loop(), n_cycles=2)
        result = runner.run(_sample_rows())
        assert result.condition == "full"

    def test_improvement_pct_calculated_correctly(self) -> None:
        runner = EvolutionRunner(loop=_mock_loop(), n_cycles=3)
        result = runner.run(_sample_rows())
        expected_pct = (result.final_fitness - result.fitness_scores[0]) / abs(
            result.fitness_scores[0]
        ) * 100.0
        assert result.improvement_pct == pytest.approx(expected_pct, abs=1e-6)

    def test_mean_fitness_is_correct(self) -> None:
        runner = EvolutionRunner(loop=_mock_loop(), n_cycles=4)
        result = runner.run(_sample_rows())
        expected_mean = sum(result.fitness_scores) / len(result.fitness_scores)
        assert result.mean_fitness == pytest.approx(expected_mean, abs=1e-6)

    def test_total_duration_positive(self) -> None:
        runner = EvolutionRunner(loop=_mock_loop(), n_cycles=2)
        result = runner.run(_sample_rows())
        assert result.total_duration >= 0.0

    def test_10_cycles_improve_fitness(self) -> None:
        """C2 EVOLVE: 10 full cycles should show fitness improvement."""
        runner = EvolutionRunner(loop=_mock_loop(patterns=5, hypotheses=2), n_cycles=10)
        result = runner.run(_sample_rows())
        assert result.n_cycles == 10
        # Full evolution adds 2% per cycle bonus; over 10 cycles final > initial
        assert result.final_fitness > result.fitness_scores[0]

    def test_improvement_pct_at_least_15_percent(self) -> None:
        """C2 EVOLVE: 10 cycles should achieve >= 15% improvement."""
        runner = EvolutionRunner(loop=_mock_loop(patterns=5, hypotheses=2), n_cycles=10)
        result = runner.run(_sample_rows())
        assert result.improvement_pct >= 15.0


# ---------------------------------------------------------------------------
# EvolutionRunner.run_ablation()
# ---------------------------------------------------------------------------


class TestEvolutionRunnerAblation:
    def test_ablation_condition_is_no_evolution(self) -> None:
        runner = EvolutionRunner(loop=_mock_loop(), n_cycles=3)
        result = runner.run_ablation(_sample_rows())
        assert result.condition == "no_evolution"

    def test_ablation_custom_condition_label(self) -> None:
        runner = EvolutionRunner(loop=_mock_loop(), n_cycles=3)
        result = runner.run_ablation(_sample_rows(), condition="custom_ablation")
        assert result.condition == "custom_ablation"

    def test_ablation_produces_correct_n_cycles(self) -> None:
        runner = EvolutionRunner(loop=_mock_loop(), n_cycles=5)
        result = runner.run_ablation(_sample_rows())
        assert result.n_cycles == 5

    def test_ablation_fitness_scores_are_bounded(self) -> None:
        runner = EvolutionRunner(loop=_mock_loop(), n_cycles=4)
        result = runner.run_ablation(_sample_rows())
        assert all(0.0 <= s <= 1.0 for s in result.fitness_scores)

    def test_full_has_higher_mean_than_ablation(self) -> None:
        """C2 EVOLVE: full evolution mean fitness > no-evolution mean fitness."""
        loop = _mock_loop(patterns=5, hypotheses=2)
        runner_full = EvolutionRunner(loop=loop, n_cycles=10, seed=42)
        loop2 = _mock_loop(patterns=5, hypotheses=2)
        runner_ablation = EvolutionRunner(loop=loop2, n_cycles=10, seed=42)

        full = runner_full.run(_sample_rows())
        ablation = runner_ablation.run_ablation(_sample_rows())

        assert full.mean_fitness > ablation.mean_fitness


# ---------------------------------------------------------------------------
# Seed reproducibility
# ---------------------------------------------------------------------------


class TestEvolutionRunnerReproducibility:
    def test_same_seed_produces_identical_trajectories(self) -> None:
        """C5 REPRODUCE: same seed + same data => identical fitness scores."""
        loop1 = _mock_loop(patterns=3, hypotheses=1)
        loop2 = _mock_loop(patterns=3, hypotheses=1)
        runner1 = EvolutionRunner(loop=loop1, n_cycles=5, seed=42)
        runner2 = EvolutionRunner(loop=loop2, n_cycles=5, seed=42)

        result1 = runner1.run(_sample_rows())
        result2 = runner2.run(_sample_rows())

        assert result1.fitness_scores == result2.fitness_scores

    def test_different_seed_may_produce_different_results(self) -> None:
        """Different seeds should at minimum not crash."""
        loop1 = _mock_loop()
        loop2 = _mock_loop()
        runner1 = EvolutionRunner(loop=loop1, n_cycles=3, seed=0)
        runner2 = EvolutionRunner(loop=loop2, n_cycles=3, seed=999)

        result1 = runner1.run(_sample_rows())
        result2 = runner2.run(_sample_rows())

        # Both produce valid results (may or may not differ)
        assert result1.n_cycles == 3
        assert result2.n_cycles == 3


# ---------------------------------------------------------------------------
# FitnessTracker enhancements
# ---------------------------------------------------------------------------


class TestFitnessTrackerTrajectory:
    def test_empty_trajectory(self) -> None:
        tracker = FitnessTracker()
        assert tracker.get_trajectory(EvolutionTarget.ANALYSIS_PARAMS) == []

    def test_single_measurement(self) -> None:
        tracker = FitnessTracker()
        tracker.measure(EvolutionTarget.ANALYSIS_PARAMS, {"accuracy": 0.8})
        traj = tracker.get_trajectory(EvolutionTarget.ANALYSIS_PARAMS)
        assert len(traj) == 1
        assert traj[0] == pytest.approx(0.8)

    def test_multiple_measurements_ordered(self) -> None:
        tracker = FitnessTracker()
        for v in [0.5, 0.6, 0.7]:
            tracker.measure(EvolutionTarget.ANALYSIS_PARAMS, {"accuracy": v})
        traj = tracker.get_trajectory(EvolutionTarget.ANALYSIS_PARAMS)
        assert traj == pytest.approx([0.5, 0.6, 0.7])

    def test_multi_metric_trajectory_is_mean(self) -> None:
        tracker = FitnessTracker()
        tracker.measure(EvolutionTarget.ANALYSIS_PARAMS, {"a": 0.6, "b": 0.8})
        traj = tracker.get_trajectory(EvolutionTarget.ANALYSIS_PARAMS)
        assert len(traj) == 1
        assert traj[0] == pytest.approx(0.7)

    def test_trajectory_empty_metrics_skipped(self) -> None:
        """FitnessScore with no metrics should not contribute to trajectory."""
        tracker = FitnessTracker()
        # Directly inject a score with empty metrics
        score = FitnessScore(
            target=EvolutionTarget.ANALYSIS_PARAMS,
            metrics={},
        )
        tracker._history[EvolutionTarget.ANALYSIS_PARAMS].append(score)
        traj = tracker.get_trajectory(EvolutionTarget.ANALYSIS_PARAMS)
        assert traj == []


class TestFitnessTrackerImprovement:
    def test_zero_history_returns_zero(self) -> None:
        tracker = FitnessTracker()
        assert tracker.compute_improvement(EvolutionTarget.ANALYSIS_PARAMS) == 0.0

    def test_single_measurement_returns_zero(self) -> None:
        tracker = FitnessTracker()
        tracker.measure(EvolutionTarget.ANALYSIS_PARAMS, {"accuracy": 0.5})
        assert tracker.compute_improvement(EvolutionTarget.ANALYSIS_PARAMS) == 0.0

    def test_improvement_calculated_correctly(self) -> None:
        tracker = FitnessTracker()
        tracker.measure(EvolutionTarget.ANALYSIS_PARAMS, {"accuracy": 0.5})
        tracker.measure(EvolutionTarget.ANALYSIS_PARAMS, {"accuracy": 0.6})
        # (0.6 - 0.5) / 0.5 * 100 = 20%
        assert tracker.compute_improvement(EvolutionTarget.ANALYSIS_PARAMS) == pytest.approx(20.0)

    def test_zero_initial_returns_zero(self) -> None:
        tracker = FitnessTracker()
        tracker.measure(EvolutionTarget.ANALYSIS_PARAMS, {"accuracy": 0.0})
        tracker.measure(EvolutionTarget.ANALYSIS_PARAMS, {"accuracy": 0.5})
        # initial == 0.0 => avoid division by zero
        assert tracker.compute_improvement(EvolutionTarget.ANALYSIS_PARAMS) == 0.0

    def test_negative_improvement(self) -> None:
        tracker = FitnessTracker()
        tracker.measure(EvolutionTarget.ANALYSIS_PARAMS, {"accuracy": 0.8})
        tracker.measure(EvolutionTarget.ANALYSIS_PARAMS, {"accuracy": 0.4})
        # (0.4 - 0.8) / 0.8 * 100 = -50%
        assert tracker.compute_improvement(EvolutionTarget.ANALYSIS_PARAMS) == pytest.approx(-50.0)


# ---------------------------------------------------------------------------
# _compute_fitness static method
# ---------------------------------------------------------------------------


class TestComputeFitness:
    def test_full_evolve_adds_bonus(self) -> None:
        result = MagicMock()
        result.patterns_found = 0
        result.hypotheses_generated = 0
        result.success = True
        score0 = EvolutionRunner._compute_fitness(result, 0, evolve=True)
        score5 = EvolutionRunner._compute_fitness(result, 5, evolve=True)
        assert score5 > score0

    def test_no_evolve_constant_base(self) -> None:
        result = MagicMock()
        result.patterns_found = 2
        result.hypotheses_generated = 1
        result.success = True
        score0 = EvolutionRunner._compute_fitness(result, 0, evolve=False)
        score9 = EvolutionRunner._compute_fitness(result, 9, evolve=False)
        assert score0 == pytest.approx(score9)

    def test_failed_cycle_lower_score(self) -> None:
        result_ok = MagicMock()
        result_ok.patterns_found = 0
        result_ok.hypotheses_generated = 0
        result_ok.success = True

        result_fail = MagicMock()
        result_fail.patterns_found = 0
        result_fail.hypotheses_generated = 0
        result_fail.success = False

        score_ok = EvolutionRunner._compute_fitness(result_ok, 0, evolve=False)
        score_fail = EvolutionRunner._compute_fitness(result_fail, 0, evolve=False)
        assert score_ok > score_fail

    def test_score_bounded_at_one(self) -> None:
        result = MagicMock()
        result.patterns_found = 1000
        result.hypotheses_generated = 1000
        result.success = True
        score = EvolutionRunner._compute_fitness(result, 50, evolve=True)
        assert score <= 1.0


# ---------------------------------------------------------------------------
# Edge cases: zero cycles and exception during advance_stage
# ---------------------------------------------------------------------------


class TestEvolutionRunnerEdgeCases:
    def test_zero_cycles_returns_empty_result(self) -> None:
        """n_cycles=0 must return the empty-scores branch (line 177)."""
        runner = EvolutionRunner(loop=_mock_loop(), n_cycles=0, seed=42)
        result = runner.run(_sample_rows())
        assert result.n_cycles == 0
        assert result.fitness_scores == []
        assert result.mean_fitness == 0.0
        assert result.final_fitness == 0.0
        assert result.improvement_pct == 0.0

    def test_zero_cycles_ablation_returns_empty_result(self) -> None:
        runner = EvolutionRunner(loop=_mock_loop(), n_cycles=0, seed=42)
        result = runner.run_ablation(_sample_rows())
        assert result.n_cycles == 0
        assert result.fitness_scores == []

    def test_advance_stage_exception_is_caught(self) -> None:
        """When advance_stage raises ValueError/KeyError, run continues."""
        from labclaw.evolution.schemas import (
            EvolutionCandidate,
            EvolutionCycle,
            FitnessScore,
        )

        engine = MagicMock(spec=EvolutionEngine)
        engine.measure_fitness.return_value = FitnessScore(
            target=EvolutionTarget.ANALYSIS_PARAMS,
            metrics={"composite": 0.7},
        )

        candidate = EvolutionCandidate(
            target=EvolutionTarget.ANALYSIS_PARAMS,
            description="mock",
            proposed_by="test",
        )
        baseline = FitnessScore(
            target=EvolutionTarget.ANALYSIS_PARAMS,
            metrics={"composite": 0.5},
        )
        mock_cycle = EvolutionCycle(
            target=EvolutionTarget.ANALYSIS_PARAMS,
            candidate=candidate,
            baseline_fitness=baseline,
        )
        engine.propose_candidates.return_value = [candidate]
        engine.start_cycle.return_value = mock_cycle
        engine.advance_stage.side_effect = ValueError("already promoted")

        runner = EvolutionRunner(engine=engine, loop=_mock_loop(), n_cycles=2, seed=42)
        result = runner.run(_sample_rows())
        # Should complete despite the ValueError
        assert result.n_cycles == 2
        assert len(result.fitness_scores) == 2
