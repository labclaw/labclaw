"""Tests for the Cloud Brain public API (brain/__init__.py)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from labclaw.brain.types import BrainResult, HealthStatus, ToolInfo

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_registry():
    """Reset the global registry before each test."""
    import labclaw.brain as brain_mod

    brain_mod._registry = None
    yield
    brain_mod._registry = None


def _make_mock_registry(
    *,
    execute_result: BrainResult | None = None,
    tools: list[ToolInfo] | None = None,
    health_map: dict[str, bool] | None = None,
) -> MagicMock:
    """Create a mock SkillRegistry with configurable returns."""
    reg = MagicMock()
    reg.execute = AsyncMock(return_value=execute_result or BrainResult(success=True, data="ok"))
    reg.list_all_tools = AsyncMock(return_value=tools or [])
    reg.health = AsyncMock(return_value=health_map or {})
    return reg


# ---------------------------------------------------------------------------
# execute
# ---------------------------------------------------------------------------


class TestExecute:
    async def test_delegates_to_registry(self):
        import labclaw.brain as brain_mod

        expected = BrainResult(success=True, data={"result": 42})
        mock_reg = _make_mock_registry(execute_result=expected)
        brain_mod._registry = mock_reg

        result = await brain_mod.execute("search_pubmed", query="CRISPR")

        mock_reg.execute.assert_awaited_once_with("search_pubmed", query="CRISPR")
        assert result is expected

    async def test_passes_kwargs_through(self):
        import labclaw.brain as brain_mod

        mock_reg = _make_mock_registry()
        brain_mod._registry = mock_reg

        await brain_mod.execute("run_tool", x=1, y="two")

        mock_reg.execute.assert_awaited_once_with("run_tool", x=1, y="two")


# ---------------------------------------------------------------------------
# list_tools
# ---------------------------------------------------------------------------


class TestListTools:
    async def test_returns_all_tools(self):
        import labclaw.brain as brain_mod

        tools = [
            ToolInfo(name="t1", description="desc1", skill="s1"),
            ToolInfo(name="t2", description="desc2", skill="s2"),
        ]
        mock_reg = _make_mock_registry(tools=tools)
        brain_mod._registry = mock_reg

        result = await brain_mod.list_tools()

        mock_reg.list_all_tools.assert_awaited_once_with(category="")
        assert result == tools

    async def test_filters_by_category(self):
        import labclaw.brain as brain_mod

        mock_reg = _make_mock_registry()
        brain_mod._registry = mock_reg

        await brain_mod.list_tools(category="biology")

        mock_reg.list_all_tools.assert_awaited_once_with(category="biology")


# ---------------------------------------------------------------------------
# reason
# ---------------------------------------------------------------------------


class TestReason:
    async def test_calls_execute_with_reason_tool(self):
        import labclaw.brain as brain_mod

        expected = BrainResult(success=True, data="reasoning output")
        mock_reg = _make_mock_registry(execute_result=expected)
        brain_mod._registry = mock_reg

        result = await brain_mod.reason("What is CRISPR?")

        mock_reg.execute.assert_awaited_once_with(
            "reason", question="What is CRISPR?", domain="general", context=""
        )
        assert result is expected

    async def test_passes_domain_and_context(self):
        import labclaw.brain as brain_mod

        mock_reg = _make_mock_registry()
        brain_mod._registry = mock_reg

        await brain_mod.reason("Q?", domain="neuroscience", context="brain imaging")

        mock_reg.execute.assert_awaited_once_with(
            "reason", question="Q?", domain="neuroscience", context="brain imaging"
        )


# ---------------------------------------------------------------------------
# write
# ---------------------------------------------------------------------------


class TestWrite:
    async def test_calls_execute_with_write_section_tool(self):
        import labclaw.brain as brain_mod

        expected = BrainResult(success=True, data="abstract text")
        mock_reg = _make_mock_registry(execute_result=expected)
        brain_mod._registry = mock_reg

        result = await brain_mod.write(section="abstract", context="CRISPR study")

        mock_reg.execute.assert_awaited_once_with(
            "write_section", section="abstract", context="CRISPR study"
        )
        assert result is expected


# ---------------------------------------------------------------------------
# health
# ---------------------------------------------------------------------------


class TestHealth:
    async def test_returns_health_status(self):
        import labclaw.brain as brain_mod

        tools = [ToolInfo(name="t1", description="d", skill="s")]
        mock_reg = _make_mock_registry(
            health_map={"tooluniverse": True, "lifesci": True}, tools=tools
        )
        brain_mod._registry = mock_reg

        result = await brain_mod.health()

        assert isinstance(result, HealthStatus)
        assert result.status == "ok"
        assert result.skills == {"tooluniverse": True, "lifesci": True}
        assert result.tool_count == 1
        assert isinstance(result.version, str)

    async def test_degraded_when_skill_unhealthy(self):
        import labclaw.brain as brain_mod

        mock_reg = _make_mock_registry(health_map={"tooluniverse": True, "lifesci": False})
        brain_mod._registry = mock_reg

        result = await brain_mod.health()

        assert result.status == "degraded"

    async def test_degraded_when_no_skills(self):
        import labclaw.brain as brain_mod

        mock_reg = _make_mock_registry(health_map={})
        brain_mod._registry = mock_reg

        result = await brain_mod.health()

        assert result.status == "degraded"
        assert result.tool_count == 0


# ---------------------------------------------------------------------------
# _get_registry
# ---------------------------------------------------------------------------


class TestGetRegistry:
    def test_creates_registry_on_first_call(self):
        import labclaw.brain as brain_mod

        with patch.object(brain_mod, "_register_defaults") as mock_register:
            reg = brain_mod._get_registry()

            assert reg is not None
            mock_register.assert_called_once_with(reg)

    def test_returns_same_registry_on_second_call(self):
        import labclaw.brain as brain_mod

        with patch.object(brain_mod, "_register_defaults"):
            reg1 = brain_mod._get_registry()
            reg2 = brain_mod._get_registry()

            assert reg1 is reg2


# ---------------------------------------------------------------------------
# _register_defaults
# ---------------------------------------------------------------------------


class TestRegisterDefaults:
    def test_handles_import_error_gracefully(self):
        import labclaw.brain as brain_mod
        from labclaw.brain.skills.registry import SkillRegistry

        registry = SkillRegistry()

        with patch(
            "labclaw.brain.skills.tooluniverse.ToolUniverseSkill",
            side_effect=ImportError("no tooluniverse"),
        ):
            # Should not raise
            brain_mod._register_defaults(registry)

    def test_handles_generic_exception_gracefully(self):
        import labclaw.brain as brain_mod
        from labclaw.brain.skills.registry import SkillRegistry

        registry = SkillRegistry()

        with patch(
            "labclaw.brain.skills.tooluniverse.ToolUniverseSkill",
            side_effect=RuntimeError("boom"),
        ):
            # Should not raise
            brain_mod._register_defaults(registry)

    def test_registers_available_skills(self):
        import labclaw.brain as brain_mod
        from labclaw.brain.skills.registry import SkillRegistry

        registry = SkillRegistry()
        brain_mod._register_defaults(registry)

        # At minimum, LifeSci and Write should register (no external deps)
        skill_names = registry.list_skills()
        assert "lifesci" in skill_names
        assert "write" in skill_names
