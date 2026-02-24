"""Pydantic schemas for the self-evolution subsystem.

Spec: docs/specs/L5-evolution.md
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from labclaw.core.schemas import EvolutionStage, EvolutionTarget


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class FitnessScore(BaseModel):
    """Measured fitness for one evolution target at a point in time."""

    target: EvolutionTarget
    metrics: dict[str, float]
    measured_at: datetime = Field(default_factory=_now)
    data_points: int = 0


class EvolutionCandidate(BaseModel):
    """A proposed configuration variant for an evolution target."""

    candidate_id: str = Field(default_factory=_uuid)
    target: EvolutionTarget
    description: str
    config_diff: dict[str, Any] = Field(default_factory=dict)
    proposed_at: datetime = Field(default_factory=_now)
    proposed_by: str = "system"


class EvolutionCycle(BaseModel):
    """Tracks one candidate through the full promotion pipeline."""

    cycle_id: str = Field(default_factory=_uuid)
    target: EvolutionTarget
    candidate: EvolutionCandidate
    baseline_fitness: FitnessScore
    current_fitness: FitnessScore | None = None
    stage: EvolutionStage = EvolutionStage.BACKTEST
    started_at: datetime = Field(default_factory=_now)
    completed_at: datetime | None = None
    promoted: bool = False
    rollback_reason: str | None = None


class EvolutionConfig(BaseModel):
    """Tuning knobs for the evolution engine."""

    min_soak_sessions: int = 5
    rollback_threshold: float = 0.1
    max_candidates: int = 3
    diversity_min: int = 2
    max_cycles: int = 1000


class EvolutionState(BaseModel):
    """Serializable snapshot of all evolution state for persistence."""

    cycles: list[EvolutionCycle] = Field(default_factory=list)
    fitness_history: dict[str, list[FitnessScore]] = Field(default_factory=dict)
    saved_at: datetime = Field(default_factory=_now)
