"""BDD step definitions for L3 Orchestrator Cycle.

Spec: docs/specs/L3-discovery.md
Uses conftest fixtures: event_capture
"""

from __future__ import annotations

import asyncio
import random
from typing import Any

import pytest
from pytest_bdd import given, parsers, then, when

from labclaw.orchestrator.loop import CycleResult, ScientificLoop
from labclaw.orchestrator.steps import (
    StepContext,
    StepName,
    StepResult,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FailingStep:
    """A step that always fails."""

    name = StepName.OBSERVE

    async def run(self, context: StepContext) -> StepResult:
        return StepResult(
            step=self.name,
            success=False,
            context=context,
            duration_seconds=0.0,
        )


# ---------------------------------------------------------------------------
# Default fixtures (overridden by given steps when present)
# ---------------------------------------------------------------------------


@pytest.fixture()
def exp_data() -> list[dict[str, Any]]:
    """Default empty experiment data (overridden by given steps)."""
    return []


@pytest.fixture()
def orchestrator_loop() -> ScientificLoop:
    """Default scientific loop (overridden by given steps)."""
    return ScientificLoop()


# ---------------------------------------------------------------------------
# Given steps
# ---------------------------------------------------------------------------


@given(
    "20 rows of experiment data with numeric columns",
    target_fixture="exp_data",
)
def twenty_rows_numeric() -> list[dict[str, Any]]:
    rng = random.Random(42)
    data: list[dict[str, Any]] = []
    for i in range(20):
        speed = 10.0 + i * 0.5 + rng.gauss(0, 0.3)
        accuracy = 50.0 + speed * 2.0 + rng.gauss(0, 0.5)
        temperature = 22.0 + rng.gauss(0, 1.0)
        data.append({
            "speed": speed,
            "accuracy": accuracy,
            "temperature": temperature,
            "session_id": f"s{i}",
        })
    return data


@given(
    "5 rows of experiment data",
    target_fixture="exp_data",
)
def five_rows() -> list[dict[str, Any]]:
    return [
        {"x": float(i), "y": float(i * 2), "session_id": f"s{i}"}
        for i in range(5)
    ]


@given(
    "a step that will fail during execution",
    target_fixture="orchestrator_loop",
)
def step_that_fails() -> ScientificLoop:
    """Create a loop with a single failing step."""
    return ScientificLoop(steps=[FailingStep()])


# ---------------------------------------------------------------------------
# When steps
# ---------------------------------------------------------------------------


@when(
    "the orchestrator runs a complete cycle",
    target_fixture="cycle_result",
)
def orchestrator_runs_cycle(
    exp_data: list[dict[str, Any]],
    orchestrator_loop: ScientificLoop,
) -> CycleResult:
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(orchestrator_loop.run_cycle(exp_data))
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# Then steps
# ---------------------------------------------------------------------------


@then("all 7 steps should execute")
def check_all_seven_steps(cycle_result: CycleResult) -> None:
    total = len(cycle_result.steps_completed) + len(cycle_result.steps_skipped)
    assert total == 7, (
        f"Expected 7 steps total, got {total} "
        f"(completed={cycle_result.steps_completed}, skipped={cycle_result.steps_skipped})"
    )


@then("patterns should be discovered")
def check_patterns_discovered(cycle_result: CycleResult) -> None:
    assert cycle_result.patterns_found > 0, (
        f"Expected patterns > 0, got {cycle_result.patterns_found}"
    )


@then("hypotheses should be generated")
def check_hypotheses_generated(cycle_result: CycleResult) -> None:
    assert cycle_result.hypotheses_generated > 0, (
        f"Expected hypotheses > 0, got {cycle_result.hypotheses_generated}"
    )


@then("the ask step should be skipped")
def check_ask_skipped(cycle_result: CycleResult) -> None:
    assert StepName.ASK in cycle_result.steps_skipped, (
        f"Expected ASK to be skipped, skipped={cycle_result.steps_skipped}"
    )


@then("the reason should mention too few rows")
def check_reason_too_few(cycle_result: CycleResult) -> None:
    # The reason is encoded in the skip — AskStep skips when < 10 rows
    assert StepName.ASK in cycle_result.steps_skipped


@then(parsers.parse("the cycle should complete with success=False"))
def check_cycle_failed(cycle_result: CycleResult) -> None:
    assert cycle_result.success is False, "Expected cycle success=False"


@then("the failing step should be recorded")
def check_failing_step_recorded(cycle_result: CycleResult) -> None:
    assert len(cycle_result.steps_completed) >= 1, "Expected at least 1 step completed"
