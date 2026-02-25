"""BDD step definitions for Self-Evolution Cycles (C2: EVOLVE).

Spec: docs/specs/L5-evolution.md
Feature: tests/features/layer5_persona/evolution_cycles.feature
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from pytest_bdd import given, parsers, then, when

from labclaw.core.schemas import EvolutionTarget
from labclaw.evolution.engine import EvolutionEngine
from labclaw.evolution.runner import EvolutionResult, EvolutionRunner
from labclaw.orchestrator.loop import CycleResult, ScientificLoop

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_loop(patterns: int = 5, hypotheses: int = 2) -> ScientificLoop:
    """Return a mock ScientificLoop for deterministic fast tests."""
    loop = MagicMock(spec=ScientificLoop)
    result = CycleResult(
        patterns_found=patterns,
        hypotheses_generated=hypotheses,
        success=True,
    )
    loop.run_cycle = AsyncMock(return_value=result)
    return loop


def _sample_rows() -> list[dict]:
    return [{"x": str(i), "y": str(i * 2)} for i in range(20)]


# ---------------------------------------------------------------------------
# Background
# ---------------------------------------------------------------------------


@given("an evolution runner is available", target_fixture="runner_available")
def evolution_runner_available() -> bool:
    """Confirm the EvolutionRunner class is importable."""
    return True


# ---------------------------------------------------------------------------
# Given steps
# ---------------------------------------------------------------------------


@given(
    parsers.parse("an evolution runner configured for {n:d} cycles"),
    target_fixture="runner",
)
def runner_for_n_cycles(n: int) -> EvolutionRunner:
    """Create an EvolutionRunner with mock loop for n cycles."""
    return EvolutionRunner(loop=_mock_loop(), n_cycles=n, seed=42)


@given(
    parsers.parse("an evolution runner configured for {n:d} cycles with shared engine"),
    target_fixture="runner_with_engine",
)
def runner_for_n_cycles_with_engine(n: int) -> tuple[EvolutionRunner, EvolutionEngine]:
    """Create an EvolutionRunner that shares its engine for inspection."""
    engine = EvolutionEngine()
    runner = EvolutionRunner(engine=engine, loop=_mock_loop(), n_cycles=n, seed=42)
    return runner, engine


@given(parsers.parse("an evolution runner with seed {seed:d}"), target_fixture="seeded_runner")
def runner_with_seed(seed: int) -> EvolutionRunner:
    """Create an EvolutionRunner with a specific seed."""
    return EvolutionRunner(loop=_mock_loop(), n_cycles=5, seed=seed)


# ---------------------------------------------------------------------------
# When steps
# ---------------------------------------------------------------------------


@when("I run evolution on behavioral data", target_fixture="evolution_result")
def run_evolution(runner: EvolutionRunner) -> EvolutionResult:
    """Run full evolution and capture result."""
    return runner.run(_sample_rows())


@when("I run full evolution and no-evolution ablation", target_fixture="both_results")
def run_full_and_ablation(runner: EvolutionRunner) -> tuple[EvolutionResult, EvolutionResult]:
    """Run both full and ablation conditions."""
    full = runner.run(_sample_rows())
    # Use a fresh runner for ablation (same config)
    ablation_runner = EvolutionRunner(
        loop=_mock_loop(), n_cycles=runner._n_cycles, seed=runner._seed
    )
    ablation = ablation_runner.run_ablation(_sample_rows())
    return full, ablation


@when("I run evolution twice on the same data", target_fixture="two_results")
def run_evolution_twice(seeded_runner: EvolutionRunner) -> tuple[EvolutionResult, EvolutionResult]:
    """Run evolution twice with the same seed."""
    result1 = seeded_runner.run(_sample_rows())
    # Re-create runner with same seed for second run
    runner2 = EvolutionRunner(
        loop=_mock_loop(), n_cycles=seeded_runner._n_cycles, seed=seeded_runner._seed
    )
    result2 = runner2.run(_sample_rows())
    return result1, result2


@when("I run the no-evolution ablation", target_fixture="ablation_result")
def run_ablation(runner: EvolutionRunner) -> EvolutionResult:
    """Run no-evolution ablation and capture result."""
    return runner.run_ablation(_sample_rows())


@when(
    "I run evolution with the shared engine",
    target_fixture="evolution_result",
)
def run_evolution_with_engine(
    runner_with_engine: tuple[EvolutionRunner, EvolutionEngine],
) -> EvolutionResult:
    """Run evolution using the shared-engine fixture."""
    runner, _ = runner_with_engine
    return runner.run(_sample_rows())


# ---------------------------------------------------------------------------
# Then steps
# ---------------------------------------------------------------------------


@then(parsers.parse("{n:d} cycles are completed"))
def check_cycles_completed(evolution_result: EvolutionResult, n: int) -> None:
    assert evolution_result.n_cycles == n, f"Expected {n} cycles, got {evolution_result.n_cycles}"


@then("fitness scores are recorded for each cycle")
def check_fitness_scores_recorded(evolution_result: EvolutionResult) -> None:
    assert len(evolution_result.fitness_scores) == evolution_result.n_cycles, (
        f"Expected {evolution_result.n_cycles} scores, got {len(evolution_result.fitness_scores)}"
    )
    assert all(s > 0.0 for s in evolution_result.fitness_scores), (
        "All fitness scores should be positive"
    )


@then("the final fitness is higher than the initial fitness")
def check_final_higher_than_initial(evolution_result: EvolutionResult) -> None:
    assert evolution_result.final_fitness > evolution_result.fitness_scores[0], (
        f"Final fitness {evolution_result.final_fitness} not > "
        f"initial {evolution_result.fitness_scores[0]}"
    )


@then("the full condition has higher mean fitness")
def check_full_higher_mean(both_results: tuple[EvolutionResult, EvolutionResult]) -> None:
    full, ablation = both_results
    assert full.mean_fitness > ablation.mean_fitness, (
        f"Full mean {full.mean_fitness:.4f} <= ablation mean {ablation.mean_fitness:.4f}"
    )


@then("both runs produce identical fitness trajectories")
def check_identical_trajectories(two_results: tuple[EvolutionResult, EvolutionResult]) -> None:
    result1, result2 = two_results
    assert result1.fitness_scores == result2.fitness_scores, (
        f"Trajectories differ: {result1.fitness_scores} vs {result2.fitness_scores}"
    )


@then(parsers.parse('the result has a condition field set to "{expected_condition}"'))
def check_result_condition(evolution_result: EvolutionResult, expected_condition: str) -> None:
    assert evolution_result.condition == expected_condition, (
        f"Expected condition {expected_condition!r}, got {evolution_result.condition!r}"
    )


@then("the result has a non-empty fitness_scores list")
def check_result_has_scores(evolution_result: EvolutionResult) -> None:
    assert len(evolution_result.fitness_scores) > 0, "fitness_scores should not be empty"


@then("the result has a positive mean_fitness")
def check_result_has_positive_mean(evolution_result: EvolutionResult) -> None:
    assert evolution_result.mean_fitness > 0.0, (
        f"mean_fitness should be positive, got {evolution_result.mean_fitness}"
    )


@then(parsers.parse('the ablation result condition is "{expected}"'))
def check_ablation_condition(ablation_result: EvolutionResult, expected: str) -> None:
    assert ablation_result.condition == expected, (
        f"Expected {expected!r}, got {ablation_result.condition!r}"
    )


@then(parsers.parse("the improvement percentage is at least {threshold:d} percent"))
def check_improvement_threshold(evolution_result: EvolutionResult, threshold: int) -> None:
    assert evolution_result.improvement_pct >= float(threshold), (
        f"Improvement {evolution_result.improvement_pct:.1f}% < threshold {threshold}%"
    )


@then(parsers.parse("the engine tracker has {n:d} fitness entries for {target_name}"))
def check_engine_tracker_entries(
    runner_with_engine: tuple[EvolutionRunner, EvolutionEngine],
    n: int,
    target_name: str,
) -> None:
    _, engine = runner_with_engine
    target = EvolutionTarget(target_name)
    history = engine.fitness_tracker.get_history(target)
    assert len(history) == n, (
        f"Expected {n} fitness entries for {target_name!r}, got {len(history)}"
    )
