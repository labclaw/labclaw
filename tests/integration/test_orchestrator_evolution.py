"""Integration tests for orchestrator -> evolution flow (daemon's core pipeline)."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from labclaw.api.deps import reset_all, set_data_dir, set_memory_root
from labclaw.core.events import event_registry
from labclaw.core.schemas import EvolutionStage, EvolutionTarget
from labclaw.daemon import DataAccumulator
from labclaw.discovery.mining import MiningConfig, PatternMiner
from labclaw.evolution.engine import EvolutionEngine
from labclaw.orchestrator.loop import ScientificLoop


@pytest.fixture()
def sample_data(tmp_path: Path) -> tuple[Path, list[dict]]:
    """Create a sample CSV and return (csv_path, rows)."""
    csv_path = tmp_path / "data" / "sample.csv"
    csv_path.parent.mkdir()
    rows = []
    for i in range(30):
        rows.append(
            {
                "session_id": f"s{i:03d}",
                "trial": i,
                "reaction_time": 0.3 + (i % 5) * 0.05,
                "accuracy": 0.8 + (i % 3) * 0.05,
                "score": 10.0 + i * 0.5,
            }
        )
    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    return csv_path, rows


@pytest.fixture(autouse=True)
def _isolated_singletons(tmp_path: Path) -> None:
    """Reset global singletons before/after each test."""
    reset_all()
    set_data_dir(tmp_path / "data")
    set_memory_root(tmp_path / "memory")
    yield  # type: ignore[misc]
    reset_all()


class TestOrchestratorEvolutionFlow:
    @pytest.mark.asyncio
    async def test_scientific_loop_completes(self, sample_data: tuple[Path, list[dict]]) -> None:
        _, rows = sample_data
        loop = ScientificLoop()
        result = await loop.run_cycle(rows)

        assert result.success is True
        assert result.total_duration > 0
        assert result.patterns_found >= 0
        assert result.hypotheses_generated >= 0

    @pytest.mark.asyncio
    async def test_full_pipeline_orchestrator_to_evolution(
        self, sample_data: tuple[Path, list[dict]]
    ) -> None:
        csv_path, rows = sample_data

        # 1. Ingest data
        accumulator = DataAccumulator()
        n = accumulator.ingest_file(csv_path)
        assert n == 30

        ingested = accumulator.get_all_rows()
        assert len(ingested) == 30

        # 2. Run scientific loop
        loop = ScientificLoop()
        cycle_result = await loop.run_cycle(ingested)
        assert cycle_result.success is True

        # 3. Mine patterns
        miner = PatternMiner()
        config = MiningConfig(min_sessions=3)
        mining_result = miner.mine(ingested, config)

        # 4. Measure fitness
        engine = EvolutionEngine()
        target = EvolutionTarget.ANALYSIS_PARAMS
        numeric_cols = [k for k, v in ingested[0].items() if isinstance(v, (int, float))]
        metrics = {
            "pattern_count": float(len(mining_result.patterns)),
            "data_rows": float(len(ingested)),
            "coverage": float(len(mining_result.patterns)) / max(len(numeric_cols), 1),
        }
        baseline = engine.measure_fitness(target=target, metrics=metrics, data_points=len(ingested))

        # 5. Propose candidates
        candidates = engine.propose_candidates(target, n=1)
        assert len(candidates) >= 1

        # 6. Start evolution cycle
        cycle = engine.start_cycle(candidates[0], baseline)
        assert cycle.stage == EvolutionStage.BACKTEST

        # 7. Advance through stages
        new_fitness = engine.measure_fitness(
            target=target,
            metrics={
                "pattern_count": metrics["pattern_count"] + 1,
                **{k: v for k, v in metrics.items() if k != "pattern_count"},
            },
            data_points=len(ingested),
        )

        engine.advance_stage(cycle.cycle_id, new_fitness)
        assert engine.get_cycle(cycle.cycle_id).stage == EvolutionStage.SHADOW

        engine.advance_stage(cycle.cycle_id, new_fitness)
        assert engine.get_cycle(cycle.cycle_id).stage == EvolutionStage.CANARY

        engine.advance_stage(cycle.cycle_id, new_fitness)
        final = engine.get_cycle(cycle.cycle_id)
        assert final.stage == EvolutionStage.PROMOTED
        assert final.promoted is True

    def test_event_emissions(self, sample_data: tuple[Path, list[dict]]) -> None:
        """Verify that events are emitted during the pipeline."""
        _, rows = sample_data
        captured: list[str] = []

        def _capture(event: object) -> None:
            name = getattr(event, "event_name", None)
            if name:
                captured.append(str(name))

        event_registry.subscribe("evolution.cycle.started", _capture)
        event_registry.subscribe("evolution.fitness.measured", _capture)
        event_registry.subscribe("evolution.cycle.advanced", _capture)

        engine = EvolutionEngine()
        target = EvolutionTarget.ANALYSIS_PARAMS
        baseline = engine.measure_fitness(target, {"pattern_count": 5.0}, data_points=30)
        candidates = engine.propose_candidates(target, n=1)
        cycle = engine.start_cycle(candidates[0], baseline)
        new_fitness = engine.measure_fitness(target, {"pattern_count": 6.0}, data_points=30)
        engine.advance_stage(cycle.cycle_id, new_fitness)

        assert len(captured) >= 3  # At least: fitness, started, fitness, advanced
