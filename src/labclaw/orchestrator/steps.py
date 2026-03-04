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


def _sync_llm_complete(provider: Any, prompt: str, system: str) -> str:
    """Call an async LLM provider from sync context. Handles event-loop bridging."""
    import asyncio

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            result = pool.submit(
                asyncio.run,
                provider.complete(prompt, system=system),
            ).result()
    else:
        result = asyncio.run(provider.complete(prompt, system=system))
    return str(result).strip()


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
    provenance_steps: list[dict[str, Any]] = Field(default_factory=list)


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
    """Takes data_rows from context. If empty, skips. Runs basic QC.

    When *sentinel* is provided, plugin sentinel rules are evaluated after
    basic QC.  Alerts are stored in ``context.metadata["sentinel_alerts"]``.
    """

    name = StepName.OBSERVE

    def __init__(self, sentinel: Any | None = None) -> None:
        self._sentinel = sentinel

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
                    1
                    for row in rows[:5]
                    if key in row
                    and isinstance(row[key], (int, float))
                    and not isinstance(row[key], bool)
                )
                if numeric_count > len(rows[:5]) / 2:
                    numeric_cols.append(key)

            prov_entry: dict[str, Any] = {
                "step": self.name.value,
                "node_id": str(uuid.uuid4()),
                "node_type": "observation",
                "inputs": [],
                "outputs": [f"{row_count} rows, {len(all_keys)} columns"],
                "timestamp": datetime.now(UTC).isoformat(),
            }
            # Sentinel checks: evaluate plugin rules against data quality metrics
            sentinel_alerts: list[dict[str, Any]] = []
            if self._sentinel is not None:
                try:
                    from labclaw.core.schemas import QualityMetric

                    metrics = [
                        QualityMetric(name="row_count", value=float(row_count)),
                        QualityMetric(
                            name="null_rate",
                            value=(
                                sum(null_counts.values()) / (row_count * len(all_keys))
                                if all_keys and row_count > 0
                                else 0.0
                            ),
                        ),
                        QualityMetric(name="numeric_column_count", value=float(len(numeric_cols))),
                    ]
                    for metric in metrics:
                        alerts = self._sentinel.check_metric(metric)
                        for alert in alerts:
                            sentinel_alerts.append(
                                {
                                    "rule": alert.rule_name,
                                    "metric": alert.metric.name,
                                    "value": alert.metric.value,
                                    "level": alert.level.value,
                                    "message": alert.message,
                                }
                            )
                    if sentinel_alerts:
                        logger.warning(
                            "ObserveStep: %d sentinel alerts raised", len(sentinel_alerts)
                        )
                except Exception:
                    logger.warning("ObserveStep: sentinel check failed")

            meta_update: dict[str, Any] = {
                **context.metadata,
                "data_stats": {
                    "row_count": row_count,
                    "columns": sorted(all_keys),
                    "numeric_columns": numeric_cols,
                    "null_counts": null_counts,
                },
            }
            if sentinel_alerts:
                meta_update["sentinel_alerts"] = sentinel_alerts

            ctx = context.model_copy(
                update={
                    "metadata": meta_update,
                    "provenance_steps": [*context.provenance_steps, prov_entry],
                }
            )

            logger.info(
                "ObserveStep: %d rows, %d columns, %d numeric",
                row_count,
                len(all_keys),
                len(numeric_cols),
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
    """Uses PatternMiner to mine patterns from data_rows.

    When *session_memory* is provided, known findings are used to
    deduplicate patterns via PatternDeduplicator.  Skips if < 10 rows.
    """

    name = StepName.ASK

    def __init__(self, session_memory: Any | None = None) -> None:
        self._session_memory = session_memory

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
            patterns = result.patterns

            # Deduplicate against known findings
            if self._session_memory is not None and patterns:
                try:
                    from labclaw.memory.dedup import PatternDeduplicator

                    known_findings = await self._session_memory.retrieve_findings()
                    dedup = PatternDeduplicator(known_findings)
                    original_count = len(patterns)
                    # Convert PatternRecord → dedup-compatible dicts
                    pattern_dicts = [
                        {
                            "column_a": getattr(p, "evidence", {}).get("col_a"),
                            "column_b": getattr(p, "evidence", {}).get("col_b"),
                            "pattern_type": getattr(p, "pattern_type", None),
                        }
                        for p in patterns
                    ]
                    unique_dicts = dedup.deduplicate(pattern_dicts)
                    # Map back to original PatternRecord objects
                    unique_set = {id(d) for d in unique_dicts}
                    patterns = [p for p, d in zip(patterns, pattern_dicts) if id(d) in unique_set]
                    deduped = original_count - len(patterns)
                    if deduped > 0:
                        logger.info("AskStep: deduplicated %d known patterns", deduped)
                except Exception:
                    logger.warning("AskStep: deduplication failed, keeping all patterns")

            prov_entry: dict[str, Any] = {
                "step": self.name.value,
                "node_id": str(uuid.uuid4()),
                "node_type": "pattern_mining",
                "inputs": [f"{len(context.data_rows)} rows"],
                "outputs": [f"{len(patterns)} patterns"],
                "timestamp": datetime.now(UTC).isoformat(),
            }
            ctx = context.model_copy(
                update={
                    "patterns": patterns,
                    "provenance_steps": [*context.provenance_steps, prov_entry],
                }
            )

            logger.info("AskStep: found %d patterns", len(patterns))
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

    When *session_memory* is provided, past findings are queried and fed
    into HypothesisInput.context_findings so the generator can build on them.
    Skips if no patterns.
    """

    name = StepName.HYPOTHESIZE

    def __init__(
        self,
        llm_provider: Any | None = None,
        max_llm_calls: int = 50,
        session_memory: Any | None = None,
        plugin_templates: list[dict] | None = None,
    ) -> None:
        self._llm_provider = llm_provider
        self._max_llm_calls = max_llm_calls
        self._session_memory = session_memory
        self._plugin_templates = plugin_templates or []

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

            generator: Any = HypothesisGenerator(
                plugin_templates=self._plugin_templates,
            )

            # Use LLM-backed generator if provider is available
            if self._llm_provider is not None:
                try:
                    from labclaw.discovery.hypothesis import (
                        LLMHypothesisGenerator,  # type: ignore[attr-error]
                    )

                    generator = LLMHypothesisGenerator(
                        llm=self._llm_provider, max_calls=self._max_llm_calls
                    )
                except (ImportError, AttributeError):
                    pass  # Fall back to template-based generator

            # Query past findings from session memory
            context_findings: list[dict] = []
            if self._session_memory is not None:
                try:
                    context_findings = await self._session_memory.retrieve_findings()
                except Exception:
                    logger.warning("HypothesizeStep: failed to retrieve past findings")

            hyp_input = HypothesisInput(
                patterns=context.patterns,
                context_findings=context_findings,
            )
            hypotheses = generator.generate(hyp_input)

            prov_entry: dict[str, Any] = {
                "step": self.name.value,
                "node_id": str(uuid.uuid4()),
                "node_type": "hypothesis_generation",
                "inputs": [f"{len(context.patterns)} patterns"],
                "outputs": [f"{len(hypotheses)} hypotheses"],
                "timestamp": datetime.now(UTC).isoformat(),
            }
            ctx = context.model_copy(
                update={
                    "hypotheses": hypotheses,
                    "provenance_steps": [*context.provenance_steps, prov_entry],
                }
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

            numeric_cols = context.metadata.get("data_stats", {}).get("numeric_columns", [])
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

            prov_entry: dict[str, Any] = {
                "step": self.name.value,
                "node_id": str(uuid.uuid4()),
                "node_type": "predictive_model",
                "inputs": [f"target={target_col}", f"features={feature_cols}"],
                "outputs": [f"r_squared={train_result.r_squared:.3f}"],
                "timestamp": datetime.now(UTC).isoformat(),
            }
            ctx = context.model_copy(
                update={
                    "predictions": predictions_dict,
                    "provenance_steps": [*context.provenance_steps, prov_entry],
                }
            )

            logger.info("PredictStep: R^2=%.3f, target=%s", train_result.r_squared, target_col)
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
    """Wraps BayesianOptimizer — proposes next experiment parameters.

    When *llm_provider* is supplied, Bayesian proposals are evaluated by the
    LLM against domain knowledge and past findings.  The LLM can annotate
    proposals with scientific rationale.  Bayesian math is never replaced.
    """

    name = StepName.EXPERIMENT

    def __init__(self, llm_provider: Any | None = None, max_llm_calls: int = 50) -> None:
        self._llm_provider = llm_provider
        self._max_llm_calls = max_llm_calls
        self._llm_call_count = 0

    async def run(self, context: StepContext) -> StepResult:
        t0 = time.monotonic()
        try:
            numeric_cols = context.metadata.get("data_stats", {}).get("numeric_columns", [])
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
                    float(row[col])
                    for row in data
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

            # LLM evaluation: annotate proposals with scientific rationale
            proposal_dicts = [
                {
                    "proposal_id": p.proposal_id,
                    "parameters": p.parameters,
                    "iteration": p.iteration,
                }
                for p in proposals
            ]
            llm_rationale = self._evaluate_with_llm(proposal_dicts, context)
            if llm_rationale:
                for pd in proposal_dicts:
                    pd["llm_rationale"] = llm_rationale

            prov_entry: dict[str, Any] = {
                "step": self.name.value,
                "node_id": str(uuid.uuid4()),
                "node_type": "experiment_proposal",
                "inputs": [f"space={space.name}", f"dims={len(dimensions)}"],
                "outputs": [f"{len(proposals)} proposals"],
                "timestamp": datetime.now(UTC).isoformat(),
            }
            ctx = context.model_copy(
                update={
                    "proposals": proposal_dicts,
                    "provenance_steps": [*context.provenance_steps, prov_entry],
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

    def _evaluate_with_llm(self, proposals: list[dict[str, Any]], context: StepContext) -> str:
        """Ask LLM to evaluate Bayesian proposals. Returns rationale or empty string."""
        if self._llm_provider is None:
            return ""
        if self._llm_call_count >= self._max_llm_calls:
            logger.info(
                "ExperimentStep LLM cost guard (calls=%d >= max=%d): skipping evaluation",
                self._llm_call_count,
                self._max_llm_calls,
            )
            return ""

        self._llm_call_count += 1

        import json as _json

        findings_ctx = "\n".join(f"- {f}" for f in context.findings) if context.findings else "None"
        hypotheses_ctx = (
            "\n".join(f"- {getattr(h, 'statement', str(h))}" for h in context.hypotheses[:5])
            if context.hypotheses
            else "None"
        )
        proposals_text = _json.dumps(proposals, default=str, indent=2)

        prompt = (
            "Evaluate the following experiment proposals from a Bayesian optimizer.\n\n"
            f"Current hypotheses:\n{hypotheses_ctx}\n\n"
            f"Current findings:\n{findings_ctx}\n\n"
            f"Proposals:\n{proposals_text}\n\n"
            "Provide a brief scientific rationale (2-3 sentences) for whether these "
            "proposals are well-targeted given the hypotheses and findings."
        )
        system = (
            "You are a scientific advisor evaluating experiment proposals. Be concise and specific."
        )

        try:
            rationale = _sync_llm_complete(self._llm_provider, prompt, system)[:1000]
            logger.info("ExperimentStep: LLM rationale produced %d chars", len(rationale))
            return rationale
        except Exception:
            logger.warning("ExperimentStep: LLM evaluation failed, using raw proposals")
            return ""


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
                            float(row[col_a]) for row in data if col_a in row and col_b in row
                        ]
                        vals_b = [
                            float(row[col_b]) for row in data if col_a in row and col_b in row
                        ]
                        if len(vals_a) >= 5 and len(vals_b) >= 5:
                            test_result = validator.run_test(
                                "permutation",
                                vals_a,
                                vals_b,
                            )
                            pattern_info["test"] = {
                                "test_name": test_result.test_name,
                                "p_value": test_result.p_value,
                                "significant": test_result.significant,
                            }

                analysis["validated_patterns"].append(pattern_info)

            prov_entry: dict[str, Any] = {
                "step": self.name.value,
                "node_id": str(uuid.uuid4()),
                "node_type": "statistical_analysis",
                "inputs": [f"{len(context.patterns)} patterns"],
                "outputs": [f"{len(analysis['validated_patterns'])} validated"],
                "timestamp": datetime.now(UTC).isoformat(),
            }
            ctx = context.model_copy(
                update={
                    "analysis_results": analysis,
                    "provenance_steps": [*context.provenance_steps, prov_entry],
                }
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
    """Generates finding summaries. Logs to Tier A memory.

    When *llm_provider* is supplied, deterministic template findings are first
    produced then passed to the LLM for a richer natural-language synthesis.
    If the LLM call fails or cost-guard fires, template findings are used as-is.
    """

    name = StepName.CONCLUDE

    def __init__(
        self,
        memory_root: Path | None = None,
        entity_id: str = "lab",
        llm_provider: Any | None = None,
        max_llm_calls: int = 50,
    ) -> None:
        self._memory_root = memory_root
        self._entity_id = entity_id
        self._llm_provider = llm_provider
        self._max_llm_calls = max_llm_calls
        self._llm_call_count = 0

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
                    findings.append(f"Predictive model for {target}: R^2={r2:.3f}.")

            # Summarize proposals
            n_proposals = len(context.proposals)
            if n_proposals > 0:
                findings.append(f"Proposed {n_proposals} experiment(s) for next cycle.")

            # Summarize analysis
            validated = context.analysis_results.get("validated_patterns", [])
            if validated:
                sig_count = sum(1 for v in validated if v.get("test", {}).get("significant", False))
                findings.append(
                    f"Statistical validation: {sig_count}/{len(validated)} patterns significant."
                )
                # Write per-pattern p-values for C1 DISCOVER traceability
                for v in validated:
                    test = v.get("test", {})
                    if test:
                        p_val = test.get("p_value")
                        sig = test.get("significant", False)
                        pid = v.get("pattern_id", "?")
                        if p_val is not None:
                            findings.append(
                                f"  Pattern {pid}: p={p_val:.4f}, significant={sig} (alpha=0.05)."
                            )

            if not findings:
                findings.append("No notable findings in this cycle.")

            # LLM synthesis: enrich template findings with natural language
            llm_synthesis = self._synthesize_with_llm(findings, context)
            if llm_synthesis:
                findings.append(f"LLM synthesis: {llm_synthesis}")

            # Build a ProvenanceChain for each finding
            from labclaw.validation.provenance import ProvenanceTracker
            from labclaw.validation.statistics import ProvenanceStep

            tracker = ProvenanceTracker()
            finding_chains: list[dict[str, Any]] = []
            for finding_text in findings:
                finding_id = str(uuid.uuid4())
                prov_steps = [
                    ProvenanceStep(
                        node_id=entry["node_id"],
                        node_type=entry["node_type"],
                        description=f"step={entry['step']} outputs={entry.get('outputs', [])}",
                        timestamp=datetime.fromisoformat(entry["timestamp"]),
                    )
                    for entry in context.provenance_steps
                ]
                # Always add a conclude step entry
                prov_steps.append(
                    ProvenanceStep(
                        node_id=str(uuid.uuid4()),
                        node_type="conclusion",
                        description=finding_text,
                    )
                )
                chain = tracker.build_chain(finding_id, prov_steps)
                finding_chains.append(chain.model_dump(mode="json"))

            conclude_prov: dict[str, Any] = {
                "step": self.name.value,
                "node_id": str(uuid.uuid4()),
                "node_type": "conclusion",
                "inputs": [f"{len(context.patterns)} patterns", f"{len(context.hypotheses)} hyp"],
                "outputs": [f"{len(findings)} findings"],
                "timestamp": datetime.now(UTC).isoformat(),
            }

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

            ctx = context.model_copy(
                update={
                    "findings": findings,
                    "provenance_steps": [*context.provenance_steps, conclude_prov],
                    "metadata": {
                        **context.metadata,
                        "finding_chains": finding_chains,
                    },
                }
            )

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

    def _synthesize_with_llm(self, findings: list[str], context: StepContext) -> str:
        """Call LLM to synthesize template findings into natural language.

        Returns empty string if LLM is unavailable, cost-guard fires, or call fails.
        """
        if self._llm_provider is None:
            return ""
        if self._llm_call_count >= self._max_llm_calls:
            logger.info(
                "ConcludeStep LLM cost guard (calls=%d >= max=%d): skipping synthesis",
                self._llm_call_count,
                self._max_llm_calls,
            )
            return ""

        self._llm_call_count += 1

        prompt = (
            "Synthesize the following scientific findings from one discovery cycle "
            "into a brief, coherent narrative paragraph (3-5 sentences). "
            "Be specific and reference the data.\n\n"
            "Findings:\n" + "\n".join(f"- {f}" for f in findings)
        )
        system = (
            "You are a scientific assistant summarizing discovery cycle results. "
            "Write clear, concise conclusions grounded in the evidence."
        )

        try:
            synthesis = _sync_llm_complete(self._llm_provider, prompt, system)[:2000]
            logger.info("ConcludeStep: LLM synthesis produced %d chars", len(synthesis))
            return synthesis
        except Exception:
            logger.warning("ConcludeStep: LLM synthesis failed, using template findings only")
            return ""
