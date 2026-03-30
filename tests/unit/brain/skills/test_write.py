"""Tests for Write Cloud Brain skill."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from labclaw.brain.skills.base import CloudSkill, SkillCapability
from labclaw.brain.types import BrainResult, ToolInfo


class TestWriteSkillMetadata:
    """WriteSkill metadata is properly configured."""

    def test_metadata_name(self) -> None:
        from labclaw.brain.skills.write import WriteSkill

        skill = WriteSkill()
        assert skill.metadata.name == "write"

    def test_metadata_version(self) -> None:
        from labclaw.brain.skills.write import WriteSkill

        skill = WriteSkill()
        assert skill.metadata.version == "0.1.0"

    def test_metadata_capabilities(self) -> None:
        from labclaw.brain.skills.write import WriteSkill

        skill = WriteSkill()
        assert SkillCapability.WRITING in skill.metadata.capabilities

    def test_satisfies_cloud_skill_protocol(self) -> None:
        from labclaw.brain.skills.write import WriteSkill

        skill = WriteSkill()
        assert isinstance(skill, CloudSkill)


class TestWriteSection:
    """execute('write_section', ...) generates scientific text."""

    @pytest.mark.asyncio
    async def test_write_section_with_llm(self) -> None:
        from labclaw.brain.skills.write import WriteSkill

        mock_llm = AsyncMock()
        mock_llm.complete.return_value = "Mice were anesthetized with isoflurane..."
        skill = WriteSkill(llm_provider=mock_llm)

        result = await skill.execute("write_section", section="methods", context="Surgery protocol")
        assert isinstance(result, BrainResult)
        assert result.success is True
        assert "anesthetized" in result.data["text"]
        assert result.data["section"] == "methods"
        mock_llm.complete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_write_section_without_llm_returns_error(self) -> None:
        from labclaw.brain.skills.write import WriteSkill

        skill = WriteSkill()  # no LLM provider
        result = await skill.execute("write_section", section="methods", context="Surgery")
        assert result.success is False
        assert "No LLM provider" in (result.error or "")

    @pytest.mark.asyncio
    async def test_write_section_unknown_section_type(self) -> None:
        from labclaw.brain.skills.write import WriteSkill

        mock_llm = AsyncMock()
        mock_llm.complete.return_value = "Generic text."
        skill = WriteSkill(llm_provider=mock_llm)

        # Unknown section still works, uses generic prompt
        result = await skill.execute("write_section", section="appendix", context="Data")
        assert result.success is True


class TestFormatCitation:
    """execute('format_citation', ...) is pure string formatting."""

    @pytest.mark.asyncio
    async def test_format_citation_apa(self) -> None:
        from labclaw.brain.skills.write import WriteSkill

        skill = WriteSkill()  # no LLM needed
        result = await skill.execute(
            "format_citation",
            title="A Great Paper",
            authors=["Smith, J.", "Doe, A."],
            year=2024,
            journal="Nature",
            doi="10.1234/test",
            style="apa",
        )
        assert result.success is True
        assert "Smith, J." in result.data["citation"]
        assert "2024" in result.data["citation"]
        assert "Nature" in result.data["citation"]
        assert "10.1234/test" in result.data["citation"]

    @pytest.mark.asyncio
    async def test_format_citation_default_style(self) -> None:
        from labclaw.brain.skills.write import WriteSkill

        skill = WriteSkill()
        result = await skill.execute(
            "format_citation",
            title="Paper Title",
        )
        assert result.success is True
        assert "Paper Title" in result.data["citation"]

    @pytest.mark.asyncio
    async def test_format_citation_non_apa_no_doi(self) -> None:
        """Test non-APA citation style without DOI (covers line 120->123 branch)."""
        from labclaw.brain.skills.write import WriteSkill

        skill = WriteSkill()
        result = await skill.execute(
            "format_citation",
            title="Paper Without DOI",
            authors=["Auth, A."],
            year=2023,
            journal="Science",
            style="mla",
        )
        assert result.success is True
        assert result.data["style"] == "mla"
        assert "doi:" not in result.data["citation"]

    @pytest.mark.asyncio
    async def test_format_citation_non_apa_with_doi(self) -> None:
        """Test non-APA citation style with DOI (covers line 121)."""
        from labclaw.brain.skills.write import WriteSkill

        skill = WriteSkill()
        result = await skill.execute(
            "format_citation",
            title="Paper With DOI",
            authors=["Auth, A."],
            year=2023,
            journal="Science",
            doi="10.5678/test",
            style="mla",
        )
        assert result.success is True
        assert result.data["style"] == "mla"
        assert "doi:10.5678/test" in result.data["citation"]


class TestWriteListTools:
    """list_tools() returns 2 ToolInfo items."""

    @pytest.mark.asyncio
    async def test_list_tools_returns_two(self) -> None:
        from labclaw.brain.skills.write import WriteSkill

        skill = WriteSkill()
        tools = await skill.list_tools()
        assert len(tools) == 2
        assert all(isinstance(t, ToolInfo) for t in tools)
        names = {t.name for t in tools}
        assert "write_section" in names
        assert "format_citation" in names

    @pytest.mark.asyncio
    async def test_list_tools_skill_field(self) -> None:
        from labclaw.brain.skills.write import WriteSkill

        skill = WriteSkill()
        tools = await skill.list_tools()
        assert all(t.skill == "write" for t in tools)


class TestWriteHealthCheck:
    """health_check() always returns True (format_citation works without LLM)."""

    @pytest.mark.asyncio
    async def test_health_check_always_true(self) -> None:
        from labclaw.brain.skills.write import WriteSkill

        skill = WriteSkill()
        assert await skill.health_check() is True

    @pytest.mark.asyncio
    async def test_health_check_true_with_llm(self) -> None:
        from labclaw.brain.skills.write import WriteSkill

        mock_llm = AsyncMock()
        skill = WriteSkill(llm_provider=mock_llm)
        assert await skill.health_check() is True


class TestWriteUnknownTool:
    """Unknown tool_name returns error."""

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self) -> None:
        from labclaw.brain.skills.write import WriteSkill

        skill = WriteSkill()
        result = await skill.execute("nonexistent_tool")
        assert result.success is False
        assert "Unknown tool" in (result.error or "")
