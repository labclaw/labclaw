"""Integration test — C1: DISCOVER.

C1 acceptance criterion: data → at least 1 finding with p < 0.05.

Marked @pytest.mark.e2e — run with: pytest -m e2e
"""

from __future__ import annotations

import asyncio
import random
from pathlib import Path
from typing import Any

import pytest

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
# Sample data with an embedded correlated signal strong enough for p < 0.05
# ---------------------------------------------------------------------------


def _make_sample_data(n: int = 60, seed: int = 42) -> list[dict[str, Any]]:
    """Generate behavioral data with strong speed-distance correlation.

    Uses a fixed seed so the test is deterministic.  n=60 rows gives
    enough power for the permutation test to reach p < 0.05.
    """
    rng = random.Random(seed)
    rows: list[dict[str, Any]] = []
    for i in range(n):
        speed = 5.0 + i * 0.4 + rng.gauss(0, 0.5)
        distance = 10.0 + speed * 3.0 + rng.gauss(0, 1.0)
        rows.append(
            {
                "speed": speed,
                "distance": distance,
                "timestamp": i,
            }
        )
    return rows


def _make_loop(memory_root: Path | None = None) -> ScientificLoop:
    conclude = ConcludeStep(memory_root=memory_root, entity_id="lab")
    return ScientificLoop(
        steps=[
            ObserveStep(),
            AskStep(),
            HypothesizeStep(llm_provider=None),
            PredictStep(),
            ExperimentStep(),
            AnalyzeStep(),
            conclude,
        ]
    )


# ---------------------------------------------------------------------------
# C1 DISCOVER: pipeline → at least 1 finding with p < 0.05
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_pipeline_produces_finding_with_p_value(tmp_path: Path) -> None:
    """C1: Run pipeline on correlated data → p < 0.05 in at least 1 validated pattern."""
    sample_data = _make_sample_data()
    memory_root = tmp_path / "lab_memory"
    memory_root.mkdir()

    loop = _make_loop(memory_root=memory_root)
    result: CycleResult = asyncio.run(loop.run_cycle(sample_data))

    assert result.success, f"Pipeline failed: {result}"
    assert result.patterns_found > 0, "Expected at least 1 pattern to be found"

    # Check that MEMORY.md was written with p-value mention
    memory_file = memory_root / "lab" / "MEMORY.md"
    assert memory_file.exists(), f"MEMORY.md not found at {memory_file}"
    content = memory_file.read_text()
    assert len(content) > 0, "MEMORY.md is empty"

    # C1 criterion: content must mention p-value or significance
    assert "p=" in content or "significant" in content.lower(), (
        f"MEMORY.md does not mention p-values or significance.\nContent:\n{content}"
    )


@pytest.mark.e2e
def test_pipeline_finds_significant_correlation(tmp_path: Path) -> None:
    """C1: Correlated data → at least 1 pattern is statistically significant (p < 0.05)."""
    sample_data = _make_sample_data()
    memory_root = tmp_path / "lab_memory"
    memory_root.mkdir()

    loop = _make_loop(memory_root=memory_root)
    result: CycleResult = asyncio.run(loop.run_cycle(sample_data))

    assert result.success

    memory_file = memory_root / "lab" / "MEMORY.md"
    content = memory_file.read_text()

    # At least one significant=True line should appear
    assert "significant=True" in content, (
        f"Expected 'significant=True' in MEMORY.md.\nContent:\n{content}"
    )
