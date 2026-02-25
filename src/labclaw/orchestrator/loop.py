"""Scientific method loop — 7-step state machine orchestrator.

Spec: docs/specs/L3-discovery.md
Design doc: section 5.3 (Discovery Loop)

Runs a complete scientific method cycle:
OBSERVE -> ASK -> HYPOTHESIZE -> PREDICT -> EXPERIMENT -> ANALYZE -> CONCLUDE
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from pydantic import BaseModel, Field

from labclaw.core.events import event_registry
from labclaw.orchestrator.steps import (
    AnalyzeStep,
    AskStep,
    ConcludeStep,
    ExperimentStep,
    HypothesizeStep,
    ObserveStep,
    PredictStep,
    ScientificStep,
    StepContext,
    StepName,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Register orchestrator events
# ---------------------------------------------------------------------------

_ORCHESTRATOR_EVENTS = [
    "orchestrator.cycle.started",
    "orchestrator.cycle.completed",
    "orchestrator.step.started",
    "orchestrator.step.completed",
    "orchestrator.step.skipped",
]

for _evt in _ORCHESTRATOR_EVENTS:
    if not event_registry.is_registered(_evt):
        event_registry.register(_evt)


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------


def _uuid() -> str:
    return str(uuid.uuid4())


class CycleResult(BaseModel):
    cycle_id: str = Field(default_factory=_uuid)
    steps_completed: list[StepName] = Field(default_factory=list)
    steps_skipped: list[StepName] = Field(default_factory=list)
    total_duration: float = 0.0
    patterns_found: int = 0
    hypotheses_generated: int = 0
    success: bool = True


# ---------------------------------------------------------------------------
# ScientificLoop
# ---------------------------------------------------------------------------


class ScientificLoop:
    """7-step scientific method state machine."""

    def __init__(self, steps: list[ScientificStep] | None = None) -> None:
        if steps is not None:
            self._steps = steps
        else:
            self._steps: list[ScientificStep] = [
                ObserveStep(),
                AskStep(),
                HypothesizeStep(),
                PredictStep(),
                ExperimentStep(),
                AnalyzeStep(),
                ConcludeStep(),
            ]

    async def run_cycle(self, data_rows: list[dict[str, Any]]) -> CycleResult:
        """Run one complete scientific method cycle."""
        cycle_id = _uuid()
        t0 = time.monotonic()

        context = StepContext(data_rows=data_rows, cycle_id=cycle_id)

        event_registry.emit(
            "orchestrator.cycle.started",
            payload={"cycle_id": cycle_id, "n_rows": len(data_rows)},
        )

        steps_completed: list[StepName] = []
        steps_skipped: list[StepName] = []
        success = True

        for step in self._steps:
            step_name = step.name

            event_registry.emit(
                "orchestrator.step.started",
                payload={"cycle_id": cycle_id, "step": step_name},
            )

            result = await step.run(context)

            if result.skipped:
                steps_skipped.append(step_name)
                event_registry.emit(
                    "orchestrator.step.skipped",
                    payload={
                        "cycle_id": cycle_id,
                        "step": step_name,
                        "reason": result.skip_reason,
                    },
                )
                logger.info(
                    "Cycle %s: step %s skipped — %s",
                    cycle_id,
                    step_name,
                    result.skip_reason,
                )
            elif result.success:
                steps_completed.append(step_name)
                context = result.context
                event_registry.emit(
                    "orchestrator.step.completed",
                    payload={
                        "cycle_id": cycle_id,
                        "step": step_name,
                        "duration": result.duration_seconds,
                    },
                )
            else:
                steps_completed.append(step_name)
                context = result.context
                success = False
                event_registry.emit(
                    "orchestrator.step.completed",
                    payload={
                        "cycle_id": cycle_id,
                        "step": step_name,
                        "duration": result.duration_seconds,
                        "success": False,
                    },
                )
                logger.warning("Cycle %s: step %s failed", cycle_id, step_name)

        total_duration = time.monotonic() - t0

        cycle_result = CycleResult(
            cycle_id=cycle_id,
            steps_completed=steps_completed,
            steps_skipped=steps_skipped,
            total_duration=total_duration,
            patterns_found=len(context.patterns),
            hypotheses_generated=len(context.hypotheses),
            success=success,
        )

        event_registry.emit(
            "orchestrator.cycle.completed",
            payload={
                "cycle_id": cycle_id,
                "steps_completed": [s.value for s in steps_completed],
                "steps_skipped": [s.value for s in steps_skipped],
                "total_duration": total_duration,
                "patterns_found": cycle_result.patterns_found,
                "hypotheses_generated": cycle_result.hypotheses_generated,
                "success": success,
            },
        )

        logger.info(
            "Cycle %s completed: %d steps, %d skipped, %.2fs",
            cycle_id,
            len(steps_completed),
            len(steps_skipped),
            total_duration,
        )

        return cycle_result
