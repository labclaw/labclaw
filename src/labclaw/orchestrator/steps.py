"""Scientific method steps — protocol, context, and 7 concrete implementations.

Spec: docs/specs/L3-discovery.md
Design doc: section 5.3 (Discovery Loop)

Each step maps to one phase of the scientific method:
OBSERVE -> ASK -> HYPOTHESIZE -> PREDICT -> EXPERIMENT -> ANALYZE -> CONCLUDE
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums & models
# ---------------------------------------------------------------------------


def _uuid() -> str:
    return str(uuid.uuid4())


class StepName(StrEnum):
    OBSERVE = "observe"
    ASK = "ask"
    HYPOTHESIZE = "hypothesize"
    PREDICT = "predict"
    EXPERIMENT = "experiment"
    ANALYZE = "analyze"
    CONCLUDE = "conclude"


class StepContext(BaseModel):
    """Passed through the pipeline, accumulating results."""

    data_rows: list[dict[str, Any]] = Field(default_factory=list)
    patterns: list[Any] = Field(default_factory=list)
    hypotheses: list[Any] = Field(default_factory=list)
    predictions: dict[str, Any] = Field(default_factory=dict)
    proposals: list[Any] = Field(default_factory=list)
    analysis_results: dict[str, Any] = Field(default_factory=dict)
    findings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    cycle_id: str = ""


class StepResult(BaseModel):
    step: StepName
    success: bool
    skipped: bool = False
    skip_reason: str = ""
    context: StepContext
    duration_seconds: float = 0.0


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class ScientificStep(Protocol):
    name: StepName

    async def run(self, context: StepContext) -> StepResult: ...


# ---------------------------------------------------------------------------
# Step implementations
# ---------------------------------------------------------------------------


class ObserveStep:
    """Takes data_rows from context. If empty, skips. Runs basic QC."""

    name = StepName.OBSERVE

    async def run(self, context: StepContext) -> StepResult:
        t0 = time.monotonic()
        try:
            if not context.data_rows:
                return StepResult(
                    step=self.name,
                    success=True,
                    skipped=True,
                    skip_reason="No data rows provided",
                    context=context,
                    duration_seconds=time.monotonic() - t0,
                )

            rows = context.data_rows
            row_count = len(rows)
            all_keys: set[str] = set()
            for row in rows:
                all_keys.update(row.keys())

            null_counts: dict[str, int] = {}
            for key in sorted(all_keys):
                nulls = sum(1 for row in rows if row.get(key) is None)
                if nulls > 0:
                    null_counts[key] = nulls

            numeric_cols: list[str] = []
            for key in sorted(all_keys):
                numeric_count = sum(
                    1 for row in rows[:5]
                    if key in row
                    and isinstance(row[key], (int, float))
                    and not isinstance(row[key], bool)
                )
                if numeric_count > len(rows[:5]) / 2:
                    numeric_cols.append(key)

            ctx = context.model_copy(
                update={
                    "metadata": {
                        **context.metadata,
                        "data_stats": {
                            "row_count": row_count,
                            "columns": sorted(all_keys),
                            "numeric_columns": numeric_cols,
                            "null_counts": null_counts,
                        },
                    },
                }
            )

            logger.info(
                "ObserveStep: %d rows, %d columns, %d numeric",
                row_count, len(all_keys), len(numeric_cols),
            )
            return StepResult(
                step=self.name,
                success=True,
                context=ctx,
                duration_seconds=time.monotonic() - t0,
            )
        except Exception:
            logger.exception("ObserveStep failed")
            return StepResult(
                step=self.name,
                success=False,
                context=context,
                duration_seconds=time.monotonic() - t0,
            )


class AskStep:
    """Uses PatternMiner to mine patterns from data_rows. Skips if < 10 rows."""

    name = StepName.ASK

    async def run(self, context: StepContext) -> StepResult:
        t0 = time.monotonic()
        try:
            if len(context.data_rows) < 10:
                return StepResult(
                    step=self.name,
                    success=True,
                    skipped=True,
                    skip_reason=f"Too few rows ({len(context.data_rows)} < 10)",
                    context=context,
                    duration_seconds=time.monotonic() - t0,
                )

            from labclaw.discovery.mining import MiningConfig, PatternMiner

            miner = PatternMiner()
            result = miner.mine(context.data_rows, MiningConfig())

            ctx = context.model_copy(
                update={"patterns": result.patterns}
            )

            logger.info("AskStep: found %d patterns", len(result.patterns))
            return StepResult(
                step=self.name,
                success=True,
                context=ctx,
                duration_seconds=time.monotonic() - t0,
            )
        except Exception:
            logger.exception("AskStep failed")
            return StepResult(
                step=self.name,
                success=False,
                context=context,
                duration_seconds=time.monotonic() - t0,
            )


class HypothesizeStep:
    """Uses HypothesisGenerator (or LLMHypothesisGenerator if available).

    Skips if no patterns.
    """

    name = StepName.HYPOTHESIZE

    def __init__(self, llm_provider: Any | None = None) -> None:
        self._llm_provider = llm_provider

    async def run(self, context: StepContext) -> StepResult:
        t0 = time.monotonic()
        try:
            if not context.patterns:
                return StepResult(
                    step=self.name,
                    success=True,
                    skipped=True,
                    skip_reason="No patterns to generate hypotheses from",
                    context=context,
                    duration_seconds=time.monotonic() - t0,
                )

            from labclaw.discovery.hypothesis import (
                HypothesisGenerator,
                HypothesisInput,
            )

            generator: Any = HypothesisGenerator()

            # Use LLM-backed generator if provider is available
            if self._llm_provider is not None:
                try:
                    from labclaw.discovery.hypothesis import (
                        LLMHypothesisGenerator,  # type: ignore[attr-error]
                    )
                    generator = LLMHypothesisGenerator(llm=self._llm_provider)
                except (ImportError, AttributeError):
                    pass  # Fall back to template-based generator

            hyp_input = HypothesisInput(patterns=context.patterns)
            hypotheses = generator.generate(hyp_input)

            ctx = context.model_copy(
                update={"hypotheses": hypotheses}
            )

            logger.info("HypothesizeStep: generated %d hypotheses", len(hypotheses))
            return StepResult(
                step=self.name,
                success=True,
                context=ctx,
                duration_seconds=time.monotonic() - t0,
            )
        except Exception:
            logger.exception("HypothesizeStep failed")
            return StepResult(
                step=self.name,
                success=False,
                context=context,
                duration_seconds=time.monotonic() - t0,
            )


class PredictStep:
    """Uses PredictiveModel to forecast. Skips if no numeric data."""

    name = StepName.PREDICT

    async def run(self, context: StepContext) -> StepResult:
        t0 = time.monotonic()
        try:
            # Detect numeric columns
            data = context.data_rows
            if not data:
                return StepResult(
                    step=self.name,
                    success=True,
                    skipped=True,
                    skip_reason="No data rows",
                    context=context,
                    duration_seconds=time.monotonic() - t0,
                )

            numeric_cols = context.metadata.get("data_stats", {}).get(
                "numeric_columns", []
            )
            if len(numeric_cols) < 2:
                return StepResult(
                    step=self.name,
                    success=True,
                    skipped=True,
                    skip_reason="Need at least 2 numeric columns for prediction",
                    context=context,
                    duration_seconds=time.monotonic() - t0,
                )

            from labclaw.discovery.modeling import ModelConfig, PredictiveModel

            # Use last numeric column as target, rest as features
            target_col = numeric_cols[-1]
            feature_cols = numeric_cols[:-1]

            model = PredictiveModel()
            config = ModelConfig(
                target_column=target_col,
                feature_columns=feature_cols,
            )
            train_result = model.train(data, config)

            predictions_dict: dict[str, Any] = {
                "model_id": train_result.model_id,
                "r_squared": train_result.r_squared,
                "cv_score": train_result.cv_score,
                "target_column": target_col,
                "feature_columns": feature_cols,
                "n_samples": train_result.n_samples,
                "feature_importances": [
                    {"feature": fi.feature, "importance": fi.importance, "rank": fi.rank}
                    for fi in train_result.feature_importances
                ],
            }

            ctx = context.model_copy(
                update={"predictions": predictions_dict}
            )

            logger.info(
                "PredictStep: R^2=%.3f, target=%s", train_result.r_squared, target_col
            )
            return StepResult(
                step=self.name,
                success=True,
                context=ctx,
                duration_seconds=time.monotonic() - t0,
            )
        except Exception:
            logger.exception("PredictStep failed")
            return StepResult(
                step=self.name,
                success=False,
                context=context,
                duration_seconds=time.monotonic() - t0,
            )


class ExperimentStep:
    """Wraps BayesianOptimizer — proposes next experiment parameters (read-only for v0.0.2)."""

    name = StepName.EXPERIMENT

    async def run(self, context: StepContext) -> StepResult:
        t0 = time.monotonic()
        try:
            numeric_cols = context.metadata.get("data_stats", {}).get(
                "numeric_columns", []
            )
            if not numeric_cols:
                return StepResult(
                    step=self.name,
                    success=True,
                    skipped=True,
                    skip_reason="No numeric columns to optimize over",
                    context=context,
                    duration_seconds=time.monotonic() - t0,
                )

            from labclaw.optimization.optimizer import (
                BayesianOptimizer,
                ParameterDimension,
                ParameterSpace,
            )

            # Build parameter space from data ranges
            data = context.data_rows
            dimensions: list[ParameterDimension] = []
            for col in numeric_cols:
                values = [
                    float(row[col]) for row in data
                    if col in row
                    and isinstance(row[col], (int, float))
                    and not isinstance(row[col], bool)
                ]
                if not values:
                    continue
                lo, hi = min(values), max(values)
                if lo == hi:
                    hi = lo + 1.0
                dimensions.append(ParameterDimension(name=col, low=lo, high=hi))

            if not dimensions:
                return StepResult(
                    step=self.name,
                    success=True,
                    skipped=True,
                    skip_reason="Could not build parameter space from data",
                    context=context,
                    duration_seconds=time.monotonic() - t0,
                )

            space = ParameterSpace(name="auto", dimensions=dimensions)
            optimizer = BayesianOptimizer(space)
            proposals = optimizer.suggest(n=1)

            ctx = context.model_copy(
                update={
                    "proposals": [
                        {
                            "proposal_id": p.proposal_id,
                            "parameters": p.parameters,
                            "iteration": p.iteration,
                        }
                        for p in proposals
                    ]
                }
            )

            logger.info("ExperimentStep: proposed %d experiments", len(proposals))
            return StepResult(
                step=self.name,
                success=True,
                context=ctx,
                duration_seconds=time.monotonic() - t0,
            )
        except Exception:
            logger.exception("ExperimentStep failed")
            return StepResult(
                step=self.name,
                success=False,
                context=context,
                duration_seconds=time.monotonic() - t0,
            )


class AnalyzeStep:
    """Uses StatisticalValidator to validate patterns."""

    name = StepName.ANALYZE

    async def run(self, context: StepContext) -> StepResult:
        t0 = time.monotonic()
        try:
            if not context.patterns:
                return StepResult(
                    step=self.name,
                    success=True,
                    skipped=True,
                    skip_reason="No patterns to validate",
                    context=context,
                    duration_seconds=time.monotonic() - t0,
                )

            from labclaw.validation.statistics import StatisticalValidator

            validator = StatisticalValidator()
            analysis: dict[str, Any] = {"validated_patterns": []}

            data = context.data_rows
            for pattern in context.patterns:
                pattern_info: dict[str, Any] = {
                    "pattern_id": getattr(pattern, "pattern_id", str(pattern)),
                    "pattern_type": getattr(pattern, "pattern_type", "unknown"),
                }

                evidence = getattr(pattern, "evidence", {})

                # For correlation patterns, validate with permutation test
                if getattr(pattern, "pattern_type", None) == "correlation":
                    col_a = evidence.get("col_a")
                    col_b = evidence.get("col_b")
                    if col_a and col_b:
                        vals_a = [
                            float(row[col_a]) for row in data
                            if col_a in row and col_b in row
                        ]
                        vals_b = [
                            float(row[col_b]) for row in data
                            if col_a in row and col_b in row
                        ]
                        if len(vals_a) >= 5 and len(vals_b) >= 5:
                            test_result = validator.run_test(
                                "permutation", vals_a, vals_b,
                            )
                            pattern_info["test"] = {
                                "test_name": test_result.test_name,
                                "p_value": test_result.p_value,
                                "significant": test_result.significant,
                            }

                analysis["validated_patterns"].append(pattern_info)

            ctx = context.model_copy(
                update={"analysis_results": analysis}
            )

            logger.info(
                "AnalyzeStep: validated %d patterns",
                len(analysis["validated_patterns"]),
            )
            return StepResult(
                step=self.name,
                success=True,
                context=ctx,
                duration_seconds=time.monotonic() - t0,
            )
        except Exception:
            logger.exception("AnalyzeStep failed")
            return StepResult(
                step=self.name,
                success=False,
                context=context,
                duration_seconds=time.monotonic() - t0,
            )


class ConcludeStep:
    """Generates finding summaries. Logs to Tier A memory."""

    name = StepName.CONCLUDE

    def __init__(self, memory_root: Path | None = None, entity_id: str = "lab") -> None:
        self._memory_root = memory_root
        self._entity_id = entity_id

    async def run(self, context: StepContext) -> StepResult:
        t0 = time.monotonic()
        try:
            findings: list[str] = []

            # Summarize patterns
            n_patterns = len(context.patterns)
            if n_patterns > 0:
                findings.append(f"Discovered {n_patterns} pattern(s) in data.")

            # Summarize hypotheses
            n_hyp = len(context.hypotheses)
            if n_hyp > 0:
                findings.append(f"Generated {n_hyp} hypothesis/hypotheses.")

            # Summarize predictions
            if context.predictions:
                r2 = context.predictions.get("r_squared")
                target = context.predictions.get("target_column")
                if r2 is not None and target:
                    findings.append(
                        f"Predictive model for {target}: R^2={r2:.3f}."
                    )

            # Summarize proposals
            n_proposals = len(context.proposals)
            if n_proposals > 0:
                findings.append(f"Proposed {n_proposals} experiment(s) for next cycle.")

            # Summarize analysis
            validated = context.analysis_results.get("validated_patterns", [])
            if validated:
                sig_count = sum(
                    1 for v in validated
                    if v.get("test", {}).get("significant", False)
                )
                findings.append(
                    f"Statistical validation: {sig_count}/{len(validated)} "
                    f"patterns significant."
                )

            if not findings:
                findings.append("No notable findings in this cycle.")

            # Log to Tier A memory if root is set
            if self._memory_root is not None:
                try:
                    from labclaw.memory.markdown import MemoryEntry, TierABackend

                    backend = TierABackend(self._memory_root)
                    entry = MemoryEntry(
                        timestamp=datetime.now(UTC),
                        category="cycle_conclusion",
                        detail="\n".join(findings),
                    )
                    backend.append_memory(self._entity_id, entry)
                except Exception:
                    logger.exception("Failed to log findings to Tier A memory")

            ctx = context.model_copy(update={"findings": findings})

            logger.info("ConcludeStep: %d findings", len(findings))
            return StepResult(
                step=self.name,
                success=True,
                context=ctx,
                duration_seconds=time.monotonic() - t0,
            )
        except Exception:
            logger.exception("ConcludeStep failed")
            return StepResult(
                step=self.name,
                success=False,
                context=context,
                duration_seconds=time.monotonic() - t0,
            )
