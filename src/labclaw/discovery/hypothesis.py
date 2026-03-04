"""Hypothesis generation — template-based + LLM-driven.

Spec: docs/specs/L3-discovery.md
Design doc: section 5.3 (Discovery Loop)

Maps to the HYPOTHESIZE step of the scientific method:
instead of hypotheses limited by personal experience and recent reading,
generate from all data patterns combined with full literature knowledge.

Two implementations:
  - HypothesisGenerator: template-based (always available, no API key needed)
  - LLMHypothesisGenerator: LLM-powered via LLMProvider, falls back to templates on error
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from labclaw.core.events import event_registry
from labclaw.core.schemas import HypothesisStatus
from labclaw.discovery.mining import PatternRecord
from labclaw.llm.provider import LLMProvider

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
    context_findings: list[dict] = Field(default_factory=list)


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

    When *plugin_templates* are provided, domain-specific templates are used
    in addition to built-in ones.
    """

    def __init__(self, plugin_templates: list[dict] | None = None) -> None:
        self._plugin_templates = plugin_templates or []

    def generate(self, hypothesis_input: HypothesisInput) -> list[HypothesisOutput]:
        """Generate hypotheses from discovered patterns.

        For each pattern, applies a type-specific template to produce a
        testable hypothesis statement. When ``context_findings`` are provided
        the generated statements reference those past discoveries.
        Emits discovery.hypothesis.created for each hypothesis.
        """
        hypotheses: list[HypothesisOutput] = []

        past_context = self._format_past_findings(hypothesis_input.context_findings)

        for pattern in hypothesis_input.patterns:
            hypothesis = self._generate_from_pattern(pattern, past_context=past_context)
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

        # Generate from plugin templates
        for tmpl in self._plugin_templates:
            hyp = self._from_plugin_template(tmpl, hypothesis_input.patterns)
            if hyp is not None:
                hypotheses.append(hyp)

        # Sort by confidence descending
        hypotheses.sort(key=lambda h: h.confidence, reverse=True)
        return hypotheses

    @staticmethod
    def _from_plugin_template(
        template: dict, patterns: list[PatternRecord]
    ) -> HypothesisOutput | None:
        """Generate a hypothesis from a plugin-provided template."""
        statement = template.get("statement", "")
        if not statement:
            return None
        # Substitute {pattern_count} placeholder if present
        statement = statement.replace("{pattern_count}", str(len(patterns)))
        return HypothesisOutput(
            statement=statement,
            testable=template.get("testable", True),
            confidence=template.get("confidence", 0.5),
            required_experiments=template.get("required_experiments", []),
            resource_estimate=template.get("resource_estimate", ""),
            patterns_used=[p.pattern_id for p in patterns[:5]],
        )

    @staticmethod
    def _format_past_findings(context_findings: list[dict]) -> str:
        """Build a human-readable summary of past findings for template use."""
        if not context_findings:
            return ""
        lines: list[str] = ["Building on past findings:"]
        for i, f in enumerate(context_findings, 1):
            desc = f.get("description") or f.get("statement") or f.get("finding_id", f"finding-{i}")
            lines.append(f"  [{i}] {desc}")
        return " ".join(lines)

    def _generate_from_pattern(
        self, pattern: PatternRecord, past_context: str = ""
    ) -> HypothesisOutput | None:
        """Generate a single hypothesis from a pattern using templates."""
        if pattern.pattern_type == "correlation":
            hyp = self._from_correlation(pattern)
        elif pattern.pattern_type == "anomaly":
            hyp = self._from_anomaly(pattern)
        elif pattern.pattern_type == "temporal":
            hyp = self._from_temporal(pattern)
        elif pattern.pattern_type == "cluster":
            hyp = self._from_cluster(pattern)
        else:
            logger.warning("Unknown pattern type: %s", pattern.pattern_type)
            return None

        if past_context and hyp is not None:
            hyp = hyp.model_copy(update={"statement": hyp.statement + " " + past_context})
        return hyp

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


# ---------------------------------------------------------------------------
# LLM-powered Hypothesis Response Model
# ---------------------------------------------------------------------------


class _LLMHypothesisItem(BaseModel):
    """Schema for a single LLM-generated hypothesis (used for structured output)."""

    statement: str
    testable: bool = True
    confidence: float
    required_experiments: list[str]
    resource_estimate: str


class _LLMHypothesisResponse(BaseModel):
    """Schema for the LLM structured response containing multiple hypotheses."""

    hypotheses: list[_LLMHypothesisItem]


# ---------------------------------------------------------------------------
# LLMHypothesisGenerator
# ---------------------------------------------------------------------------


