"""End-to-end integration test: ScientificLoop on real-format behavioral fixture data.

Loads CSV files from tests/fixtures/sample_lab/, runs a full 7-step scientific method
cycle, and asserts that patterns are discovered and the cycle succeeds.

Marked with @pytest.mark.e2e — can be filtered with: pytest -m e2e
"""

from __future__ import annotations

import asyncio
import csv
from pathlib import Path
from typing import Any

import pytest

from labclaw.orchestrator.loop import CycleResult, ScientificLoop
from labclaw.orchestrator.steps import ConcludeStep, HypothesizeStep

# ---------------------------------------------------------------------------
# Fixtures dir (absolute path, never relative)
# ---------------------------------------------------------------------------

_FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "sample_lab"
_SESSION_001 = _FIXTURES_DIR / "behavioral_session_001.csv"
_SESSION_002 = _FIXTURES_DIR / "behavioral_session_002.csv"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_behavioral_data() -> list[dict[str, Any]]:
    """Load both fixture CSV files and cast numeric columns."""
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


def _make_loop(memory_root: Path | None = None) -> ScientificLoop:
    """Return a ScientificLoop using template-based hypothesis gen (no API key)."""
    from labclaw.orchestrator.steps import (
        AnalyzeStep,
        AskStep,
        ExperimentStep,
        ObserveStep,
        PredictStep,
    )

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
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestFullPipeline:
    """End-to-end pipeline tests using sample_lab fixture data."""

    def test_fixtures_exist(self) -> None:
        """Sanity check: fixture files are present and have 50 data rows each."""
        assert _SESSION_001.exists(), f"Missing fixture: {_SESSION_001}"
        assert _SESSION_002.exists(), f"Missing fixture: {_SESSION_002}"

        for path in [_SESSION_001, _SESSION_002]:
            with open(path, newline="") as fh:
                row_count = sum(1 for _ in csv.DictReader(fh))
            assert row_count == 50, f"{path.name}: expected 50 rows, got {row_count}"

    def test_fixture_data_has_correlation(self) -> None:
        """The fixture data has speed-distance correlation r > 0.3 (embedded signal)."""
        import math

        rows = _load_behavioral_data()
        # Exclude the 2 anomaly rows (speed=999.0)
        clean = [r for r in rows if r["speed"] < 100.0]

        center_x, center_y = 150.0, 200.0
        dists = [math.sqrt((r["x"] - center_x) ** 2 + (r["y"] - center_y) ** 2) for r in clean]
        speeds = [r["speed"] for r in clean]

        n = len(clean)
        mx = sum(dists) / n
        my = sum(speeds) / n
        cov = sum((d - mx) * (s - my) for d, s in zip(dists, speeds)) / n
        sx = math.sqrt(sum((d - mx) ** 2 for d in dists) / n)
        sy = math.sqrt(sum((s - my) ** 2 for s in speeds) / n)
        r = cov / (sx * sy) if sx * sy else 0.0

        assert r > 0.3, (
            f"Expected speed-distance Pearson r > 0.3 for embedded signal, got r={r:.3f}"
        )

    def test_pipeline_success(self) -> None:
        """Full cycle on behavioral fixture data succeeds and finds patterns."""
        data = _load_behavioral_data()
        assert len(data) == 100, f"Expected 100 rows (2×50), got {len(data)}"

        loop = _make_loop()
        result: CycleResult = asyncio.run(loop.run_cycle(data))

        assert result.success is True, (
            f"Expected cycle success=True, got success={result.success}"
        )
        assert len(result.steps_completed) >= 3, (
            f"Expected >= 3 completed steps, got {result.steps_completed}"
        )
        assert result.patterns_found > 0, (
            f"Expected patterns_found > 0, got {result.patterns_found}"
        )

    def test_pipeline_deterministic(self) -> None:
        """Running the same data twice yields identical patterns_found and steps_completed."""
        data = _load_behavioral_data()

        loop1 = _make_loop()
        result1: CycleResult = asyncio.run(loop1.run_cycle(data))

        loop2 = _make_loop()
        result2: CycleResult = asyncio.run(loop2.run_cycle(data))

        assert result1.patterns_found == result2.patterns_found, (
            f"Determinism broken: run1 patterns={result1.patterns_found}, "
            f"run2 patterns={result2.patterns_found}"
        )
        assert result1.steps_completed == result2.steps_completed, (
            f"Determinism broken: run1 steps={result1.steps_completed}, "
            f"run2 steps={result2.steps_completed}"
        )

    def test_pipeline_writes_memory(self, tmp_path: Path) -> None:
        """ConcludeStep writes MEMORY.md when memory_root is provided."""
        data = _load_behavioral_data()
        memory_root = tmp_path / "lab_memory"
        memory_root.mkdir()

        loop = _make_loop(memory_root=memory_root)
        result: CycleResult = asyncio.run(loop.run_cycle(data))

        assert result.success is True

        memory_file = memory_root / "lab" / "MEMORY.md"
        assert memory_file.exists(), (
            f"Expected MEMORY.md at {memory_file}, but it was not created"
        )
        content = memory_file.read_text()
        assert len(content) > 0, "MEMORY.md should not be empty"

    def test_pipeline_cycle_id_unique(self) -> None:
        """Each cycle gets a distinct cycle_id (UUID)."""
        data = _load_behavioral_data()

        loop1 = _make_loop()
        result1: CycleResult = asyncio.run(loop1.run_cycle(data))

        loop2 = _make_loop()
        result2: CycleResult = asyncio.run(loop2.run_cycle(data))

        assert result1.cycle_id != result2.cycle_id, (
            "Each cycle should have a unique cycle_id"
        )

    def test_pipeline_hypotheses_from_patterns(self) -> None:
        """When patterns are found, hypotheses are generated."""
        data = _load_behavioral_data()
        loop = _make_loop()
        result: CycleResult = asyncio.run(loop.run_cycle(data))

        if result.patterns_found > 0:
            assert result.hypotheses_generated > 0, (
                f"Patterns found ({result.patterns_found}) but no hypotheses generated"
            )
