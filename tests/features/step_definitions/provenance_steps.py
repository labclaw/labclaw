"""BDD step definitions for layer3_engine/provenance.feature.

Covers C4: TRACE — full provenance chains from raw data to conclusion.
"""

from __future__ import annotations

import asyncio
import csv
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

from pytest_bdd import given, then, when

from labclaw.export.nwb import NWBExporter
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
from labclaw.validation.provenance import ProvenanceTracker
from labclaw.validation.statistics import ProvenanceChain, ProvenanceStep

_FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures" / "sample_lab"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_data() -> list[dict[str, Any]]:
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


def _run_cycle(data: list[dict[str, Any]]) -> CycleResult:
    return asyncio.run(_build_loop().run_cycle(data))


# ---------------------------------------------------------------------------
# Given steps
# ---------------------------------------------------------------------------


@given("behavioral data from fixtures", target_fixture="fixture_data")
def behavioral_data_from_fixtures() -> list[dict[str, Any]]:
    return _load_data()


@given("a completed discovery cycle with findings", target_fixture="cycle_result_with_findings")
def completed_cycle_with_findings() -> CycleResult:
    return _run_cycle(_load_data())


@given("a finding with a provenance chain", target_fixture="single_chain")
def finding_with_provenance_chain() -> ProvenanceChain:
    tracker = ProvenanceTracker()
    steps = [
        ProvenanceStep(node_id="n1", node_type="observation", description="raw data"),
        ProvenanceStep(node_id="n2", node_type="pattern_mining", description="patterns"),
        ProvenanceStep(node_id="n3", node_type="conclusion", description="finding"),
    ]
    return tracker.build_chain("find-bdd-001", steps)


@given("a completed discovery cycle", target_fixture="cycle_for_export")
def completed_cycle_for_export() -> CycleResult:
    return _run_cycle(_load_data())


# ---------------------------------------------------------------------------
# When steps
# ---------------------------------------------------------------------------


@when(
    "I run a full discovery cycle with provenance tracking",
    target_fixture="provenance_cycle_result",
)
def run_cycle_with_provenance(fixture_data: list[dict[str, Any]]) -> CycleResult:
    return _run_cycle(fixture_data)


@when("I export to NWB format", target_fixture="nwb_export_path")
def export_to_nwb(cycle_result_with_findings: CycleResult, tmp_path: Path) -> Path:
    session_data = {
        "session_id": cycle_result_with_findings.cycle_id,
        "findings": cycle_result_with_findings.findings,
        "provenance_steps": [],
        "finding_chains": cycle_result_with_findings.final_context.get("finding_chains", []),
        "metadata": cycle_result_with_findings.final_context,
    }
    out = tmp_path / "session.json"
    exporter = NWBExporter()
    with patch.dict(sys.modules, {"pynwb": None}):
        return exporter.export_session(session_data, out)


@when("I verify the chain", target_fixture="verification_result")
def verify_chain(single_chain: ProvenanceChain) -> bool:
    return ProvenanceTracker().verify_chain(single_chain)


@when(
    "I export with NWB format but pynwb is unavailable",
    target_fixture="json_fallback_path",
)
def export_nwb_no_pynwb(cycle_for_export: CycleResult, tmp_path: Path) -> Path:
    session_data = {
        "session_id": cycle_for_export.cycle_id,
        "findings": cycle_for_export.findings,
        "provenance_steps": [],
        "finding_chains": cycle_for_export.final_context.get("finding_chains", []),
    }
    out = tmp_path / "fallback.json"
    exporter = NWBExporter()
    with patch.dict(sys.modules, {"pynwb": None}):
        return exporter.export_session(session_data, out)


# ---------------------------------------------------------------------------
# Then steps
# ---------------------------------------------------------------------------


@then("every finding has a provenance chain")
def every_finding_has_chain(provenance_cycle_result: CycleResult) -> None:
    chains = provenance_cycle_result.final_context.get("finding_chains", [])
    findings = provenance_cycle_result.findings
    assert len(findings) > 0, "Pipeline must produce at least one finding"
    assert len(chains) == len(findings), (
        f"Each finding must have a chain. findings={len(findings)}, chains={len(chains)}"
    )


@then("each chain starts from the data source")
def each_chain_starts_from_source(provenance_cycle_result: CycleResult) -> None:
    chains = provenance_cycle_result.final_context.get("finding_chains", [])
    for chain in chains:
        first = chain["steps"][0]
        assert first["node_type"] == "observation", (
            f"Expected first step to be 'observation', got {first['node_type']!r}"
        )


@then("the export file contains provenance metadata")
def export_contains_provenance(nwb_export_path: Path) -> None:
    import json
    assert nwb_export_path.exists()
    payload = json.loads(nwb_export_path.read_text())
    assert "provenance_steps" in payload or "finding_chains" in payload


@then("all steps are present and connected")
def all_steps_present(verification_result: bool) -> None:
    assert verification_result is True


@then("a JSON fallback file is created")
def json_fallback_created(json_fallback_path: Path) -> None:
    import json
    assert json_fallback_path.exists()
    payload = json.loads(json_fallback_path.read_text())
    assert payload["format"] == "labclaw-json-stub"
