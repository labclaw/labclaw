"""Tests for the scientific method orchestrator — steps.py and loop.py."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from labclaw.core.events import event_registry
from labclaw.orchestrator.loop import CycleResult, ScientificLoop
from labclaw.orchestrator.steps import (
    AnalyzeStep,
    AskStep,
    ConcludeStep,
    ExperimentStep,
    HypothesizeStep,
    ObserveStep,
    PredictStep,
    StepContext,
    StepName,
    StepResult,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _numeric_rows(n: int = 20) -> list[dict[str, Any]]:
    return [{"x": float(i), "y": float(i * 2 + 1), "label": f"s{i}"} for i in range(n)]


def _non_numeric_rows(n: int = 5) -> list[dict[str, Any]]:
    return [{"name": f"item_{i}", "status": "ok"} for i in range(n)]


# ---------------------------------------------------------------------------
# ObserveStep
# ---------------------------------------------------------------------------


class TestObserveStep:
    @pytest.mark.asyncio
    async def test_empty_data_skipped(self):
        ctx = StepContext(data_rows=[])
        result = await ObserveStep().run(ctx)
        assert result.skipped is True
        assert result.success is True
        assert "No data" in result.skip_reason

    @pytest.mark.asyncio
    async def test_valid_data_computes_stats(self):
        rows = _numeric_rows(10)
        ctx = StepContext(data_rows=rows)
        result = await ObserveStep().run(ctx)
        assert result.success is True
        assert result.skipped is False
        stats = result.context.metadata["data_stats"]
        assert stats["row_count"] == 10
        assert "x" in stats["numeric_columns"]
        assert "y" in stats["numeric_columns"]
        assert "label" not in stats["numeric_columns"]

    @pytest.mark.asyncio
    async def test_null_counts(self):
        rows = [{"x": 1, "y": None}, {"x": 2, "y": 3}]
        ctx = StepContext(data_rows=rows)
        result = await ObserveStep().run(ctx)
        assert result.success is True
        stats = result.context.metadata["data_stats"]
        assert stats["null_counts"]["y"] == 1

    @pytest.mark.asyncio
    async def test_non_numeric_data(self):
        rows = _non_numeric_rows(5)
        ctx = StepContext(data_rows=rows)
        result = await ObserveStep().run(ctx)
        assert result.success is True
        stats = result.context.metadata["data_stats"]
        assert stats["numeric_columns"] == []


# ---------------------------------------------------------------------------
# AskStep
# ---------------------------------------------------------------------------


class TestAskStep:
    @pytest.mark.asyncio
    async def test_too_few_rows_skipped(self):
        ctx = StepContext(data_rows=_numeric_rows(5))
        result = await AskStep().run(ctx)
        assert result.skipped is True
        assert "Too few rows" in result.skip_reason

    @pytest.mark.asyncio
    async def test_sufficient_rows_calls_miner(self):
        mock_result = MagicMock()
        mock_result.patterns = ["p1", "p2"]
        with (
            patch("labclaw.discovery.mining.PatternMiner") as mock_miner_cls,
            patch("labclaw.discovery.mining.MiningConfig"),
        ):
            mock_miner_cls.return_value.mine.return_value = mock_result
            ctx = StepContext(data_rows=_numeric_rows(15))
            result = await AskStep().run(ctx)
            assert result.success is True
            assert result.context.patterns == ["p1", "p2"]
            mock_miner_cls.return_value.mine.assert_called_once()

    @pytest.mark.asyncio
    async def test_exception_handling(self):
        with patch(
            "labclaw.discovery.mining.PatternMiner",
            side_effect=RuntimeError("boom"),
        ):
            ctx = StepContext(data_rows=_numeric_rows(15))
            result = await AskStep().run(ctx)
            assert result.success is False


# ---------------------------------------------------------------------------
# HypothesizeStep
# ---------------------------------------------------------------------------


class TestHypothesizeStep:
    @pytest.mark.asyncio
    async def test_no_patterns_skips(self):
        ctx = StepContext(patterns=[])
        result = await HypothesizeStep().run(ctx)
        assert result.skipped is True
        assert "No patterns" in result.skip_reason

    @pytest.mark.asyncio
    async def test_with_patterns_calls_generator(self):
        mock_gen = MagicMock()
        mock_gen.generate.return_value = ["hyp1"]
        with (
            patch(
                "labclaw.discovery.hypothesis.HypothesisGenerator",
                return_value=mock_gen,
            ),
            patch(
                "labclaw.discovery.hypothesis.HypothesisInput",
            ),
        ):
            ctx = StepContext(patterns=["p1"])
            result = await HypothesizeStep().run(ctx)
            assert result.success is True
            assert result.context.hypotheses == ["hyp1"]

    @pytest.mark.asyncio
    async def test_with_llm_provider_tries_llm(self):
        mock_llm = MagicMock()
        mock_llm_gen = MagicMock()
        mock_llm_gen.generate.return_value = ["llm_hyp"]
        with (
            patch(
                "labclaw.discovery.hypothesis.HypothesisGenerator",
            ),
            patch(
                "labclaw.discovery.hypothesis.HypothesisInput",
            ),
            patch(
                "labclaw.discovery.hypothesis.LLMHypothesisGenerator",
                return_value=mock_llm_gen,
            ),
        ):
            step = HypothesizeStep(llm_provider=mock_llm)
            ctx = StepContext(patterns=["p1"])
            result = await step.run(ctx)
            assert result.success is True
            assert result.context.hypotheses == ["llm_hyp"]

    @pytest.mark.asyncio
    async def test_llm_import_falls_back(self):
        """When LLMHypothesisGenerator import fails, falls back to template generator."""
        mock_llm = MagicMock()
        mock_template_gen = MagicMock()
        mock_template_gen.generate.return_value = ["fallback_hyp"]

        with (
            patch(
                "labclaw.discovery.hypothesis.HypothesisGenerator",
                return_value=mock_template_gen,
            ),
            patch(
                "labclaw.discovery.hypothesis.HypothesisInput",
            ),
            patch(
                "labclaw.discovery.hypothesis.LLMHypothesisGenerator",
                side_effect=ImportError("no LLM"),
            ),
        ):
            step = HypothesizeStep(llm_provider=mock_llm)
            ctx = StepContext(patterns=["p1"])
            result = await step.run(ctx)
            assert result.success is True
            # Should have used the template generator as fallback
            assert result.context.hypotheses == ["fallback_hyp"]


# ---------------------------------------------------------------------------
# PredictStep
# ---------------------------------------------------------------------------


class TestPredictStep:
    @pytest.mark.asyncio
    async def test_no_data_skips(self):
        ctx = StepContext(data_rows=[])
        result = await PredictStep().run(ctx)
        assert result.skipped is True
        assert "No data" in result.skip_reason

    @pytest.mark.asyncio
    async def test_fewer_than_2_numeric_cols_skips(self):
        rows = [{"x": 1.0, "label": "a"} for _ in range(5)]
        ctx = StepContext(
            data_rows=rows,
            metadata={"data_stats": {"numeric_columns": ["x"]}},
        )
        result = await PredictStep().run(ctx)
        assert result.skipped is True
        assert "2 numeric columns" in result.skip_reason

    @pytest.mark.asyncio
    async def test_valid_data_trains_model(self):
        mock_train = MagicMock()
        mock_train.model_id = "m1"
        mock_train.r_squared = 0.95
        mock_train.cv_score = 0.90
        mock_train.n_samples = 20
        mock_train.feature_importances = []

        with (
            patch("labclaw.discovery.modeling.PredictiveModel") as mock_model_cls,
            patch("labclaw.discovery.modeling.ModelConfig"),
        ):
            mock_model_cls.return_value.train.return_value = mock_train
            rows = _numeric_rows(20)
            ctx = StepContext(
                data_rows=rows,
                metadata={"data_stats": {"numeric_columns": ["x", "y"]}},
            )
            result = await PredictStep().run(ctx)
            assert result.success is True
            assert result.context.predictions["r_squared"] == 0.95
            assert result.context.predictions["model_id"] == "m1"


# ---------------------------------------------------------------------------
# ExperimentStep
# ---------------------------------------------------------------------------


class TestExperimentStep:
    @pytest.mark.asyncio
    async def test_no_numeric_cols_skips(self):
        ctx = StepContext(
            data_rows=[{"a": "text"}],
            metadata={"data_stats": {"numeric_columns": []}},
        )
        result = await ExperimentStep().run(ctx)
        assert result.skipped is True

    @pytest.mark.asyncio
    async def test_valid_data_proposes(self):
        mock_proposal = MagicMock()
        mock_proposal.proposal_id = "prop1"
        mock_proposal.parameters = {"x": 5.0}
        mock_proposal.iteration = 1

        with (
            patch("labclaw.optimization.optimizer.BayesianOptimizer") as mock_opt_cls,
            patch("labclaw.optimization.optimizer.ParameterDimension"),
            patch("labclaw.optimization.optimizer.ParameterSpace"),
        ):
            mock_opt_cls.return_value.suggest.return_value = [mock_proposal]
            rows = _numeric_rows(10)
            ctx = StepContext(
                data_rows=rows,
                metadata={"data_stats": {"numeric_columns": ["x", "y"]}},
            )
            result = await ExperimentStep().run(ctx)
            assert result.success is True
            assert len(result.context.proposals) == 1
            assert result.context.proposals[0]["proposal_id"] == "prop1"

    @pytest.mark.asyncio
    async def test_equal_lo_hi_range(self):
        """When all values are the same, lo==hi, code adjusts hi = lo+1."""
        rows = [{"x": 5.0, "y": 5.0} for _ in range(10)]
        mock_proposal = MagicMock()
        mock_proposal.proposal_id = "p2"
        mock_proposal.parameters = {"x": 5.5}
        mock_proposal.iteration = 1

        with (
            patch("labclaw.optimization.optimizer.BayesianOptimizer") as mock_opt_cls,
            patch("labclaw.optimization.optimizer.ParameterDimension") as mock_dim_cls,
            patch("labclaw.optimization.optimizer.ParameterSpace"),
        ):
            mock_opt_cls.return_value.suggest.return_value = [mock_proposal]
            ctx = StepContext(
                data_rows=rows,
                metadata={"data_stats": {"numeric_columns": ["x", "y"]}},
            )
            result = await ExperimentStep().run(ctx)
            assert result.success is True
            # Verify ParameterDimension was called with adjusted hi
            calls = mock_dim_cls.call_args_list
            for call in calls:
                assert call.kwargs["high"] == 6.0  # lo=5 + 1


# ---------------------------------------------------------------------------
# AnalyzeStep
# ---------------------------------------------------------------------------


class TestAnalyzeStep:
    @pytest.mark.asyncio
    async def test_no_patterns_skips(self):
        ctx = StepContext(patterns=[])
        result = await AnalyzeStep().run(ctx)
        assert result.skipped is True
        assert "No patterns" in result.skip_reason

    @pytest.mark.asyncio
    async def test_correlation_pattern_validates(self):
        pattern = MagicMock()
        pattern.pattern_id = "pat1"
        pattern.pattern_type = "correlation"
        pattern.evidence = {"col_a": "x", "col_b": "y"}

        mock_test_result = MagicMock()
        mock_test_result.test_name = "permutation"
        mock_test_result.p_value = 0.01
        mock_test_result.significant = True

        with patch("labclaw.validation.statistics.StatisticalValidator") as mock_validator_cls:
            mock_validator_cls.return_value.run_test.return_value = mock_test_result
            rows = [{"x": float(i), "y": float(i * 2)} for i in range(10)]
            ctx = StepContext(data_rows=rows, patterns=[pattern])
            result = await AnalyzeStep().run(ctx)
            assert result.success is True
            validated = result.context.analysis_results["validated_patterns"]
            assert len(validated) == 1
            assert validated[0]["test"]["significant"] is True

    @pytest.mark.asyncio
    async def test_missing_evidence_fields(self):
        """Pattern with correlation type but missing col_a/col_b evidence."""
        pattern = MagicMock()
        pattern.pattern_id = "pat2"
        pattern.pattern_type = "correlation"
        pattern.evidence = {}  # Missing col_a, col_b

        ctx = StepContext(data_rows=_numeric_rows(10), patterns=[pattern])
        result = await AnalyzeStep().run(ctx)
        assert result.success is True
        validated = result.context.analysis_results["validated_patterns"]
        assert len(validated) == 1
        assert "test" not in validated[0]


# ---------------------------------------------------------------------------
# ConcludeStep
# ---------------------------------------------------------------------------


class TestConcludeStep:
    @pytest.mark.asyncio
    async def test_empty_context_no_findings(self):
        ctx = StepContext()
        result = await ConcludeStep().run(ctx)
        assert result.success is True
        assert "No notable findings" in result.context.findings[0]

    @pytest.mark.asyncio
    async def test_full_context_summarizes_all(self):
        ctx = StepContext(
            patterns=["p1", "p2"],
            hypotheses=["h1"],
            predictions={"r_squared": 0.95, "target_column": "y"},
            proposals=[{"id": 1}],
            analysis_results={
                "validated_patterns": [
                    {"test": {"significant": True}},
                    {"test": {"significant": False}},
                ]
            },
        )
        result = await ConcludeStep().run(ctx)
        assert result.success is True
        findings = result.context.findings
        assert any("2 pattern(s)" in f for f in findings)
        assert any("1 hypothesis" in f for f in findings)
        assert any("R^2=0.950" in f for f in findings)
        assert any("1 experiment(s)" in f for f in findings)
        assert any("1/2" in f for f in findings)

    @pytest.mark.asyncio
    async def test_with_memory_root(self, tmp_path: Path):
        with (
            patch("labclaw.memory.markdown.TierABackend") as mock_backend_cls,
            patch("labclaw.memory.markdown.MemoryEntry"),
        ):
            ctx = StepContext(patterns=["p1"])
            step = ConcludeStep(memory_root=tmp_path, entity_id="lab")
            result = await step.run(ctx)
            assert result.success is True
            mock_backend_cls.return_value.append_memory.assert_called_once()

    @pytest.mark.asyncio
    async def test_memory_write_failure(self, tmp_path: Path):
        with (
            patch("labclaw.memory.markdown.TierABackend") as mock_backend_cls,
            patch("labclaw.memory.markdown.MemoryEntry"),
        ):
            mock_backend_cls.return_value.append_memory.side_effect = OSError("write fail")
            ctx = StepContext(patterns=["p1"])
            step = ConcludeStep(memory_root=tmp_path)
            result = await step.run(ctx)
            assert result.success is True


# ---------------------------------------------------------------------------
# ScientificLoop
# ---------------------------------------------------------------------------


class TestScientificLoop:
    @pytest.mark.asyncio
    async def test_run_cycle_with_valid_data(self):
        mock_steps = []
        for name in StepName:
            step = MagicMock()
            step.name = name

            async def make_result(ctx, n=name):
                return StepResult(step=n, success=True, context=ctx)

            step.run = make_result
            mock_steps.append(step)

        loop = ScientificLoop(steps=mock_steps)
        result = await loop.run_cycle(_numeric_rows(10))
        assert isinstance(result, CycleResult)
        assert result.success is True
        assert len(result.steps_completed) == 7

    @pytest.mark.asyncio
    async def test_run_cycle_with_empty_data(self):
        loop = ScientificLoop()
        result = await loop.run_cycle([])
        assert isinstance(result, CycleResult)
        assert StepName.OBSERVE in result.steps_skipped

    @pytest.mark.asyncio
    async def test_run_cycle_custom_steps(self):
        step = MagicMock()
        step.name = StepName.OBSERVE

        async def make_result(ctx):
            return StepResult(step=StepName.OBSERVE, success=True, context=ctx)

        step.run = make_result

        loop = ScientificLoop(steps=[step])
        result = await loop.run_cycle([{"x": 1}])
        assert len(result.steps_completed) == 1
        assert result.steps_completed[0] == StepName.OBSERVE

    @pytest.mark.asyncio
    async def test_events_emitted(self):
        events_captured: list[str] = []

        def handler(event):
            events_captured.append(str(event.event_name))

        event_registry.subscribe("*", handler)
        try:
            run_step = MagicMock()
            run_step.name = StepName.OBSERVE

            async def run_result(ctx):
                return StepResult(step=StepName.OBSERVE, success=True, context=ctx)

            run_step.run = run_result

            skip_step = MagicMock()
            skip_step.name = StepName.ASK

            async def skip_result(ctx):
                return StepResult(
                    step=StepName.ASK,
                    success=True,
                    skipped=True,
                    skip_reason="test",
                    context=ctx,
                )

            skip_step.run = skip_result

            loop = ScientificLoop(steps=[run_step, skip_step])
            await loop.run_cycle([{"x": 1}])

            assert "orchestrator.cycle.started" in events_captured
            assert "orchestrator.cycle.completed" in events_captured
            assert "orchestrator.step.started" in events_captured
            assert "orchestrator.step.completed" in events_captured
            assert "orchestrator.step.skipped" in events_captured
        finally:
            event_registry._handlers.pop("*", None)

    @pytest.mark.asyncio
    async def test_cycle_result_fields(self):
        step = MagicMock()
        step.name = StepName.OBSERVE

        async def result_fn(ctx):
            ctx2 = ctx.model_copy(update={"patterns": ["p1"], "hypotheses": ["h1"]})
            return StepResult(step=StepName.OBSERVE, success=True, context=ctx2)

        step.run = result_fn

        loop = ScientificLoop(steps=[step])
        result = await loop.run_cycle([{"x": 1}])
        assert result.patterns_found == 1
        assert result.hypotheses_generated == 1
        assert result.total_duration >= 0
        assert result.cycle_id
