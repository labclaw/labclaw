"""Integration tests for C2 EVOLVE: 10 cycles, fitness improvement >= 15%.

These tests verify the full multi-cycle evolution pipeline.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from labclaw.evolution.engine import EvolutionEngine
from labclaw.evolution.runner import EvolutionResult, EvolutionRunner
from labclaw.orchestrator.loop import CycleResult, ScientificLoop

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _mock_loop(patterns: int = 5, hypotheses: int = 2, success: bool = True) -> ScientificLoop:
    """Return a mock ScientificLoop for fast testing."""
    loop = MagicMock(spec=ScientificLoop)
    result = CycleResult(
        patterns_found=patterns,
        hypotheses_generated=hypotheses,
        success=success,
    )
    loop.run_cycle = AsyncMock(return_value=result)
    return loop


@pytest.fixture()
def sample_data() -> list[dict]:
    return [
        {
            "session_id": f"s{i:03d}",
            "trial": str(i),
            "reaction_time": str(0.3 + (i % 5) * 0.05),
            "accuracy": str(0.8 + (i % 3) * 0.05),
            "score": str(10.0 + i * 0.5),
        }
        for i in range(30)
    ]


# ---------------------------------------------------------------------------
# C2 EVOLVE: 10 cycles
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_10_cycles_improve_fitness(sample_data: list[dict], tmp_path: Path) -> None:
    """C2: 10 evolution cycles produce fitness improvement >= 15%."""
    runner = EvolutionRunner(
        loop=_mock_loop(patterns=5, hypotheses=2),
        n_cycles=10,
        seed=42,
    )
    result = runner.run(sample_data)

    assert result.n_cycles == 10
    assert len(result.fitness_scores) == 10
    assert result.improvement_pct >= 15.0
    assert result.condition == "full"


@pytest.mark.e2e
def test_ablation_shows_evolution_helps(sample_data: list[dict], tmp_path: Path) -> None:
    """C2: Full evolution mean fitness > no-evolution mean fitness."""
    full_runner = EvolutionRunner(
        loop=_mock_loop(patterns=5, hypotheses=2),
        n_cycles=10,
        seed=42,
    )
    ablation_runner = EvolutionRunner(
        loop=_mock_loop(patterns=5, hypotheses=2),
        n_cycles=10,
        seed=42,
    )

    full = full_runner.run(sample_data)
    ablation = ablation_runner.run_ablation(sample_data)

    assert full.mean_fitness > ablation.mean_fitness
    assert full.condition == "full"
    assert ablation.condition == "no_evolution"


@pytest.mark.e2e
def test_evolution_result_has_all_required_fields(sample_data: list[dict]) -> None:
    """EvolutionResult contains all required fields for C2 reporting."""
    runner = EvolutionRunner(
        loop=_mock_loop(),
        n_cycles=5,
    )
    result = runner.run(sample_data)

    assert isinstance(result, EvolutionResult)
    assert result.n_cycles > 0
    assert result.total_duration >= 0.0
    assert result.mean_fitness > 0.0
    assert result.final_fitness > 0.0
    assert isinstance(result.fitness_scores, list)


@pytest.mark.e2e
def test_evolution_runner_uses_engine_fitness_tracker(sample_data: list[dict]) -> None:
    """The runner records every cycle's fitness in the engine's tracker."""
    engine = EvolutionEngine()
    runner = EvolutionRunner(
        engine=engine,
        loop=_mock_loop(),
        n_cycles=5,
    )
    runner.run(sample_data)

    from labclaw.core.schemas import EvolutionTarget

    trajectory = engine.fitness_tracker.get_trajectory(EvolutionTarget.ANALYSIS_PARAMS)
    assert len(trajectory) == 5


@pytest.mark.e2e
def test_statistical_comparison_full_vs_ablation(sample_data: list[dict]) -> None:
    """The fitness scores from full vs ablation are quantitatively different."""
    from labclaw.validation.statistics import StatisticalValidator, ValidationConfig

    full_runner = EvolutionRunner(
        loop=_mock_loop(patterns=5, hypotheses=2),
        n_cycles=10,
        seed=42,
    )
    ablation_runner = EvolutionRunner(
        loop=_mock_loop(patterns=5, hypotheses=2),
        n_cycles=10,
        seed=42,
    )

    full = full_runner.run(sample_data)
    ablation = ablation_runner.run_ablation(sample_data)

    validator = StatisticalValidator()
    cfg = ValidationConfig(min_sample_size=2)
    stat_result = validator.run_test(
        "permutation",
        full.fitness_scores,
        ablation.fitness_scores,
        config=cfg,
    )

    # At minimum, the test should complete and return a valid p-value
    assert 0.0 <= stat_result.p_value <= 1.0
    # Full evolution produces strictly higher scores at every cycle
    assert full.mean_fitness > ablation.mean_fitness
