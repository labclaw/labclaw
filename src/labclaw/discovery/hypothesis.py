"""Hypothesis generation — template-based MVP, LLM-driven in future.

Spec: docs/specs/L3-discovery.md
Design doc: section 5.3 (Discovery Loop)

Maps to the HYPOTHESIZE step of the scientific method:
instead of hypotheses limited by personal experience and recent reading,
generate from all data patterns combined with full literature knowledge.

MVP: template-based generation from PatternRecord types.
Future: LLM + statistical evidence generates testable hypotheses.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from labclaw.core.events import event_registry
from labclaw.core.schemas import HypothesisStatus
from labclaw.discovery.mining import PatternRecord

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

class HypothesisInput(BaseModel):
    """Input to the hypothesis generator."""

    patterns: list[PatternRecord]
    context: str = ""
    constraints: list[str] = Field(default_factory=list)


class HypothesisOutput(BaseModel):
    """A generated hypothesis with metadata."""

    hypothesis_id: str = Field(default_factory=_uuid)
    statement: str
    testable: bool = True
    status: HypothesisStatus = HypothesisStatus.PROPOSED
    confidence: float = 0.0
    required_experiments: list[str] = Field(default_factory=list)
    resource_estimate: str = ""
    patterns_used: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Register events
# ---------------------------------------------------------------------------

_HYPOTHESIS_EVENTS = [
    "discovery.hypothesis.created",
]

for _evt in _HYPOTHESIS_EVENTS:
    if not event_registry.is_registered(_evt):
        event_registry.register(_evt)


# ---------------------------------------------------------------------------
# HypothesisGenerator
# ---------------------------------------------------------------------------

class HypothesisGenerator:
    """Template-based hypothesis generation from discovered patterns.

    Spec: docs/specs/L3-discovery.md
    MVP implementation — no LLM calls.
    """

    def generate(self, hypothesis_input: HypothesisInput) -> list[HypothesisOutput]:
        """Generate hypotheses from discovered patterns.

        For each pattern, applies a type-specific template to produce a
        testable hypothesis statement. Emits discovery.hypothesis.created
        for each hypothesis.
        """
        hypotheses: list[HypothesisOutput] = []

        for pattern in hypothesis_input.patterns:
            hypothesis = self._generate_from_pattern(pattern)
            if hypothesis is not None:
                hypotheses.append(hypothesis)

                event_registry.emit(
                    "discovery.hypothesis.created",
                    payload={
                        "hypothesis_id": hypothesis.hypothesis_id,
                        "statement": hypothesis.statement,
                        "confidence": float(hypothesis.confidence),
                    },
                )

        # Sort by confidence descending
        hypotheses.sort(key=lambda h: h.confidence, reverse=True)
        return hypotheses

    def _generate_from_pattern(self, pattern: PatternRecord) -> HypothesisOutput | None:
        """Generate a single hypothesis from a pattern using templates."""
        if pattern.pattern_type == "correlation":
            return self._from_correlation(pattern)
        if pattern.pattern_type == "anomaly":
            return self._from_anomaly(pattern)
        if pattern.pattern_type == "temporal":
            return self._from_temporal(pattern)
        if pattern.pattern_type == "cluster":
            return self._from_cluster(pattern)

        logger.warning("Unknown pattern type: %s", pattern.pattern_type)
        return None

    @staticmethod
    def _from_correlation(pattern: PatternRecord) -> HypothesisOutput:
        evidence = pattern.evidence
        col_a = evidence.get("col_a", "X")
        col_b = evidence.get("col_b", "Y")
        r = evidence.get("r", 0.0)
        p = evidence.get("p_value", 1.0)

        statement = (
            f"{col_a} is correlated with {col_b} "
            f"(r={r:.3f}, p={p:.4f}). "
            f"Hypothesis: changing {col_a} affects {col_b}."
        )

        return HypothesisOutput(
            statement=statement,
            testable=True,
            confidence=pattern.confidence,
            required_experiments=[
                f"Manipulate {col_a} and measure effect on {col_b}",
                "Control for confounding variables",
            ],
            resource_estimate="1-2 experimental sessions",
            patterns_used=[pattern.pattern_id],
        )

    @staticmethod
    def _from_anomaly(pattern: PatternRecord) -> HypothesisOutput:
        evidence = pattern.evidence
        column = evidence.get("column", "X")
        indices = evidence.get("anomalous_indices", [])

        statement = (
            f"Anomalous values in {column} at {len(indices)} data point(s). "
            f"Hypothesis: an external factor caused deviation in {column}."
        )

        return HypothesisOutput(
            statement=statement,
            testable=True,
            confidence=pattern.confidence,
            required_experiments=[
                f"Review experimental logs for sessions with anomalous {column}",
                "Replicate conditions to test reproducibility",
            ],
            resource_estimate="0.5-1 experimental sessions",
            patterns_used=[pattern.pattern_id],
        )

    @staticmethod
    def _from_temporal(pattern: PatternRecord) -> HypothesisOutput:
        evidence = pattern.evidence
        column = evidence.get("column", "X")
        direction = evidence.get("direction", "changing")

        statement = (
            f"Trend detected: {column} is {direction} over time. "
            f"Hypothesis: progressive change in {column} reflects "
            f"an underlying biological or experimental drift."
        )

        return HypothesisOutput(
            statement=statement,
            testable=True,
            confidence=pattern.confidence,
            required_experiments=[
                f"Track {column} over extended time with controls",
                "Check for equipment calibration drift",
            ],
            resource_estimate="2-3 experimental sessions",
            patterns_used=[pattern.pattern_id],
        )

    @staticmethod
    def _from_cluster(pattern: PatternRecord) -> HypothesisOutput:
        statement = (
            "Distinct clusters found in the data. "
            "Hypothesis: subpopulations exist with different characteristics."
        )

        return HypothesisOutput(
            statement=statement,
            testable=True,
            confidence=pattern.confidence,
            required_experiments=[
                "Characterize cluster members by metadata",
                "Test cluster stability with additional data",
            ],
            resource_estimate="1-2 analysis sessions",
            patterns_used=[pattern.pattern_id],
        )
