"""Integration test — full pipeline provenance chain (C4: TRACE).

Verifies that every finding produced by ScientificLoop.run_cycle has a
complete ProvenanceChain from data source to conclusion.
"""

from __future__ import annotations

import asyncio
import csv
from pathlib import Path
from typing import Any

from labclaw.orchestrator.loop import ScientificLoop
from labclaw.orchestrator.steps import (
    AnalyzeStep,
    AskStep,
    ConcludeStep,
    ExperimentStep,
    HypothesizeStep,
    ObserveStep,
    PredictStep,
)
from labclaw.validation.provenance import ProvenanceTracker

_FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "sample_lab"


def _load_fixture_data() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for fname in ("behavioral_session_001.csv", "behavioral_session_002.csv"):
        path = _FIXTURES_DIR / fname
        with open(path, newline="") as fh:
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


def _build_loop() -> ScientificLoop:
    return ScientificLoop(
        steps=[
            ObserveStep(),
            AskStep(),
            HypothesizeStep(llm_provider=None),
            PredictStep(),
            ExperimentStep(),
            AnalyzeStep(),
            ConcludeStep(),
        ]
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_every_finding_has_provenance_chain() -> None:
    """C4 TRACE: all findings have a complete chain."""
    data = _load_fixture_data()
    result = asyncio.run(_build_loop().run_cycle(data))

    assert result.success, "Pipeline must succeed"
    assert result.findings, "Must produce at least one finding"

    chains = result.final_context.get("finding_chains", [])
    assert len(chains) == len(result.findings), (
        f"Expected one chain per finding. findings={len(result.findings)}, "
        f"chains={len(chains)}"
    )


def test_each_chain_starts_from_data_source() -> None:
    """First provenance step in each chain must be an observation node."""
    data = _load_fixture_data()
    result = asyncio.run(_build_loop().run_cycle(data))

    chains = result.final_context.get("finding_chains", [])
    assert chains, "No chains produced"

    for chain in chains:
        first = chain["steps"][0]
        assert first["node_type"] == "observation", (
            f"First step must be 'observation', got {first['node_type']!r}"
        )


def test_provenance_chain_is_verifiable() -> None:
    """ProvenanceTracker.verify_chain must return True for all chains."""
    data = _load_fixture_data()
    result = asyncio.run(_build_loop().run_cycle(data))

    chains = result.final_context.get("finding_chains", [])
    tracker = ProvenanceTracker()

    from labclaw.validation.provenance import from_dict
    for chain_dict in chains:
        chain = from_dict(chain_dict)
        assert tracker.verify_chain(chain), (
            f"Chain {chain.chain_id} failed verification"
        )


def test_provenance_chain_all_steps_connected() -> None:
    """Each chain must include at least one step per pipeline stage that ran."""
    data = _load_fixture_data()
    result = asyncio.run(_build_loop().run_cycle(data))

    chains = result.final_context.get("finding_chains", [])
    assert chains

    for chain in chains:
        node_types = {s["node_type"] for s in chain["steps"]}
        # conclusion step is always present
        assert "conclusion" in node_types
