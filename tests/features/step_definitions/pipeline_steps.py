"""BDD step definitions for the full end-to-end scientific pipeline.

Covers scenarios in tests/features/layer3_engine/full_pipeline.feature.
"""

from __future__ import annotations

import asyncio
import csv
from pathlib import Path
from typing import Any

from pytest_bdd import given, then, when

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

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures" / "sample_lab"
_SESSION_001 = _FIXTURES_DIR / "behavioral_session_001.csv"
_SESSION_002 = _FIXTURES_DIR / "behavioral_session_002.csv"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_behavioral_data() -> list[dict[str, Any]]:
    """Load both fixture CSV files and cast numeric columns to float."""
    rows: list[dict[str, Any]] = []
    for csv_path in [_SESSION_001, _SESSION_002]:
        with open(csv_path, newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                rows.append({
                    "timestamp": row["timestamp"],
                    "x": float(row["x"]),
                    "y": float(row["y"]),
                    "speed": float(row["speed"]),
                    "angle": float(row["angle"]),
                    "zone": row["zone"],
                    "animal_id": row["animal_id"],
                })
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
            ConcludeStep(memory_root=memory_root, entity_id="lab"),
        ]
    )


# ---------------------------------------------------------------------------
# Given steps
# ---------------------------------------------------------------------------


@given(
    "behavioral data from 2 sessions with 50 rows each",
    target_fixture="behavioral_data",
)
def behavioral_data_from_fixtures() -> list[dict[str, Any]]:
    """Load 100 rows from the sample_lab fixture CSV files."""
    data = _load_behavioral_data()
    assert len(data) == 100, f"Expected 100 rows, got {len(data)}"
    return data


@given("a temporary memory directory", target_fixture="memory_dir")
def temporary_memory_directory(tmp_path: Path) -> Path:
    """Create a fresh temporary directory for memory writes."""
    mem = tmp_path / "pipeline_memory"
    mem.mkdir()
    return mem


# ---------------------------------------------------------------------------
# When steps
# ---------------------------------------------------------------------------


@when("I run a full scientific method cycle", target_fixture="cycle_result")
def run_full_cycle(behavioral_data: list[dict[str, Any]]) -> CycleResult:
    loop = _build_loop()
    return asyncio.run(loop.run_cycle(behavioral_data))


@when(
    "I run 2 scientific method cycles on the same data",
    target_fixture="two_cycle_results",
)
def run_two_cycles(behavioral_data: list[dict[str, Any]]) -> tuple[CycleResult, CycleResult]:
    result1 = asyncio.run(_build_loop().run_cycle(behavioral_data))
    result2 = asyncio.run(_build_loop().run_cycle(behavioral_data))
    return result1, result2


@when(
    "I run a full scientific method cycle with memory writing",
    target_fixture="cycle_result_with_memory",
)
def run_cycle_with_memory(
    behavioral_data: list[dict[str, Any]],
    memory_dir: Path,
) -> CycleResult:
    loop = _build_loop(memory_root=memory_dir)
    return asyncio.run(loop.run_cycle(behavioral_data))


# ---------------------------------------------------------------------------
# Then steps
# ---------------------------------------------------------------------------


@then("the cycle completes successfully")
def cycle_completes_successfully(cycle_result: CycleResult) -> None:
    assert cycle_result.success is True, (
        f"Expected cycle success=True, got success={cycle_result.success}"
    )


@then("at least 1 pattern is found")
def at_least_one_pattern(cycle_result: CycleResult) -> None:
    assert cycle_result.patterns_found > 0, (
        f"Expected patterns_found > 0, got {cycle_result.patterns_found}"
    )


@then("both cycles find the same number of patterns")
def both_cycles_same_patterns(
    two_cycle_results: tuple[CycleResult, CycleResult],
) -> None:
    r1, r2 = two_cycle_results
    assert r1.patterns_found == r2.patterns_found, (
        f"Determinism broken: run1 patterns={r1.patterns_found}, "
        f"run2 patterns={r2.patterns_found}"
    )


@then("a MEMORY.md file is created in the memory directory")
def memory_md_created(
    cycle_result_with_memory: CycleResult,
    memory_dir: Path,
) -> None:
    success = cycle_result_with_memory.success
    assert success is True, (
        f"Cycle must succeed before checking MEMORY.md, got success={success}"
    )
    memory_file = memory_dir / "lab" / "MEMORY.md"
    assert memory_file.exists(), (
        f"Expected MEMORY.md at {memory_file}, but it was not created. "
        f"Memory dir contents: {list(memory_dir.rglob('*'))}"
    )
