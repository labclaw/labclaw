"""Cover skill uncovered lines.

lifesci.py  lines 84-86, 107-109:  Exception in _reason / _design_experiment
tooluniverse.py lines 45, 68-70:   init_sdk early return / generic exception
write.py lines 94-96:              Exception in _write_section
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# lifesci.py lines 84-86
# ---------------------------------------------------------------------------


class TestLifeSciReasonException:
    """_reason catches LLM exception and returns BrainResult(success=False)."""

    @pytest.mark.asyncio
    async def test_reason_llm_exception_returns_error(self) -> None:
        from labclaw.brain.skills.lifesci import LifeSciSkill

        mock_llm = AsyncMock()
        mock_llm.complete.side_effect = RuntimeError("API timeout")
        skill = LifeSciSkill(llm_provider=mock_llm)

        result = await skill.execute("reason", question="What is GABA?")
        assert result.success is False
        assert "API timeout" in (result.error or "")


# ---------------------------------------------------------------------------
# lifesci.py lines 107-109
# ---------------------------------------------------------------------------


class TestLifeSciDesignExperimentException:
    """_design_experiment catches LLM exception and returns BrainResult(success=False)."""

    @pytest.mark.asyncio
    async def test_design_experiment_llm_exception_returns_error(self) -> None:
        from labclaw.brain.skills.lifesci import LifeSciSkill

        mock_llm = AsyncMock()
        mock_llm.complete.side_effect = RuntimeError("Provider crashed")
        skill = LifeSciSkill(llm_provider=mock_llm)

        result = await skill.execute("design_experiment", description="Test drug X")
        assert result.success is False
        assert "Provider crashed" in (result.error or "")


# ---------------------------------------------------------------------------
# tooluniverse.py line 45: init_sdk early return when _tu_instance is not None
# ---------------------------------------------------------------------------


class TestToolUniverseInitSdkEarlyReturn:
    """init_sdk returns immediately when instance already initialized."""

    @pytest.mark.asyncio
    async def test_init_sdk_returns_early_when_instance_exists(self) -> None:
        from labclaw.brain.skills.tooluniverse import ToolUniverseSkill

        skill = ToolUniverseSkill()
        skill._tu_instance = MagicMock()  # already initialized

        # Should return without doing anything
        await skill.init_sdk()
        # Instance unchanged
        assert skill._tu_instance is not None


# ---------------------------------------------------------------------------
# tooluniverse.py lines 68-70: generic exception in init_sdk
# ---------------------------------------------------------------------------


class TestToolUniverseInitSdkGenericException:
    """init_sdk handles non-ImportError exceptions gracefully."""

    @pytest.mark.asyncio
    async def test_init_sdk_generic_exception(self) -> None:
        from labclaw.brain.skills.tooluniverse import ToolUniverseSkill

        mock_tu_class = MagicMock(side_effect=RuntimeError("SDK crash"))

        with patch.dict("sys.modules", {"tooluniverse": MagicMock(ToolUniverse=mock_tu_class)}):
            skill = ToolUniverseSkill()
            await skill.init_sdk()
            assert skill._tu_instance is None


# ---------------------------------------------------------------------------
# write.py lines 94-96
# ---------------------------------------------------------------------------


class TestWriteSectionException:
    """_write_section catches LLM exception and returns BrainResult(success=False)."""

    @pytest.mark.asyncio
    async def test_write_section_llm_exception_returns_error(self) -> None:
        from labclaw.brain.skills.write import WriteSkill

        mock_llm = AsyncMock()
        mock_llm.complete.side_effect = RuntimeError("LLM unavailable")
        skill = WriteSkill(llm_provider=mock_llm)

        result = await skill.execute("write_section", section="methods", context="Protocol")
        assert result.success is False
        assert "LLM unavailable" in (result.error or "")
