"""Tests for Cloud Brain skill registry."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from labclaw.brain.skills.base import SkillCapability, SkillMetadata
from labclaw.brain.skills.registry import SkillRegistry
from labclaw.brain.types import BrainResult, ToolInfo


def _make_mock_skill(
    name: str = "test_skill",
    tools: list[ToolInfo] | None = None,
) -> MagicMock:
    """Create a mock CloudSkill with sensible defaults."""
    skill = MagicMock()
    skill.metadata = SkillMetadata(
        name=name,
        version="0.1.0",
        description="Test",
        capabilities=[SkillCapability.TOOL_EXECUTION],
    )
    if tools is None:
        tools = [ToolInfo(name=f"{name}_tool", description="A tool", skill=name)]
    skill.list_tools = AsyncMock(return_value=tools)
    skill.execute = AsyncMock(return_value=BrainResult(success=True, data="ok"))
    skill.health_check = AsyncMock(return_value=True)
    return skill


class TestRegisterAndList:
    """register() and list_skills() basics."""

    def test_register_and_list(self) -> None:
        reg = SkillRegistry()
        skill = _make_mock_skill("alpha")
        reg.register(skill)
        assert reg.list_skills() == ["alpha"]

    def test_register_multiple(self) -> None:
        reg = SkillRegistry()
        reg.register(_make_mock_skill("a"))
        reg.register(_make_mock_skill("b"))
        assert sorted(reg.list_skills()) == ["a", "b"]

    def test_register_duplicate_raises(self) -> None:
        reg = SkillRegistry()
        reg.register(_make_mock_skill("dup"))
        with pytest.raises(ValueError, match="already registered"):
            reg.register(_make_mock_skill("dup"))


class TestUnregister:
    """unregister() removes a skill."""

    def test_unregister_existing(self) -> None:
        reg = SkillRegistry()
        reg.register(_make_mock_skill("gone"))
        reg.unregister("gone")
        assert reg.list_skills() == []

    def test_unregister_missing_raises(self) -> None:
        reg = SkillRegistry()
        with pytest.raises(KeyError, match="not registered"):
            reg.unregister("nope")


class TestListAllTools:
    """list_all_tools() aggregates tools across skills."""

    @pytest.mark.asyncio
    async def test_list_all_tools_multiple_skills(self) -> None:
        reg = SkillRegistry()
        reg.register(_make_mock_skill("s1"))
        reg.register(_make_mock_skill("s2"))
        tools = await reg.list_all_tools()
        names = [t.name for t in tools]
        assert "s1_tool" in names
        assert "s2_tool" in names

    @pytest.mark.asyncio
    async def test_list_all_tools_category_filter(self) -> None:
        reg = SkillRegistry()
        tool_a = ToolInfo(name="a", description="A", skill="s", category="bio")
        tool_b = ToolInfo(name="b", description="B", skill="s", category="chem")
        reg.register(_make_mock_skill("s", tools=[tool_a, tool_b]))

        bio_tools = await reg.list_all_tools(category="bio")
        assert len(bio_tools) == 1
        assert bio_tools[0].name == "a"

    @pytest.mark.asyncio
    async def test_list_all_tools_empty_registry(self) -> None:
        reg = SkillRegistry()
        tools = await reg.list_all_tools()
        assert tools == []


class TestExecute:
    """execute() routes to the correct skill."""

    @pytest.mark.asyncio
    async def test_execute_routes_correctly(self) -> None:
        reg = SkillRegistry()
        skill = _make_mock_skill("router")
        reg.register(skill)

        result = await reg.execute("router_tool", arg1="val")
        assert result.success is True
        skill.execute.assert_awaited_once_with("router_tool", arg1="val")

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self) -> None:
        reg = SkillRegistry()
        result = await reg.execute("nonexistent")
        assert result.success is False
        assert "not found" in (result.error or "").lower()

    @pytest.mark.asyncio
    async def test_execute_picks_right_skill_among_many(self) -> None:
        reg = SkillRegistry()
        s1 = _make_mock_skill("first")
        s2 = _make_mock_skill("second")
        reg.register(s1)
        reg.register(s2)

        await reg.execute("second_tool")
        s2.execute.assert_awaited_once_with("second_tool")
        s1.execute.assert_not_awaited()


class TestHealth:
    """health() returns status dict for all skills."""

    @pytest.mark.asyncio
    async def test_health_all_healthy(self) -> None:
        reg = SkillRegistry()
        reg.register(_make_mock_skill("h1"))
        reg.register(_make_mock_skill("h2"))
        status = await reg.health()
        assert status == {"h1": True, "h2": True}

    @pytest.mark.asyncio
    async def test_health_with_unhealthy_skill(self) -> None:
        reg = SkillRegistry()
        healthy = _make_mock_skill("ok")
        unhealthy = _make_mock_skill("bad")
        unhealthy.health_check = AsyncMock(return_value=False)
        reg.register(healthy)
        reg.register(unhealthy)
        status = await reg.health()
        assert status == {"ok": True, "bad": False}

    @pytest.mark.asyncio
    async def test_health_empty_registry(self) -> None:
        reg = SkillRegistry()
        status = await reg.health()
        assert status == {}