class LLMHypothesisGenerator:
    """LLM-powered hypothesis generation from discovered patterns.

    Falls back to template-based HypothesisGenerator on any LLM error or when
    the cost guard limit (max_calls) is exceeded.
    """

    def __init__(self, llm: LLMProvider, max_calls: int = 50) -> None:
        self._llm = llm
        self._fallback = HypothesisGenerator()
        self._max_calls = max_calls
        self._call_count = 0

    def generate(self, hypothesis_input: HypothesisInput) -> list[HypothesisOutput]:
        """Generate hypotheses — delegates to async _generate_llm, falls back on error.

        If _call_count >= max_calls the cost guard activates and template-based
        generation is used instead of calling the LLM.
        """
        if self._call_count >= self._max_calls:
            logger.info(
                "LLM cost guard triggered (call_count=%d >= max_calls=%d): using templates",
                self._call_count,
                self._max_calls,
            )
            return self._fallback.generate(hypothesis_input)

        self._call_count += 1

        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # Already inside an async context — use a new thread to avoid deadlock
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                result = pool.submit(asyncio.run, self._generate_llm(hypothesis_input)).result()
            return result

        return asyncio.run(self._generate_llm(hypothesis_input))

    async def _generate_llm(self, hypothesis_input: HypothesisInput) -> list[HypothesisOutput]:
        """Call the LLM to generate hypotheses; fall back to templates on error."""
        if not hypothesis_input.patterns:
            return []

        prompt = self._build_prompt(hypothesis_input)
        system = (
            "You are a scientific hypothesis generator for a neuroscience laboratory. "
            "Given experimental data patterns, generate testable hypotheses with "
            "confidence scores, required experiments, and resource estimates. "
            "Be specific and grounded in the evidence provided."
        )

        try:
            response = await self._llm.complete_structured(
                prompt,
                system=system,
                response_model=_LLMHypothesisResponse,
                temperature=0.7,
            )
        except Exception:
            logger.warning("LLM hypothesis generation failed, falling back to templates")
            return self._fallback.generate(hypothesis_input)

        # Convert LLM response to HypothesisOutput objects
        pattern_ids = [p.pattern_id for p in hypothesis_input.patterns]
        hypotheses: list[HypothesisOutput] = []

        typed_response = _LLMHypothesisResponse.model_validate(response.model_dump())
        for item in typed_response.hypotheses[:20]:
            statement = item.statement.strip()
            experiments = [e.strip() for e in item.required_experiments if e.strip()]
            if not statement:
                logger.warning("Discarding empty LLM hypothesis statement")
                continue
            if len(statement) > 1000:
                logger.warning("Discarding overly long LLM hypothesis statement")
                continue
            if not experiments:
                logger.warning("Discarding LLM hypothesis without experiments")
                continue
            hypothesis = HypothesisOutput(
                statement=statement,
                testable=item.testable,
                confidence=max(0.0, min(item.confidence, 1.0)),
                required_experiments=experiments[:10],
                resource_estimate=item.resource_estimate.strip()[:200],
                patterns_used=pattern_ids,
            )
            hypotheses.append(hypothesis)

            event_registry.emit(
                "discovery.hypothesis.created",
                payload={
                    "hypothesis_id": hypothesis.hypothesis_id,
                    "statement": hypothesis.statement,
                    "confidence": float(hypothesis.confidence),
                    "source": "llm",
                },
            )

        hypotheses.sort(key=lambda h: h.confidence, reverse=True)
        return hypotheses

    @staticmethod
    def _build_prompt(hypothesis_input: HypothesisInput) -> str:
        """Build a prompt from patterns, context, and past findings."""
        parts: list[str] = []

        if hypothesis_input.context:
            parts.append(f"Domain context: {hypothesis_input.context}")

        if hypothesis_input.context_findings:
            parts.append(f"Past findings ({len(hypothesis_input.context_findings)}):")
            for i, f in enumerate(hypothesis_input.context_findings, 1):
                desc = (
                    f.get("description")
                    or f.get("statement")
                    or f.get("finding_id", f"finding-{i}")
                )
                parts.append(f"  [{i}] {desc}")
            parts.append("Build on these past findings; do not re-propose already-known results.")
            parts.append("")

        parts.append(f"Number of patterns discovered: {len(hypothesis_input.patterns)}")
        parts.append("")

        for i, pattern in enumerate(hypothesis_input.patterns, 1):
            parts.append(f"Pattern {i}:")
            parts.append(f"  Type: {pattern.pattern_type}")
            parts.append(f"  Description: {pattern.description}")
            parts.append(f"  Confidence: {pattern.confidence:.3f}")
            parts.append(f"  Evidence: {json.dumps(pattern.evidence, default=str)}")
            parts.append("")

        if hypothesis_input.constraints:
            parts.append("Constraints:")
            for c in hypothesis_input.constraints:
                parts.append(f"  - {c}")
            parts.append("")

        parts.append(
            "Generate testable hypotheses based on these patterns. "
            "For each hypothesis provide: a clear statement, whether it is testable, "
            "a confidence score (0-1), a list of required experiments, "
            "and a resource estimate."
        )

        return "\n".join(parts)
