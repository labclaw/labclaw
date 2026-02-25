"""Fitness tracking — measures and stores fitness scores for evolution targets.

Spec: docs/specs/L5-evolution.md
"""

from __future__ import annotations

import logging
from collections import defaultdict

from labclaw.core.events import event_registry
from labclaw.core.schemas import EvolutionTarget
from labclaw.evolution.schemas import FitnessScore

logger = logging.getLogger(__name__)


class FitnessTracker:
    """Tracks fitness scores for evolution targets.

    In-memory storage; production would persist to SQLite.
    """

    def __init__(self) -> None:
        self._history: dict[EvolutionTarget, list[FitnessScore]] = defaultdict(list)

    def measure(
        self,
        target: EvolutionTarget,
        metrics: dict[str, float],
        data_points: int = 0,
    ) -> FitnessScore:
        """Record a new fitness measurement for a target.

        Emits ``evolution.fitness.measured`` event.
        """
        score = FitnessScore(
            target=target,
            metrics=metrics,
            data_points=data_points,
        )
        self._history[target].append(score)

        event_registry.emit(
            "evolution.fitness.measured",
            payload={
                "target": target.value,
                "metrics": metrics,
                "data_points": data_points,
            },
        )

        logger.info(
            "Fitness measured for %s: %s (n=%d)",
            target.value,
            metrics,
            data_points,
        )
        return score

    def get_latest(self, target: EvolutionTarget) -> FitnessScore | None:
        """Return the most recent fitness score for a target, or None."""
        history = self._history.get(target)
        if not history:
            return None
        return history[-1]

    def get_history(self, target: EvolutionTarget) -> list[FitnessScore]:
        """Return all fitness scores for a target, oldest first."""
        return list(self._history.get(target, []))

    def to_dict(self) -> dict[str, list[dict]]:
        """Serialize fitness history keyed by target value string."""
        return {
            target.value: [s.model_dump(mode="json") for s in scores]
            for target, scores in self._history.items()
        }

    @classmethod
    def from_dict(cls, data: dict[str, list[dict]]) -> FitnessTracker:
        """Deserialize fitness history from target-keyed dict."""
        tracker = cls()
        for target_str, scores_data in data.items():
            target = EvolutionTarget(target_str)
            tracker._history[target] = [FitnessScore.model_validate(s) for s in scores_data]
        return tracker
