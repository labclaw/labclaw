"""Evolution engine — manages the 7-step evolution cycle.

Spec: docs/specs/L5-evolution.md
Design doc: section 8.3

Stage transitions: BACKTEST -> SHADOW -> CANARY -> PROMOTED
Auto-rollback if any metric drops > rollback_threshold from baseline.
"""

from __future__ import annotations

import logging
import random
from datetime import UTC, datetime
from typing import Any

from labclaw.core.events import event_registry
from labclaw.core.schemas import EvolutionStage, EvolutionTarget
from labclaw.evolution.fitness import FitnessTracker
from labclaw.evolution.schemas import (
    EvolutionCandidate,
    EvolutionConfig,
    EvolutionCycle,
    FitnessScore,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Register evolution events at module import time
# ---------------------------------------------------------------------------

_EVOLUTION_EVENTS = [
    "evolution.cycle.started",
    "evolution.cycle.advanced",
    "evolution.cycle.promoted",
    "evolution.cycle.rolled_back",
    "evolution.fitness.measured",
]

for _evt in _EVOLUTION_EVENTS:
    if not event_registry.is_registered(_evt):
        event_registry.register(_evt)

# ---------------------------------------------------------------------------
# Stage ordering
# ---------------------------------------------------------------------------

_STAGE_ORDER: list[EvolutionStage] = [
    EvolutionStage.BACKTEST,
    EvolutionStage.SHADOW,
    EvolutionStage.CANARY,
    EvolutionStage.PROMOTED,
]

# ---------------------------------------------------------------------------
# Template-based candidate proposals (MVP)
# ---------------------------------------------------------------------------

_PROPOSAL_TEMPLATES: dict[EvolutionTarget, list[dict[str, Any]]] = {
    EvolutionTarget.ANALYSIS_PARAMS: [
        {"correlation_threshold": 0.4, "_desc": "Lower correlation threshold to 0.4"},
        {"correlation_threshold": 0.6, "_desc": "Raise correlation threshold to 0.6"},
        {"anomaly_z_threshold": 1.5, "_desc": "Lower anomaly z-threshold to 1.5"},
        {"anomaly_z_threshold": 2.5, "_desc": "Raise anomaly z-threshold to 2.5"},
        {"min_sessions": 5, "_desc": "Reduce minimum sessions to 5"},
    ],
    EvolutionTarget.PROMPTS: [
        {"temperature": 0.5, "_desc": "Lower LLM temperature to 0.5"},
        {"temperature": 0.9, "_desc": "Raise LLM temperature to 0.9"},
        {"max_tokens": 1024, "_desc": "Cap generation at 1024 tokens"},
    ],
    EvolutionTarget.ROUTING: [
        {"priority_weight": 0.7, "_desc": "Increase priority weight to 0.7"},
        {"priority_weight": 0.3, "_desc": "Decrease priority weight to 0.3"},
        {"timeout_seconds": 30, "_desc": "Set routing timeout to 30s"},
    ],
    EvolutionTarget.HEURISTICS: [
        {"confidence_floor": 0.6, "_desc": "Raise confidence floor to 0.6"},
        {"confidence_floor": 0.3, "_desc": "Lower confidence floor to 0.3"},
        {"max_retries": 5, "_desc": "Increase max retries to 5"},
    ],
    EvolutionTarget.STRATEGY: [
        {"pipeline_order": "correlations_first", "_desc": "Run correlations before anomalies"},
        {"pipeline_order": "anomalies_first", "_desc": "Run anomalies before correlations"},
        {"parallel": True, "_desc": "Enable parallel mining stages"},
    ],
}


class EvolutionEngine:
    """Manages the full evolution lifecycle for all targets.

    Spec: docs/specs/L5-evolution.md
    """

    def __init__(self, config: EvolutionConfig | None = None) -> None:
        self._config = config or EvolutionConfig()
        self._fitness = FitnessTracker()
        self._cycles: dict[str, EvolutionCycle] = {}

    @property
    def config(self) -> EvolutionConfig:
        return self._config

    @property
    def fitness_tracker(self) -> FitnessTracker:
        return self._fitness

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def measure_fitness(
        self,
        target: EvolutionTarget,
        metrics: dict[str, float],
        data_points: int = 0,
    ) -> FitnessScore:
        """Measure and record fitness for a target."""
        return self._fitness.measure(target, metrics, data_points)

    def propose_candidates(
        self,
        target: EvolutionTarget,
        n: int = 3,
    ) -> list[EvolutionCandidate]:
        """Generate N candidate config variants using template-based proposals.

        MVP implementation: picks from predefined templates.
        Future: LLM-based generation.
        """
        templates = _PROPOSAL_TEMPLATES.get(target, [])
        if not templates:
            return []

        # Sample up to n distinct templates
        chosen = random.sample(templates, min(n, len(templates)))

        candidates: list[EvolutionCandidate] = []
        for tmpl in chosen:
            tmpl = dict(tmpl)  # shallow copy — do NOT mutate module-level templates
            desc = tmpl.pop("_desc", f"Variant for {target.value}")
            candidate = EvolutionCandidate(
                target=target,
                description=desc,
                config_diff={k: v for k, v in tmpl.items() if k != "_desc"},
                proposed_by="system",
            )
            candidates.append(candidate)

        return candidates

    def start_cycle(
        self,
        candidate: EvolutionCandidate,
        baseline: FitnessScore,
    ) -> EvolutionCycle:
        """Start a new evolution cycle for a candidate.

        The cycle begins in BACKTEST stage.
        Emits ``evolution.cycle.started``.
        """
        if len(self._cycles) >= self._config.max_cycles:
            # Evict oldest completed/rolled-back cycle, or oldest overall
            evict_id = None
            for cid, c in list(self._cycles.items()):
                if c.stage in (EvolutionStage.PROMOTED,) or c.rollback_reason is not None:
                    evict_id = cid
                    break
            if evict_id is None:
                evict_id = next(iter(self._cycles))
            del self._cycles[evict_id]

        cycle = EvolutionCycle(
            target=candidate.target,
            candidate=candidate,
            baseline_fitness=baseline,
            stage=EvolutionStage.BACKTEST,
        )
        self._cycles[cycle.cycle_id] = cycle

        event_registry.emit(
            "evolution.cycle.started",
            payload={
                "cycle_id": cycle.cycle_id,
                "target": cycle.target.value,
                "candidate_id": candidate.candidate_id,
            },
        )

        logger.info(
            "Evolution cycle started: %s (target=%s, candidate=%s)",
            cycle.cycle_id,
            cycle.target.value,
            candidate.candidate_id,
        )
        return cycle

    def advance_stage(
        self,
        cycle_id: str,
        new_fitness: FitnessScore,
    ) -> EvolutionCycle:
        """Advance a cycle to the next stage, or auto-rollback on regression.

        Stage transitions: BACKTEST -> SHADOW -> CANARY -> PROMOTED.
        If any metric drops > rollback_threshold from baseline, auto-rollback.
        Emits ``evolution.cycle.advanced`` or ``evolution.cycle.rolled_back``.
        On promotion, also emits ``evolution.cycle.promoted``.
        """
        cycle = self._get_cycle(cycle_id)

        if cycle.stage == EvolutionStage.PROMOTED:
            raise ValueError(f"Cycle {cycle_id} already promoted")
        if cycle.stage == EvolutionStage.ROLLED_BACK:
            raise ValueError(f"Cycle {cycle_id} already rolled back")

        # Check for regression
        regression_metric = self._check_regression(cycle.baseline_fitness, new_fitness)
        if regression_metric is not None:
            reason = (
                f"Metric '{regression_metric}' regressed beyond threshold "
                f"({self._config.rollback_threshold:.0%})"
            )
            return self.rollback(cycle_id, reason)

        # Advance to next stage
        try:
            current_idx = _STAGE_ORDER.index(cycle.stage)
        except ValueError:
            raise ValueError(
                f"Cycle {cycle_id} is in unadvanceable stage {cycle.stage!r}"
            ) from None
        if current_idx + 1 >= len(_STAGE_ORDER):
            raise ValueError(f"Cycle {cycle_id} is already at the final stage")
        next_stage = _STAGE_ORDER[current_idx + 1]
        old_stage = cycle.stage

        cycle.stage = next_stage
        cycle.current_fitness = new_fitness

        if next_stage == EvolutionStage.PROMOTED:
            cycle.promoted = True
            cycle.completed_at = datetime.now(UTC)

        event_registry.emit(
            "evolution.cycle.advanced",
            payload={
                "cycle_id": cycle_id,
                "from_stage": old_stage.value,
                "to_stage": next_stage.value,
            },
        )

        if next_stage == EvolutionStage.PROMOTED:
            event_registry.emit(
                "evolution.cycle.promoted",
                payload={
                    "cycle_id": cycle_id,
                    "target": cycle.target.value,
                    "fitness": new_fitness.metrics,
                },
            )
            logger.info("Evolution cycle promoted: %s", cycle_id)

        return cycle

    def rollback(self, cycle_id: str, reason: str) -> EvolutionCycle:
        """Manually or auto-rollback a cycle.

        Sets stage to ROLLED_BACK, records reason and completion time.
        Emits ``evolution.cycle.rolled_back``.
        """
        cycle = self._get_cycle(cycle_id)

        cycle.stage = EvolutionStage.ROLLED_BACK
        cycle.rollback_reason = reason
        cycle.promoted = False
        cycle.completed_at = datetime.now(UTC)

        event_registry.emit(
            "evolution.cycle.rolled_back",
            payload={
                "cycle_id": cycle_id,
                "reason": reason,
                "stage": cycle.stage.value,
            },
        )

        logger.warning("Evolution cycle rolled back: %s — %s", cycle_id, reason)
        return cycle

    def get_history(
        self,
        target: EvolutionTarget | None = None,
    ) -> list[EvolutionCycle]:
        """Return evolution cycles, optionally filtered by target."""
        cycles = list(self._cycles.values())
        if target is not None:
            cycles = [c for c in cycles if c.target == target]
        return sorted(cycles, key=lambda c: c.started_at)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_cycle(self, cycle_id: str) -> EvolutionCycle:
        if cycle_id not in self._cycles:
            raise KeyError(f"Evolution cycle {cycle_id!r} not found")
        return self._cycles[cycle_id]

    def _check_regression(
        self,
        baseline: FitnessScore,
        current: FitnessScore,
    ) -> str | None:
        """Return the name of the first metric that regressed, or None."""
        for metric_name, baseline_value in baseline.metrics.items():
            current_value = current.metrics.get(metric_name)
            if current_value is None:
                logger.warning("Baseline metric '%s' missing from current fitness", metric_name)
                continue
            if baseline_value == 0.0:
                continue
            drop = (baseline_value - current_value) / abs(baseline_value)
            if drop > self._config.rollback_threshold:
                return metric_name
        return None
