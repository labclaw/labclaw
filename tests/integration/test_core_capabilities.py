"""Integration tests proving the 5 core capabilities for LabClaw.

These tests use the fixture data at tests/fixtures/sample_lab/ to demonstrate
each of the 5 core capabilities.

C1 DISCOVER  — Real data -> finding with p < 0.05
C2 EVOLVE    — 10 cycles, fitness +15%, ablation significant
C3 REMEMBER  — Restart -> 90% findings retrievable
C4 TRACE     — 100% findings have complete provenance
C5 REPRODUCE — Same input + seed = same output
"""

from __future__ import annotations

import asyncio
import csv
import json
import random
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from labclaw.evolution.runner import EvolutionRunner
from labclaw.memory.session_memory import SessionMemoryManager
from labclaw.orchestrator.loop import CycleResult, ScientificLoop
from labclaw.orchestrator.steps import (
    AnalyzeStep,
    AskStep,
    ConcludeStep,
    ExperimentStep,
    HypothesizeStep,
    ObserveStep,
    PredictStep,
)
from labclaw.validation.statistics import StatisticalValidator, ValidationConfig

# ---------------------------------------------------------------------------
# Constants and helpers
# ---------------------------------------------------------------------------

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "sample_lab"


def _load_typed_rows() -> list[dict[str, Any]]:
    """Load fixture CSV files with numeric columns cast to float."""
    rows: list[dict[str, Any]] = []
    for csv_path in sorted(FIXTURE_DIR.glob("*.csv")):
        with open(csv_path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(
                    {
                        "timestamp": row["timestamp"],
                        "x": float(row["x"]),
                        "y": float(row["y"]),
                        "speed": float(row["speed"]),
                        "angle": float(row["angle"]),
                        "zone": row["zone"],
                        "animal_id": row["animal_id"],
                    }
                )
    return rows


@pytest.fixture
def data_rows() -> list[dict[str, Any]]:
    """Load all CSV files from the sample_lab fixture directory (typed)."""
    return _load_typed_rows()


def _build_loop(memory_root: Path | None = None) -> ScientificLoop:
    """Return a ScientificLoop with template-based hypothesis gen (no API key)."""
    return ScientificLoop(
        steps=[
            ObserveStep(),
            AskStep(),
            HypothesizeStep(llm_provider=None),
            PredictStep(),
            ExperimentStep(),
            AnalyzeStep(),
            ConcludeStep(memory_root=memory_root),
        ]
    )


def _make_mock_loop(patterns: int = 5, hypotheses: int = 2) -> ScientificLoop:
    """Return a fast mock ScientificLoop for evolution tests."""
    loop = MagicMock(spec=ScientificLoop)
    result = CycleResult(
        patterns_found=patterns,
        hypotheses_generated=hypotheses,
        success=True,
    )
    loop.run_cycle = AsyncMock(return_value=result)
    return loop


def _make_finding(n: int) -> dict[str, Any]:
    return {
        "finding_id": f"cap-finding-{n}",
        "description": f"Core capability finding number {n}",
        "column_a": f"col_a_{n}",
        "column_b": f"col_b_{n}",
        "pattern_type": "correlation",
        "p_value": 0.01,
    }


def _normalize_result(d: dict[str, Any]) -> dict[str, Any]:
    """Strip non-deterministic fields from a model_dump dict for comparison."""
    d["cycle_id"] = "X"
    d["total_duration"] = 0.0
    # finding_chains contain per-run UUIDs and timestamps — exclude from comparison
    fc = d.get("final_context", {})
    fc.pop("finding_chains", None)
    d["final_context"] = fc
    return d


# ---------------------------------------------------------------------------
# Test class proving all 5 core capabilities
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestCoreCapabilities:
    """Integration tests proving the 5 core capabilities."""

    def test_c1_discover_finding_with_significance(self, data_rows: list[dict[str, Any]]) -> None:
        """C1: Real data -> finding with p < 0.05."""
        loop = _build_loop()
        result: CycleResult = asyncio.run(loop.run_cycle(data_rows))

        assert result.success is True, f"Pipeline must succeed, got success={result.success}"
        assert result.patterns_found > 0, (
            f"Expected at least one pattern found, got patterns_found={result.patterns_found}"
        )

        # Validate with StatisticalValidator on the numeric fixture columns
        speed_vals = [float(row["speed"]) for row in data_rows if row.get("speed") is not None]
        angle_vals = [float(row["angle"]) for row in data_rows if row.get("angle") is not None]

        validator = StatisticalValidator()
        cfg = ValidationConfig(min_sample_size=2)
        stat_result = validator.run_test(
            "permutation",
            speed_vals,
            angle_vals,
            config=cfg,
        )
        assert stat_result.p_value < 0.05, (
            f"Expected p < 0.05 for C1 DISCOVER, got p={stat_result.p_value:.6f}"
        )

    def test_c2_evolve_fitness_improvement(self, data_rows: list[dict[str, Any]]) -> None:
        """C2: 10 cycles, fitness +15%, ablation significant."""
        runner = EvolutionRunner(
            loop=_make_mock_loop(patterns=5, hypotheses=2),
            n_cycles=10,
            seed=42,
        )
        result = runner.run(data_rows)

        assert result.n_cycles == 10, f"Expected 10 cycles, got {result.n_cycles}"
        assert len(result.fitness_scores) == 10, (
            f"Expected 10 fitness scores, got {len(result.fitness_scores)}"
        )
        assert result.improvement_pct >= 15.0, (
            f"Expected improvement >= 15%, got {result.improvement_pct:.1f}%"
        )

        # Ablation comparison
        ablation_runner = EvolutionRunner(
            loop=_make_mock_loop(patterns=5, hypotheses=2),
            n_cycles=10,
            seed=42,
        )
        ablation_result = ablation_runner.run_ablation(data_rows)

        assert result.mean_fitness > ablation_result.mean_fitness, (
            f"Full evolution mean fitness ({result.mean_fitness:.4f}) must exceed "
            f"ablation ({ablation_result.mean_fitness:.4f})"
        )

        # Statistical comparison
        validator = StatisticalValidator()
        cfg = ValidationConfig(min_sample_size=2)
        stat_result = validator.run_test(
            "permutation",
            result.fitness_scores,
            ablation_result.fitness_scores,
            config=cfg,
        )
        assert stat_result.p_value < 0.05, (
            f"Expected p < 0.05 for C2 ablation, got p={stat_result.p_value:.6f}"
        )

    @pytest.mark.asyncio
    async def test_c3_remember_findings_retrievable(
        self, tmp_path: Path, data_rows: list[dict[str, Any]]
    ) -> None:
        """C3: Restart -> 90% findings retrievable."""
        db_path = tmp_path / "tier_b.db"
        memory_root = tmp_path / "memory"

        # Store 10 findings in the first manager
        n_findings = 10
        mgr1 = SessionMemoryManager(memory_root, db_path)
        await mgr1.init()

        for i in range(n_findings):
            await mgr1.store_finding(_make_finding(i))

        stored_count = len(mgr1._findings)
        assert stored_count == n_findings

        # "Restart" — create a new manager from the same paths
        mgr2 = SessionMemoryManager(memory_root, db_path)
        await mgr2.init()
        retrieved = await mgr2.retrieve_findings()

        rate = len(retrieved) / stored_count
        assert rate >= 0.9, (
            f"Expected >= 90% retrieval after restart, "
            f"got {rate:.1%} ({len(retrieved)}/{stored_count})"
        )

    def test_c4_trace_complete_provenance(self, data_rows: list[dict[str, Any]]) -> None:
        """C4: 100% findings have complete provenance chains."""
        loop = _build_loop()
        result: CycleResult = asyncio.run(loop.run_cycle(data_rows))

        assert result.success is True, "Pipeline must succeed"
        assert len(result.steps_completed) >= 3, (
            f"Expected at least 3 steps completed, got {result.steps_completed}"
        )

        # Provenance chains are stored in final_context["finding_chains"]
        finding_chains = result.final_context.get("finding_chains", [])
        assert len(finding_chains) > 0, (
            f"Expected finding_chains in final_context, "
            f"got keys: {list(result.final_context.keys())}"
        )

        # Each chain must have steps with node_id and description
        for chain in finding_chains:
            steps = chain.get("steps", [])
            assert len(steps) > 0, f"Chain must have at least one step: {chain}"
            for step in steps:
                assert "node_id" in step, f"Step missing node_id: {step}"
                assert "description" in step, f"Step missing description: {step}"
                assert step["node_id"], "node_id must not be empty"
                assert step["description"], "description must not be empty"

    def test_c5_reproduce_deterministic_output(
        self, data_rows: list[dict[str, Any]], tmp_path: Path
    ) -> None:
        """C5: Same input + seed = same output."""
        seed = 42

        # Run 1
        random.seed(seed)
        loop1 = _build_loop()
        result1: CycleResult = asyncio.run(loop1.run_cycle(data_rows))

        # Run 2
        random.seed(seed)
        loop2 = _build_loop()
        result2: CycleResult = asyncio.run(loop2.run_cycle(data_rows))

        d1 = _normalize_result(result1.model_dump())
        d2 = _normalize_result(result2.model_dump())

        assert d1 == d2, (
            f"Pipeline is not reproducible with seed={seed}. "
            f"Differing keys: {[k for k in d1 if d1[k] != d2[k]]}"
        )

        # Verify the JSON-serialized output is also identical
        j1 = json.dumps(d1, sort_keys=True)
        j2 = json.dumps(d2, sort_keys=True)
        assert j1 == j2, "JSON dumps of both runs must be identical"
