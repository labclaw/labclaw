"""Tests for LifeSci skill exception handlers.

Covers lines 84-86 (_reason exception) and 107-109 (_design_experiment exception).
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from labclaw.brain.skills.lifesci import LifeSciSkill
from labclaw.brain.types import BrainResult


class TestLifeSciReasonException:
    """Cover lines 84-86: exception handler in _reason."""

    @pytest.mark.asyncio
    async def test_reason_exception_returns_error(self) -> None:
        """When LLM provider throws during reason, exception is caught."""
        mock_llm = AsyncMock()
        mock_llm.complete.side_effect = ConnectionError("API down")
        skill = LifeSciSkill(llm_provider=mock_llm)

        result = await skill.execute("reason", question="What is GABA?")
        assert isinstance(result, BrainResult)
        assert result.success is False
        assert "API down" in (result.error or "")


class TestLifeSciDesignExperimentException:
    """Cover lines 107-109: exception handler in _design_experiment."""

    @pytest.mark.asyncio
    async def test_design_experiment_exception_returns_error(self) -> None:
        """When LLM provider throws during design_experiment, exception is caught."""
        mock_llm = AsyncMock()
        mock_llm.complete.side_effect = RuntimeError("Model overloaded")
        skill = LifeSciSkill(llm_provider=mock_llm)

        result = await skill.execute("design_experiment", description="Test drug X")
        assert isinstance(result, BrainResult)
        assert result.success is False
        assert "Model overloaded" in (result.error or "")
