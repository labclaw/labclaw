"""L5 Self-Evolution — autonomous strategy improvement with regression prevention.

Spec: docs/specs/L5-evolution.md
Design doc: section 8.3
"""

from __future__ import annotations

from labclaw.evolution.engine import EvolutionEngine
from labclaw.evolution.fitness import FitnessTracker
from labclaw.evolution.schemas import (
    EvolutionCandidate,
    EvolutionConfig,
    EvolutionCycle,
    EvolutionState,
    FitnessScore,
)

__all__ = [
    "EvolutionCandidate",
    "EvolutionConfig",
    "EvolutionCycle",
    "EvolutionEngine",
    "EvolutionState",
    "FitnessScore",
    "FitnessTracker",
]
