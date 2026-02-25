"""Bayesian optimization for experimental parameter tuning.

Spec: docs/specs/L3-optimization.md
Design doc: section 5.4 (Conductor)

MVP: random sampling within parameter bounds.
Future: replace with scikit-optimize GP-based optimizer.
"""

from __future__ import annotations

import logging
import random
import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from labclaw.core.events import event_registry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------


class ParameterDimension(BaseModel):
    """A single dimension in the parameter search space."""

    name: str
    low: float
    high: float
    prior: str = "uniform"


class ParameterSpace(BaseModel):
    """Definition of the experimental parameter search space."""

    name: str
    dimensions: list[ParameterDimension]


class ExperimentProposal(BaseModel):
    """A proposed set of experimental parameters."""

    proposal_id: str = Field(default_factory=_uuid)
    parameters: dict[str, float]
    expected_improvement: float = 0.0
    iteration: int = 0
    timestamp: datetime = Field(default_factory=_now)


class OptimizationResult(BaseModel):
    """Result of an executed experiment."""

    iteration: int
    parameters: dict[str, float]
    objective_value: float
    timestamp: datetime = Field(default_factory=_now)


# ---------------------------------------------------------------------------
# Register events
# ---------------------------------------------------------------------------

_OPTIMIZATION_EVENTS = [
    "optimization.proposal.created",
    "optimization.result.recorded",
]

for _evt in _OPTIMIZATION_EVENTS:
    if not event_registry.is_registered(_evt):
        event_registry.register(_evt)


# ---------------------------------------------------------------------------
# BayesianOptimizer
# ---------------------------------------------------------------------------


class BayesianOptimizer:
    """Bayesian optimization engine for experimental parameters.

    MVP implementation uses random sampling within parameter bounds.
    Tracks results and returns the best observed outcome.
    """

    def __init__(self, space: ParameterSpace) -> None:
        if not space.dimensions:
            raise ValueError("Parameter space must have at least one dimension")
        self._space = space
        self._history: list[OptimizationResult] = []
        self._iteration = 0
        self._rng = random.Random()

    def suggest(self, n: int = 1) -> list[ExperimentProposal]:
        """Suggest n experimental parameter sets via random sampling."""
        if n <= 0:
            raise ValueError(f"n must be positive, got {n}")

        proposals: list[ExperimentProposal] = []
        for _ in range(n):
            self._iteration += 1
            params = {
                dim.name: self._rng.uniform(dim.low, dim.high) for dim in self._space.dimensions
            }
            proposal = ExperimentProposal(
                parameters=params,
                expected_improvement=0.0,
                iteration=self._iteration,
            )
            proposals.append(proposal)

            event_registry.emit(
                "optimization.proposal.created",
                payload={
                    "proposal_id": proposal.proposal_id,
                    "parameters": proposal.parameters,
                    "iteration": proposal.iteration,
                },
            )

        return proposals

    def tell(self, result: OptimizationResult) -> None:
        """Record an optimization result."""
        self._history.append(result)

        event_registry.emit(
            "optimization.result.recorded",
            payload={
                "iteration": result.iteration,
                "objective_value": result.objective_value,
            },
        )

    def get_best(self) -> OptimizationResult | None:
        """Return the result with the highest objective value."""
        if not self._history:
            return None
        return max(self._history, key=lambda r: r.objective_value)

    def get_history(self) -> list[OptimizationResult]:
        """Return all recorded results in order."""
        return list(self._history)
