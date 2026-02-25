"""Unit tests — provenance tracking in pipeline steps.

Verifies that every step appends to StepContext.provenance_steps and that
ConcludeStep builds a ProvenanceChain for each finding.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from labclaw.orchestrator.steps import (
    AnalyzeStep,
    AskStep,
    ConcludeStep,
    ExperimentStep,
    HypothesizeStep,
    ObserveStep,
    PredictStep,
    StepContext,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_data(n: int = 20) -> list[dict[str, Any]]:
    return [{"x": float(i), "y": float(i * 2), "label": str(i % 3)} for i in range(n)]


def _run(coro):  # type: ignore[no-untyped-def]
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# ObserveStep provenance
# ---------------------------------------------------------------------------


def test_observe_step_appends_provenance() -> None:
    ctx = StepContext(data_rows=_make_data(20))
    result = _run(ObserveStep().run(ctx))
    assert result.success
    assert len(result.context.provenance_steps) == 1
    entry = result.context.provenance_steps[0]
    assert entry["step"] == "observe"
    assert entry["node_type"] == "observation"
    assert "node_id" in entry
    assert "timestamp" in entry


def test_observe_step_skipped_no_provenance() -> None:
    ctx = StepContext(data_rows=[])
    result = _run(ObserveStep().run(ctx))
    assert result.skipped
    assert result.context.provenance_steps == []


# ---------------------------------------------------------------------------
# AskStep provenance
# ---------------------------------------------------------------------------


def test_ask_step_appends_provenance() -> None:
    ctx = StepContext(data_rows=_make_data(20))
    # Run observe first so metadata is populated
    ctx = _run(ObserveStep().run(ctx)).context
    result = _run(AskStep().run(ctx))
    assert result.success
    prov_steps = result.context.provenance_steps
    step_names = [e["step"] for e in prov_steps]
    assert "ask" in step_names
    ask_entry = next(e for e in prov_steps if e["step"] == "ask")
    assert ask_entry["node_type"] == "pattern_mining"


def test_ask_step_skipped_no_provenance_added() -> None:
    ctx = StepContext(data_rows=_make_data(5))  # < 10 rows
    result = _run(AskStep().run(ctx))
    assert result.skipped
    assert result.context.provenance_steps == []


# ---------------------------------------------------------------------------
# HypothesizeStep provenance
# ---------------------------------------------------------------------------


def test_hypothesize_step_appends_provenance() -> None:
    # Build context with patterns already present

    data = _make_data(30)
    ctx = StepContext(data_rows=data)
    ctx = _run(ObserveStep().run(ctx)).context
    ctx = _run(AskStep().run(ctx)).context
    if not ctx.patterns:
        pytest.skip("No patterns mined from test data")
    result = _run(HypothesizeStep(llm_provider=None).run(ctx))
    assert result.success
    names = [e["step"] for e in result.context.provenance_steps]
    assert "hypothesize" in names


def test_hypothesize_step_skipped_no_provenance_added() -> None:
    ctx = StepContext(data_rows=_make_data(20), patterns=[])
    result = _run(HypothesizeStep(llm_provider=None).run(ctx))
    assert result.skipped
    assert result.context.provenance_steps == []


# ---------------------------------------------------------------------------
# PredictStep provenance
# ---------------------------------------------------------------------------


def test_predict_step_appends_provenance() -> None:
    data = _make_data(30)
    ctx = StepContext(
        data_rows=data,
        metadata={"data_stats": {"numeric_columns": ["x", "y"]}},
    )
    result = _run(PredictStep().run(ctx))
    assert result.success or result.skipped
    if not result.skipped:
        names = [e["step"] for e in result.context.provenance_steps]
        assert "predict" in names
        entry = next(e for e in result.context.provenance_steps if e["step"] == "predict")
        assert entry["node_type"] == "predictive_model"


def test_predict_step_skipped_no_data() -> None:
    ctx = StepContext(data_rows=[])
    result = _run(PredictStep().run(ctx))
    assert result.skipped


def test_predict_step_skipped_no_numeric_cols() -> None:
    ctx = StepContext(
        data_rows=_make_data(20),
        metadata={"data_stats": {"numeric_columns": ["x"]}},
    )
    result = _run(PredictStep().run(ctx))
    assert result.skipped


# ---------------------------------------------------------------------------
# ExperimentStep provenance
# ---------------------------------------------------------------------------


def test_experiment_step_appends_provenance() -> None:
    data = _make_data(20)
    ctx = StepContext(
        data_rows=data,
        metadata={"data_stats": {"numeric_columns": ["x", "y"]}},
    )
    result = _run(ExperimentStep().run(ctx))
    assert result.success or result.skipped
    if not result.skipped:
        names = [e["step"] for e in result.context.provenance_steps]
        assert "experiment" in names


def test_experiment_step_skipped_no_numeric_cols() -> None:
    ctx = StepContext(data_rows=_make_data(20), metadata={"data_stats": {"numeric_columns": []}})
    result = _run(ExperimentStep().run(ctx))
    assert result.skipped


# ---------------------------------------------------------------------------
# AnalyzeStep provenance
# ---------------------------------------------------------------------------


def test_analyze_step_appends_provenance() -> None:
    data = _make_data(30)
    ctx = StepContext(data_rows=data)
    ctx = _run(ObserveStep().run(ctx)).context
    ctx = _run(AskStep().run(ctx)).context
    if not ctx.patterns:
        pytest.skip("No patterns for analyze")
    result = _run(AnalyzeStep().run(ctx))
    assert result.success
    names = [e["step"] for e in result.context.provenance_steps]
    assert "analyze" in names
    entry = next(e for e in result.context.provenance_steps if e["step"] == "analyze")
    assert entry["node_type"] == "statistical_analysis"


def test_analyze_step_skipped_no_patterns() -> None:
    ctx = StepContext(data_rows=_make_data(20), patterns=[])
    result = _run(AnalyzeStep().run(ctx))
    assert result.skipped


# ---------------------------------------------------------------------------
# ConcludeStep provenance — chains built for each finding
# ---------------------------------------------------------------------------


def test_conclude_step_builds_finding_chains() -> None:
    data = _make_data(30)
    ctx = StepContext(data_rows=data)
    # Run the full pipeline
    ctx = _run(ObserveStep().run(ctx)).context
    ctx = _run(AskStep().run(ctx)).context
    ctx = _run(HypothesizeStep(llm_provider=None).run(ctx)).context
    ctx = _run(PredictStep().run(ctx)).context
    ctx = _run(ExperimentStep().run(ctx)).context
    ctx = _run(AnalyzeStep().run(ctx)).context
    result = _run(ConcludeStep().run(ctx))
    assert result.success
    chains = result.context.metadata.get("finding_chains", [])
    assert len(chains) > 0
    # Every chain must have steps
    for chain in chains:
        assert len(chain["steps"]) > 0
        assert chain["finding_id"] != ""


def test_conclude_step_chain_starts_from_observation() -> None:
    """When observe ran, first provenance step node_type should be 'observation'."""
    data = _make_data(30)
    ctx = StepContext(data_rows=data)
    ctx = _run(ObserveStep().run(ctx)).context
    ctx = _run(AskStep().run(ctx)).context
    ctx = _run(HypothesizeStep(llm_provider=None).run(ctx)).context
    ctx = _run(PredictStep().run(ctx)).context
    ctx = _run(ExperimentStep().run(ctx)).context
    ctx = _run(AnalyzeStep().run(ctx)).context
    result = _run(ConcludeStep().run(ctx))
    chains = result.context.metadata.get("finding_chains", [])
    assert chains
    first_chain = chains[0]
    first_step = first_chain["steps"][0]
    assert first_step["node_type"] == "observation"


def test_conclude_step_no_prior_provenance_still_builds_chain() -> None:
    """Even with empty provenance_steps, ConcludeStep builds chains via conclude entry."""
    ctx = StepContext(data_rows=_make_data(5))
    # Skip all steps — go straight to conclude
    result = _run(ConcludeStep().run(ctx))
    assert result.success
    chains = result.context.metadata.get("finding_chains", [])
    assert len(chains) > 0
    for chain in chains:
        assert len(chain["steps"]) >= 1  # at least the conclude step


def test_conclude_prov_entry_appended_to_provenance_steps() -> None:
    ctx = StepContext(data_rows=_make_data(5))
    result = _run(ConcludeStep().run(ctx))
    names = [e["step"] for e in result.context.provenance_steps]
    assert "conclude" in names


def test_step_context_provenance_steps_field_default() -> None:
    ctx = StepContext()
    assert ctx.provenance_steps == []
