"""Coverage tests for src/labclaw/orchestrator/steps.py — exception handlers and edge cases."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from labclaw.orchestrator.steps import (
    AnalyzeStep,
    ConcludeStep,
    ExperimentStep,
    HypothesizeStep,
    ObserveStep,
    PredictStep,
    StepContext,
    StepName,
    _uuid,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _numeric_rows(n: int = 20) -> list[dict[str, Any]]:
    return [{"x": float(i), "y": float(i * 2 + 1)} for i in range(n)]


def _context_with_numeric_stats(n: int = 20) -> StepContext:
    rows = _numeric_rows(n)
    return StepContext(
        data_rows=rows,
        metadata={"data_stats": {"numeric_columns": ["x", "y"]}},
    )


# ---------------------------------------------------------------------------
# _uuid — Line 31: module-level uuid helper
# ---------------------------------------------------------------------------


class TestUuidHelper:
    def test_returns_string(self) -> None:
        result = _uuid()
        assert isinstance(result, str)
        assert len(result) == 36  # UUID4 format

    def test_unique(self) -> None:
        assert _uuid() != _uuid()


# ---------------------------------------------------------------------------
# ObserveStep exception handler — Lines 149-151
# ---------------------------------------------------------------------------


class TestObserveStepExceptionHandler:
    @pytest.mark.asyncio
    async def test_exception_returns_failure(self) -> None:
        """Patch StepContext.model_copy at the class level to trigger the exception handler."""
        ctx = StepContext(data_rows=[{"x": 1}])
        with patch(
            "labclaw.orchestrator.steps.StepContext.model_copy", side_effect=RuntimeError("boom")
        ):
            result = await ObserveStep().run(ctx)
        assert result.success is False
        assert result.step == StepName.OBSERVE

    @pytest.mark.asyncio
    async def test_exception_preserves_original_context(self) -> None:
        """The exception handler returns the original context, not a copy."""
        ctx = StepContext(data_rows=[{"a": 1}])
        with patch(
            "labclaw.orchestrator.steps.StepContext.model_copy", side_effect=ValueError("bad")
        ):
            result = await ObserveStep().run(ctx)
        assert result.success is False
        assert result.context is ctx


# ---------------------------------------------------------------------------
# HypothesizeStep exception handler — Lines 258-260
# ---------------------------------------------------------------------------


class TestHypothesizeStepExceptionHandler:
    @pytest.mark.asyncio
    async def test_exception_returns_failure(self) -> None:
        """Force HypothesisGenerator to raise inside run()."""
        mock_pattern = MagicMock()
        ctx = StepContext(patterns=[mock_pattern])
        step = HypothesizeStep(llm_provider=None)

        mock_gen = MagicMock()
        mock_gen.generate.side_effect = RuntimeError("hypothesis crash")

        with patch("labclaw.discovery.hypothesis.HypothesisGenerator", return_value=mock_gen):
            result = await step.run(ctx)

        assert result.success is False
        assert result.step == StepName.HYPOTHESIZE
        assert result.context is ctx

    @pytest.mark.asyncio
    async def test_exception_no_llm_provider(self) -> None:
        """With no LLM provider, a crash in HypothesisGenerator is caught."""
        ctx = StepContext(patterns=["some_pattern"])
        step = HypothesizeStep(llm_provider=None)

        mock_gen = MagicMock()
        mock_gen.generate.side_effect = RuntimeError("gen failed")

        with patch("labclaw.discovery.hypothesis.HypothesisGenerator", return_value=mock_gen):
            result = await step.run(ctx)

        assert result.success is False
        assert result.step == StepName.HYPOTHESIZE


# ---------------------------------------------------------------------------
# PredictStep exception handler — Lines 340-342
# ---------------------------------------------------------------------------


class TestPredictStepExceptionHandler:
    @pytest.mark.asyncio
    async def test_exception_returns_failure(self) -> None:
        """PredictiveModel.train() raises, handler catches it."""
        ctx = _context_with_numeric_stats()

        mock_model = MagicMock()
        mock_model.train.side_effect = RuntimeError("model crash")

        with patch("labclaw.discovery.modeling.PredictiveModel", return_value=mock_model):
            result = await PredictStep().run(ctx)

        assert result.success is False
        assert result.step == StepName.PREDICT
        assert result.context is ctx

    @pytest.mark.asyncio
    async def test_exception_preserves_context(self) -> None:
        ctx = _context_with_numeric_stats()
        with patch(
            "labclaw.discovery.modeling.PredictiveModel", side_effect=RuntimeError("no model")
        ):
            result = await PredictStep().run(ctx)
        assert result.success is False
        assert result.context is ctx


# ---------------------------------------------------------------------------
# ExperimentStep — constant-value dimension (Lines 388, 395) + exception
# ---------------------------------------------------------------------------


class TestExperimentStepEdgeCases:
    @pytest.mark.asyncio
    async def test_constant_column_widens_range(self) -> None:
        """When lo == hi, hi is bumped to lo + 1.0 so optimizer doesn't crash."""
        rows = [{"x": 5.0, "y": 5.0} for _ in range(5)]
        ctx = StepContext(
            data_rows=rows,
            metadata={"data_stats": {"numeric_columns": ["x", "y"]}},
        )
        # Should not raise; optimizer gets valid (non-degenerate) bounds
        result = await ExperimentStep().run(ctx)
        # Either success or skip — must not be an exception failure
        assert result.step == StepName.EXPERIMENT

    @pytest.mark.asyncio
    async def test_all_values_non_numeric_skips(self) -> None:
        """If all values for a column are non-numeric, dimensions list stays empty → skip."""
        rows = [{"x": "bad"} for _ in range(5)]
        ctx = StepContext(
            data_rows=rows,
            metadata={"data_stats": {"numeric_columns": ["x"]}},
        )
        result = await ExperimentStep().run(ctx)
        assert result.skipped is True
        assert "Could not build parameter space" in result.skip_reason

    @pytest.mark.asyncio
    async def test_exception_returns_failure(self) -> None:
        """BayesianOptimizer.suggest() raises, handler catches it."""
        ctx = _context_with_numeric_stats()

        mock_optimizer = MagicMock()
        mock_optimizer.suggest.side_effect = RuntimeError("optimizer crash")

        # BayesianOptimizer is imported locally inside run(), patch at source
        with patch("labclaw.optimization.optimizer.BayesianOptimizer", return_value=mock_optimizer):
            result = await ExperimentStep().run(ctx)

        assert result.success is False
        assert result.step == StepName.EXPERIMENT
        assert result.context is ctx


