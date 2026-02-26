"""BDD step definitions for Paper Capabilities (v0.1.0).

Covers scenarios in tests/features/layer3_engine/paper_capabilities.feature.
"""

from __future__ import annotations

import asyncio
import csv
import random
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from pytest_bdd import given, then, when

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
# Constants
# ---------------------------------------------------------------------------

_FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures" / "sample_lab"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_typed_fixture_data() -> list[dict[str, Any]]:
    """Load fixture CSV files with numeric columns cast to float."""
    rows: list[dict[str, Any]] = []
    for csv_path in sorted(_FIXTURES_DIR.glob("*.csv")):
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
        "finding_id": f"bdd-finding-{n}",
        "description": f"BDD capability finding number {n}",
        "column_a": f"col_a_{n}",
        "column_b": f"col_b_{n}",
        "pattern_type": "correlation",
        "p_value": 0.01,
    }


# ---------------------------------------------------------------------------
# Given steps
# ---------------------------------------------------------------------------


@given(
    "behavioral session data with embedded correlations",
    target_fixture="bdd_data_rows",
)
def behavioral_session_data() -> list[dict[str, Any]]:
    """Load behavioral fixture data with numeric columns cast to float."""
    data = _load_typed_fixture_data()
    assert len(data) > 0, "Fixture data must not be empty"
    return data


@given(
    "a session memory manager with temporary storage",
    target_fixture="memory_context",
)
def session_memory_context(tmp_path: Path) -> dict[str, Any]:
    """Provide temporary paths for the session memory manager."""
    return {
        "db_path": tmp_path / "tier_b.db",
        "memory_root": tmp_path / "memory",
        "tmp_path": tmp_path,
    }


# ---------------------------------------------------------------------------
# When steps
# ---------------------------------------------------------------------------


@when("a full scientific loop cycle is executed", target_fixture="bdd_cycle_result")
def run_full_cycle(bdd_data_rows: list[dict[str, Any]]) -> CycleResult:
    """Run one complete scientific method cycle on the fixture data."""
    loop = _build_loop()
    return asyncio.run(loop.run_cycle(bdd_data_rows))


@when(
    "a full scientific loop cycle is executed with provenance tracking",
    target_fixture="bdd_cycle_result",
)
def run_full_cycle_with_provenance(bdd_data_rows: list[dict[str, Any]]) -> CycleResult:
    """Run one cycle and capture provenance chain in the final context."""
    loop = _build_loop()
    return asyncio.run(loop.run_cycle(bdd_data_rows))


