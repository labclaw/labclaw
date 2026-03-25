"""Tests for ToolUniverse Cloud Brain skill."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from labclaw.brain.skills.base import CloudSkill, SkillCapability
from labclaw.brain.types import BrainResult, ToolInfo


class TestToolUniverseSkillMetadata:
    """ToolUniverseSkill metadata is properly configured."""

    def test_metadata_name(self) -> None:
        from labclaw.brain.skills.tooluniverse import ToolUniverseSkill

        skill = ToolUniverseSkill()
        assert skill.metadata.name == "tooluniverse"

    def test_metadata_version(self) -> None:
        from labclaw.brain.skills.tooluniverse import ToolUniverseSkill

        skill = ToolUniverseSkill()
        assert skill.metadata.version == "0.1.0"

    def test_metadata_capabilities(self) -> None:
        from labclaw.brain.skills.tooluniverse import ToolUniverseSkill

        skill = ToolUniverseSkill()
        assert SkillCapability.TOOL_EXECUTION in skill.metadata.capabilities

    def test_satisfies_cloud_skill_protocol(self) -> None:
        from labclaw.brain.skills.tooluniverse import ToolUniverseSkill

        skill = ToolUniverseSkill()
        assert isinstance(skill, CloudSkill)


class TestToolUniverseExecute:
    """execute() delegates to ToolUniverse SDK via executor."""

    @pytest.mark.asyncio
    async def test_execute_returns_brain_result(self) -> None:
        from labclaw.brain.skills.tooluniverse import ToolUniverseSkill

        skill = ToolUniverseSkill()
        mock_tu = MagicMock()
        mock_tu.run.return_value = {"result": "protein_data"}
        skill._tu_instance = mock_tu

        result = await skill.execute("UniProt_get_entry", accession="P12345")
        assert isinstance(result, BrainResult)
        assert result.success is True
        assert result.data == {"result": "protein_data"}

    @pytest.mark.asyncio
    async def test_execute_sdk_error_status(self) -> None:
        from labclaw.brain.skills.tooluniverse import ToolUniverseSkill

        skill = ToolUniverseSkill()
        mock_tu = MagicMock()
        mock_tu.run.return_value = {"status": "error", "error": "tool not found"}
        skill._tu_instance = mock_tu

        result = await skill.execute("bad_tool")
        assert result.success is False
        assert "tool not found" in (result.error or "")

    @pytest.mark.asyncio
    async def test_execute_timeout_returns_error(self) -> None:
        from labclaw.brain.skills.tooluniverse import ToolUniverseSkill

        skill = ToolUniverseSkill()
        mock_tu = MagicMock()

        async def slow_run(*_args: object, **_kw: object) -> None:
            await asyncio.sleep(100)

        # Patch run_in_executor to simulate slow call
        with patch("asyncio.wait_for", side_effect=TimeoutError):
            skill._tu_instance = mock_tu
            result = await skill.execute("slow_tool")
            assert result.success is False
            assert "timed out" in (result.error or "").lower()

    @pytest.mark.asyncio
    async def test_execute_exception_returns_error(self) -> None:
        from labclaw.brain.skills.tooluniverse import ToolUniverseSkill

        skill = ToolUniverseSkill()
        mock_tu = MagicMock()
        mock_tu.run.side_effect = RuntimeError("SDK crashed")
        skill._tu_instance = mock_tu

        result = await skill.execute("crashing_tool")
        assert isinstance(result, BrainResult)
        assert result.success is False
        assert "SDK crashed" in (result.error or "")

    @pytest.mark.asyncio
    async def test_execute_without_sdk_returns_error(self) -> None:
        from labclaw.brain.skills.tooluniverse import ToolUniverseSkill

        skill = ToolUniverseSkill()
        # _tu_instance is None by default
        result = await skill.execute("any_tool")
        assert result.success is False
        assert result.error is not None


class TestToolUniverseListTools:
    """list_tools() queries the SDK for available tools."""

    @pytest.mark.asyncio
    async def test_list_tools_returns_tool_info_list(self) -> None:
        from labclaw.brain.skills.tooluniverse import ToolUniverseSkill

        skill = ToolUniverseSkill()
        mock_tu = MagicMock()
        mock_tu.return_all_loaded_tools.return_value = [
            {"name": "UniProt_search", "description": "Search UniProt", "category": "protein"},
            {"name": "PubChem_lookup", "description": "Lookup compound", "category": "chemistry"},
        ]
        skill._tu_instance = mock_tu

        tools = await skill.list_tools()
        assert len(tools) == 2
        assert all(isinstance(t, ToolInfo) for t in tools)
        assert tools[0].name == "UniProt_search"
        assert tools[0].skill == "tooluniverse"

    @pytest.mark.asyncio
    async def test_list_tools_no_sdk_returns_empty(self) -> None:
        from labclaw.brain.skills.tooluniverse import ToolUniverseSkill

        skill = ToolUniverseSkill()
        # _tu_instance is None
        tools = await skill.list_tools()
        assert tools == []


class TestToolUniverseHealthCheck:
    """health_check() depends on SDK availability."""

    @pytest.mark.asyncio
    async def test_health_check_true_when_loaded(self) -> None:
        from labclaw.brain.skills.tooluniverse import ToolUniverseSkill

        skill = ToolUniverseSkill()
        skill._tu_instance = MagicMock()
        assert await skill.health_check() is True

    @pytest.mark.asyncio
    async def test_health_check_false_when_not_loaded(self) -> None:
        from labclaw.brain.skills.tooluniverse import ToolUniverseSkill

        skill = ToolUniverseSkill()
        assert await skill.health_check() is False


class TestToolUniverseInitLock:
    """Singleton initialization uses asyncio.Lock for safety."""

    @pytest.mark.asyncio
    async def test_init_sdk_concurrent_calls_safe(self) -> None:
        from labclaw.brain.skills.tooluniverse import ToolUniverseSkill

        mock_tu_class = MagicMock()
        mock_instance = MagicMock()
        mock_instance.return_all_loaded_tools.return_value = [{"name": "t"}]
        mock_tu_class.return_value = mock_instance

        with patch.dict("sys.modules", {"tooluniverse": MagicMock(ToolUniverse=mock_tu_class)}):
            skill = ToolUniverseSkill()
            # Call init_sdk concurrently
            await asyncio.gather(
                skill.init_sdk(),
                skill.init_sdk(),
                skill.init_sdk(),
            )
            # All should succeed, SDK constructed at most once
            assert skill._tu_instance is not None


class TestToolUniverseImportError:
    """Graceful handling when tooluniverse package is not installed."""

    @pytest.mark.asyncio
    async def test_init_sdk_import_error(self) -> None:
        from labclaw.brain.skills.tooluniverse import ToolUniverseSkill

        skill = ToolUniverseSkill()

        with patch.dict("sys.modules", {"tooluniverse": None}):
            # init_sdk should not raise
            await skill.init_sdk()
            assert skill._tu_instance is None
