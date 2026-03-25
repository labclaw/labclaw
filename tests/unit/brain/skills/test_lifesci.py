"""Tests for LifeSci Cloud Brain skill."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from labclaw.brain.skills.base import CloudSkill, SkillCapability
from labclaw.brain.types import BrainResult, ToolInfo


class TestLifeSciMetadata:
    """LifeSciSkill metadata is properly configured."""

    def test_metadata_name(self) -> None:
        from labclaw.brain.skills.lifesci import LifeSciSkill

        skill = LifeSciSkill()
        assert skill.metadata.name == "lifesci"

    def test_metadata_version(self) -> None:
        from labclaw.brain.skills.lifesci import LifeSciSkill

        skill = LifeSciSkill()
        assert skill.metadata.version == "0.1.0"

    def test_metadata_capabilities(self) -> None:
        from labclaw.brain.skills.lifesci import LifeSciSkill

        skill = LifeSciSkill()
        assert SkillCapability.REASONING in skill.metadata.capabilities

    def test_satisfies_cloud_skill_protocol(self) -> None:
        from labclaw.brain.skills.lifesci import LifeSciSkill

        skill = LifeSciSkill()
        assert isinstance(skill, CloudSkill)


class TestLifeSciReason:
    """execute('reason', ...) calls LLM with system prompt."""

    @pytest.mark.asyncio
    async def test_reason_with_llm(self) -> None:
        from labclaw.brain.skills.lifesci import LifeSciSkill

        mock_llm = AsyncMock()
        mock_llm.complete.return_value = "GABA is an inhibitory neurotransmitter."
        skill = LifeSciSkill(llm_provider=mock_llm)

        result = await skill.execute("reason", question="What is GABA?")
        assert isinstance(result, BrainResult)
        assert result.success is True
        assert "GABA" in result.data["answer"]
        mock_llm.complete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_reason_with_domain(self) -> None:
        from labclaw.brain.skills.lifesci import LifeSciSkill

        mock_llm = AsyncMock()
        mock_llm.complete.return_value = "Neuroscience answer."
        skill = LifeSciSkill(llm_provider=mock_llm)

        result = await skill.execute("reason", question="Q?", domain="neuroscience")
        assert result.success is True
        assert result.data["domain"] == "neuroscience"

    @pytest.mark.asyncio
    async def test_reason_without_llm_returns_error(self) -> None:
        from labclaw.brain.skills.lifesci import LifeSciSkill

        skill = LifeSciSkill()  # no LLM provider
        result = await skill.execute("reason", question="What is GABA?")
        assert result.success is False
        assert "No LLM provider" in (result.error or "")


class TestLifeSciDesignExperiment:
    """execute('design_experiment', ...) calls LLM with experiment prompt."""

    @pytest.mark.asyncio
    async def test_design_experiment_with_llm(self) -> None:
        from labclaw.brain.skills.lifesci import LifeSciSkill

        mock_llm = AsyncMock()
        mock_llm.complete.return_value = "Use 3 groups of 10 mice..."
        skill = LifeSciSkill(llm_provider=mock_llm)

        result = await skill.execute("design_experiment", description="Test drug X on memory")
        assert isinstance(result, BrainResult)
        assert result.success is True
        assert "mice" in result.data["design"]

    @pytest.mark.asyncio
    async def test_design_experiment_without_llm_returns_error(self) -> None:
        from labclaw.brain.skills.lifesci import LifeSciSkill

        skill = LifeSciSkill()
        result = await skill.execute("design_experiment", description="Test drug X")
        assert result.success is False
        assert "No LLM provider" in (result.error or "")


class TestLifeSciListTools:
    """list_tools() returns 2 ToolInfo items."""

    @pytest.mark.asyncio
    async def test_list_tools_returns_two(self) -> None:
        from labclaw.brain.skills.lifesci import LifeSciSkill

        skill = LifeSciSkill()
        tools = await skill.list_tools()
        assert len(tools) == 2
        assert all(isinstance(t, ToolInfo) for t in tools)
        names = {t.name for t in tools}
        assert "reason" in names
        assert "design_experiment" in names

    @pytest.mark.asyncio
    async def test_list_tools_skill_field(self) -> None:
        from labclaw.brain.skills.lifesci import LifeSciSkill

        skill = LifeSciSkill()
        tools = await skill.list_tools()
        assert all(t.skill == "lifesci" for t in tools)


class TestLifeSciHealthCheck:
    """health_check() depends on LLM provider."""

    @pytest.mark.asyncio
    async def test_health_check_with_provider(self) -> None:
        from labclaw.brain.skills.lifesci import LifeSciSkill

        mock_llm = AsyncMock()
        skill = LifeSciSkill(llm_provider=mock_llm)
        assert await skill.health_check() is True

    @pytest.mark.asyncio
    async def test_health_check_without_provider(self) -> None:
        from labclaw.brain.skills.lifesci import LifeSciSkill

        skill = LifeSciSkill()
        assert await skill.health_check() is False


class TestLifeSciUnknownTool:
    """Unknown tool_name returns error."""

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self) -> None:
        from labclaw.brain.skills.lifesci import LifeSciSkill

        skill = LifeSciSkill()
        result = await skill.execute("nonexistent_tool", question="Q?")
        assert result.success is False
        assert "Unknown tool" in (result.error or "")