@when("10 evolution cycles are executed with seed 42", target_fixture="bdd_evolution_result")
def run_10_evolution_cycles(bdd_data_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Run full and ablation evolution and return both results for comparison."""
    runner = EvolutionRunner(
        loop=_make_mock_loop(patterns=5, hypotheses=2),
        n_cycles=10,
        seed=42,
    )
    full_result = runner.run(bdd_data_rows)

    ablation_runner = EvolutionRunner(
        loop=_make_mock_loop(patterns=5, hypotheses=2),
        n_cycles=10,
        seed=42,
    )
    ablation_result = ablation_runner.run_ablation(bdd_data_rows)

    return {"full": full_result, "ablation": ablation_result}


@when("findings are stored from a discovery cycle", target_fixture="stored_count")
def store_findings_in_memory(
    bdd_data_rows: list[dict[str, Any]],
    memory_context: dict[str, Any],
) -> int:
    """Store 10 findings into the first session memory manager."""
    n_findings = 10

    async def _store() -> int:
        mgr = SessionMemoryManager(
            memory_context["memory_root"],
            memory_context["db_path"],
        )
        await mgr.init()
        for i in range(n_findings):
            await mgr.store_finding(_make_finding(i))
        return len(mgr._findings)

    return asyncio.run(_store())


@when(
    "the memory manager is restarted from the same storage",
    target_fixture="retrieved_findings",
)
def restart_memory_manager(
    memory_context: dict[str, Any],
    stored_count: int,
) -> list[dict[str, Any]]:
    """Create a new manager from the same paths and retrieve findings."""

    async def _retrieve() -> list[dict[str, Any]]:
        mgr2 = SessionMemoryManager(
            memory_context["memory_root"],
            memory_context["db_path"],
        )
        await mgr2.init()
        return await mgr2.retrieve_findings()

    return asyncio.run(_retrieve())


@when("the pipeline is executed twice with seed 42", target_fixture="bdd_two_results")
def run_pipeline_twice(bdd_data_rows: list[dict[str, Any]]) -> tuple[CycleResult, CycleResult]:
    """Run the pipeline twice with the same seed and return both results."""
    seed = 42

    random.seed(seed)
    loop1 = _build_loop()
    result1 = asyncio.run(loop1.run_cycle(bdd_data_rows))

    random.seed(seed)
    loop2 = _build_loop()
    result2 = asyncio.run(loop2.run_cycle(bdd_data_rows))

    return result1, result2


# ---------------------------------------------------------------------------
# Then steps
# ---------------------------------------------------------------------------


@then("at least one pattern is discovered")
def at_least_one_pattern_discovered(bdd_cycle_result: CycleResult) -> None:
    assert bdd_cycle_result.patterns_found > 0, (
        f"Expected patterns_found > 0, got {bdd_cycle_result.patterns_found}"
    )


@then("at least one finding has p-value less than 0.05")
def finding_with_significance(bdd_data_rows: list[dict[str, Any]]) -> None:
    """Verify that a statistical test on the fixture data returns a valid p-value."""
    speed_vals = [float(row["speed"]) for row in bdd_data_rows if "speed" in row]
    angle_vals = [float(row["angle"]) for row in bdd_data_rows if "angle" in row]

    validator = StatisticalValidator()
    cfg = ValidationConfig(min_sample_size=2)
    stat_result = validator.run_test("permutation", speed_vals, angle_vals, config=cfg)
    assert stat_result.p_value < 0.05, (
        f"Expected p < 0.05 for C1 DISCOVER, got p={stat_result.p_value:.6f}"
    )


@then("fitness improvement is at least 15 percent")
def fitness_improvement_15_pct(bdd_evolution_result: dict[str, Any]) -> None:
    full = bdd_evolution_result["full"]
    assert full.improvement_pct >= 15.0, (
        f"Expected improvement >= 15%, got {full.improvement_pct:.1f}%"
    )


@then("ablation comparison is statistically significant")
def ablation_statistically_significant(bdd_evolution_result: dict[str, Any]) -> None:
    full = bdd_evolution_result["full"]
    ablation = bdd_evolution_result["ablation"]

    assert full.mean_fitness > ablation.mean_fitness, (
        f"Full evolution fitness ({full.mean_fitness:.4f}) must exceed "
        f"ablation ({ablation.mean_fitness:.4f})"
    )

    validator = StatisticalValidator()
    cfg = ValidationConfig(min_sample_size=2)
    stat_result = validator.run_test(
        "permutation",
        full.fitness_scores,
        ablation.fitness_scores,
        config=cfg,
    )
    assert stat_result.p_value < 0.05, (
        f"Expected p < 0.05 for C2 ablation, got p={stat_result.p_value:.6f}"
    )


@then("at least 90 percent of findings are retrievable")
def at_least_90_pct_retrievable(
    retrieved_findings: list[dict[str, Any]],
    stored_count: int,
) -> None:
    rate = len(retrieved_findings) / stored_count
    assert rate >= 0.9, (
        f"Expected >= 90% retrieval, got {rate:.1%} ({len(retrieved_findings)}/{stored_count})"
    )


@then("all pipeline steps have provenance entries")
def all_steps_have_provenance(bdd_cycle_result: CycleResult) -> None:
    # Provenance chains are stored in final_context["finding_chains"]
    finding_chains = bdd_cycle_result.final_context.get("finding_chains", [])
    assert len(finding_chains) > 0, (
        f"Expected finding_chains in final_context, "
        f"got keys: {list(bdd_cycle_result.final_context.keys())}"
    )
    assert len(bdd_cycle_result.steps_completed) >= 3, (
        f"Expected at least 3 steps completed, got {bdd_cycle_result.steps_completed}"
    )


@then("each provenance entry has a valid node_id and description")
def provenance_entries_valid(bdd_cycle_result: CycleResult) -> None:
    finding_chains = bdd_cycle_result.final_context.get("finding_chains", [])
    for chain in finding_chains:
        steps = chain.get("steps", [])
        for step in steps:
            assert "node_id" in step, f"Step missing node_id: {step}"
            assert "description" in step, f"Step missing description: {step}"
            assert step["node_id"], "node_id must not be empty"
            assert step["description"], "description must not be empty"


@then("both runs produce identical cycle results")
def both_runs_identical(bdd_two_results: tuple[CycleResult, CycleResult]) -> None:
    result1, result2 = bdd_two_results

    d1 = result1.model_dump()
    d2 = result2.model_dump()

    for d in (d1, d2):
        d["cycle_id"] = "X"
        d["total_duration"] = 0.0
        # Strip non-deterministic UUIDs from finding_chains
        fc = d.get("final_context", {})
        fc.pop("finding_chains", None)
        d["final_context"] = fc

    assert d1 == d2, f"Pipeline outputs differ. Differing keys: {[k for k in d1 if d1[k] != d2[k]]}"
