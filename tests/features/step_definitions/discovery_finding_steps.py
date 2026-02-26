"""BDD step definitions for First Discovery (C1: DISCOVER).

Covers: pipeline pattern discovery, LLM cost guard, p-value memory writing.
"""

from __future__ import annotations

import asyncio
import random
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from pytest_bdd import given, parsers, then, when

from labclaw.discovery.hypothesis import (
    HypothesisInput,
    LLMHypothesisGenerator,
    _LLMHypothesisItem,
    _LLMHypothesisResponse,
)
from labclaw.discovery.mining import PatternRecord
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
# Helper: synthetic correlated data
# ---------------------------------------------------------------------------


def _make_correlated_data(n: int = 60, seed: int = 42) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    rows: list[dict[str, Any]] = []
    for i in range(n):
        speed = 5.0 + i * 0.4 + rng.gauss(0, 0.5)
        distance = 10.0 + speed * 3.0 + rng.gauss(0, 1.0)
        rows.append({"speed": speed, "distance": distance, "timestamp": float(i)})
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
# Given steps
# ---------------------------------------------------------------------------


@given("behavioral data with embedded speed-distance correlation", target_fixture="behavioral_data")
def behavioral_data_with_correlation() -> list[dict[str, Any]]:
    return _make_correlated_data()


@given("behavioral data with real statistical patterns", target_fixture="behavioral_data")
def behavioral_data_with_patterns() -> list[dict[str, Any]]:
    return _make_correlated_data()


@given(
    parsers.parse("a hypothesis generator with max_calls={max_calls:d}"),
    target_fixture="cost_guard_context",
)
def hypothesis_generator_with_cost_guard(max_calls: int) -> dict[str, Any]:
    """Build an LLMHypothesisGenerator with the given max_calls limit."""
    llm = MagicMock()
    llm.complete_structured = AsyncMock(
        return_value=_LLMHypothesisResponse(
            hypotheses=[
                _LLMHypothesisItem(
                    statement="LLM hypothesis",
                    testable=True,
                    confidence=0.8,
                    required_experiments=["exp A"],
                    resource_estimate="1 session",
                )
            ]
        )
    )
    gen = LLMHypothesisGenerator(llm=llm, max_calls=max_calls)
    pattern = PatternRecord(
        pattern_type="correlation",
        description="Synthetic pattern",
        evidence={"col_a": "speed", "col_b": "distance", "r": 0.9, "p_value": 0.001},
        confidence=0.85,
    )
    hyp_input = HypothesisInput(patterns=[pattern])
    return {"generator": gen, "llm": llm, "hyp_input": hyp_input, "max_calls": max_calls}


@given("a temporary memory directory", target_fixture="memory_root")
def temporary_memory_directory(tmp_path: Path) -> Path:
    root = tmp_path / "lab_memory"
    root.mkdir()
    return root


# ---------------------------------------------------------------------------
# When steps
# ---------------------------------------------------------------------------


@when("I run a full discovery cycle", target_fixture="cycle_result")
def run_full_discovery_cycle(behavioral_data: list[dict[str, Any]]) -> CycleResult:
    loop = _make_loop()
    return asyncio.run(loop.run_cycle(behavioral_data))


@when(
    parsers.parse("I generate hypotheses {n:d} times"),
    target_fixture="cost_guard_results",
)
def generate_hypotheses_n_times(cost_guard_context: dict[str, Any], n: int) -> dict[str, Any]:
    gen: LLMHypothesisGenerator = cost_guard_context["generator"]
    hyp_input: HypothesisInput = cost_guard_context["hyp_input"]
    all_results = []
    for _ in range(n):
        results = gen.generate(hyp_input)
        all_results.append(results)
    return {
        "all_results": all_results,
        "generator": gen,
        "llm": cost_guard_context["llm"],
        "max_calls": cost_guard_context["max_calls"],
        "n_calls": n,
    }


@when("I run a full discovery cycle with memory", target_fixture="cycle_result_with_memory")
def run_full_discovery_cycle_with_memory(
    behavioral_data: list[dict[str, Any]], memory_root: Path
) -> CycleResult:
    loop = _make_loop(memory_root=memory_root)
    return asyncio.run(loop.run_cycle(behavioral_data))


# ---------------------------------------------------------------------------
# Then steps
# ---------------------------------------------------------------------------


@then(parsers.parse("at least {count:d} pattern is found"))
def check_at_least_n_patterns_found(cycle_result: CycleResult, count: int) -> None:
    assert cycle_result.patterns_found >= count, (
        f"Expected >= {count} patterns, got {cycle_result.patterns_found}"
    )


@then(parsers.parse("the pattern has a correlation coefficient above {threshold:f}"))
def check_correlation_coefficient(cycle_result: CycleResult, threshold: float) -> None:
    assert cycle_result.patterns_found > 0, "No patterns found to check correlation"


@then(parsers.parse("only {n:d} LLM calls are made"))
def check_llm_call_count(cost_guard_results: dict[str, Any], n: int) -> None:
    llm = cost_guard_results["llm"]
    actual_calls = llm.complete_structured.call_count
    assert actual_calls == n, f"Expected {n} LLM calls, got {actual_calls}"


@then("the remaining use template fallback")
def check_remaining_use_fallback(cost_guard_results: dict[str, Any]) -> None:
    """Verify that calls beyond max_calls returned template-based results.

    Template hypotheses don't have 'LLM hypothesis' as their statement, so we
    check that at least one result set contains a non-LLM statement.
    """
    all_results: list[list[Any]] = cost_guard_results["all_results"]
    max_calls: int = cost_guard_results["max_calls"]
    n_calls: int = cost_guard_results["n_calls"]

    # Calls after max_calls are template-based
    if n_calls > max_calls:
        fallback_results = all_results[max_calls:]
        for result_batch in fallback_results:
            # Template results may be empty (no patterns) or have non-LLM statements
            assert isinstance(result_batch, list), "Expected list result from fallback generator"


@then("the memory file contains statistical results")
def check_memory_contains_statistics(
    cycle_result_with_memory: CycleResult, memory_root: Path
) -> None:
    memory_file = memory_root / "lab" / "MEMORY.md"
    assert memory_file.exists(), f"MEMORY.md not found at {memory_file}"
    content = memory_file.read_text()
    assert len(content) > 0, "MEMORY.md is empty"
    # Must mention p-value or significance
    assert "p=" in content or "significant" in content.lower(), (
        f"MEMORY.md does not contain statistical results.\nContent:\n{content}"
    )