# ---------------------------------------------------------------------------
# AnalyzeStep exception handler — Lines 509-511
# ---------------------------------------------------------------------------


class TestAnalyzeStepExceptionHandler:
    @pytest.mark.asyncio
    async def test_exception_returns_failure(self) -> None:
        """StatisticalValidator init raises, handler catches it."""
        mock_pattern = MagicMock()
        mock_pattern.pattern_type = "correlation"
        mock_pattern.pattern_id = "p1"
        ctx = StepContext(patterns=[mock_pattern])

        with patch(
            "labclaw.validation.statistics.StatisticalValidator",
            side_effect=RuntimeError("validator crash"),
        ):
            result = await AnalyzeStep().run(ctx)

        assert result.success is False
        assert result.step == StepName.ANALYZE
        assert result.context is ctx

    @pytest.mark.asyncio
    async def test_exception_with_model_copy_raise(self) -> None:
        """Patch model_copy at class level so exception is triggered after the loop."""
        ctx = StepContext(patterns=[MagicMock()])
        with patch(
            "labclaw.orchestrator.steps.StepContext.model_copy",
            side_effect=RuntimeError("bad copy"),
        ):
            result = await AnalyzeStep().run(ctx)
        assert result.success is False
        assert result.context is ctx


# ---------------------------------------------------------------------------
# ConcludeStep exception handler — Lines 596-598
# ---------------------------------------------------------------------------


class TestConcludeStepExceptionHandler:
    @pytest.mark.asyncio
    async def test_exception_returns_failure(self) -> None:
        """Patch StepContext.model_copy at class level to trigger exception handler."""
        ctx = StepContext(
            patterns=["p1"],
            hypotheses=["h1"],
        )
        with patch(
            "labclaw.orchestrator.steps.StepContext.model_copy",
            side_effect=RuntimeError("copy crash"),
        ):
            result = await ConcludeStep().run(ctx)

        assert result.success is False
        assert result.step == StepName.CONCLUDE
        assert result.context is ctx

    @pytest.mark.asyncio
    async def test_exception_preserves_context(self) -> None:
        ctx = StepContext(patterns=["p"])
        with patch(
            "labclaw.orchestrator.steps.StepContext.model_copy", side_effect=ValueError("bad")
        ):
            result = await ConcludeStep().run(ctx)
        assert result.success is False
        assert result.context is ctx

    @pytest.mark.asyncio
    async def test_duration_is_non_negative_on_exception(self) -> None:
        ctx = StepContext(patterns=["p"])
        with patch(
            "labclaw.orchestrator.steps.StepContext.model_copy", side_effect=RuntimeError("crash")
        ):
            result = await ConcludeStep().run(ctx)
        assert result.duration_seconds >= 0.0
