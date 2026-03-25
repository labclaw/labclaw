"""Tests for the LabClaw MCP server tools."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from labclaw.brain.types import BrainResult, HealthStatus, ToolInfo

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_registry():
    """Reset brain module registry between tests."""
    import labclaw.brain as brain_mod

    brain_mod._registry = None
    yield
    brain_mod._registry = None


# ---------------------------------------------------------------------------
# labclaw_search_tools
# ---------------------------------------------------------------------------


class TestSearchTools:
    async def test_returns_all_tools(self):
        from labclaw.mcp.server import labclaw_search_tools

        tools = [
            ToolInfo(name="search_pubmed", description="Search PubMed", skill="tu"),
            ToolInfo(name="run_blast", description="Run BLAST query", skill="tu"),
        ]
        with patch(
            "labclaw.mcp.server.list_tools",
            new_callable=AsyncMock,
            return_value=tools,
        ):
            result = await labclaw_search_tools()

        parsed = json.loads(result)
        assert len(parsed) == 2
        assert parsed[0]["name"] == "search_pubmed"

    async def test_filters_by_query(self):
        from labclaw.mcp.server import labclaw_search_tools

        tools = [
            ToolInfo(name="search_pubmed", description="Search PubMed", skill="tu"),
            ToolInfo(name="run_blast", description="Run BLAST query", skill="tu"),
        ]
        with patch(
            "labclaw.mcp.server.list_tools",
            new_callable=AsyncMock,
            return_value=tools,
        ):
            result = await labclaw_search_tools(query="blast")

        parsed = json.loads(result)
        assert len(parsed) == 1
        assert parsed[0]["name"] == "run_blast"

    async def test_filters_by_description(self):
        from labclaw.mcp.server import labclaw_search_tools

        tools = [
            ToolInfo(name="tool1", description="Search PubMed articles", skill="s"),
            ToolInfo(name="tool2", description="Protein folding", skill="s"),
        ]
        with patch(
            "labclaw.mcp.server.list_tools",
            new_callable=AsyncMock,
            return_value=tools,
        ):
            result = await labclaw_search_tools(query="pubmed")

        parsed = json.loads(result)
        assert len(parsed) == 1
        assert parsed[0]["name"] == "tool1"

    async def test_passes_category(self):
        from labclaw.mcp.server import labclaw_search_tools

        with patch(
            "labclaw.mcp.server.list_tools",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_lt:
            await labclaw_search_tools(category="biology")

        mock_lt.assert_awaited_once_with(category="biology")

    async def test_empty_result(self):
        from labclaw.mcp.server import labclaw_search_tools

        with patch(
            "labclaw.mcp.server.list_tools",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await labclaw_search_tools()

        assert json.loads(result) == []


# ---------------------------------------------------------------------------
# labclaw_execute_tool
# ---------------------------------------------------------------------------


class TestExecuteTool:
    async def test_execute_with_json_arguments(self):
        from labclaw.mcp.server import labclaw_execute_tool

        expected = BrainResult(success=True, data={"pmids": [1, 2]})
        with patch(
            "labclaw.mcp.server.execute",
            new_callable=AsyncMock,
            return_value=expected,
        ) as mock_ex:
            result = await labclaw_execute_tool("search_pubmed", '{"query": "CRISPR"}')

        parsed = json.loads(result)
        assert parsed["success"] is True
        assert parsed["data"]["pmids"] == [1, 2]
        mock_ex.assert_awaited_once_with("search_pubmed", query="CRISPR")

    async def test_execute_with_default_arguments(self):
        from labclaw.mcp.server import labclaw_execute_tool

        expected = BrainResult(success=True, data="ok")
        with patch(
            "labclaw.mcp.server.execute",
            new_callable=AsyncMock,
            return_value=expected,
        ) as mock_ex:
            result = await labclaw_execute_tool("some_tool")

        parsed = json.loads(result)
        assert parsed["success"] is True
        mock_ex.assert_awaited_once_with("some_tool")

    async def test_execute_failure(self):
        from labclaw.mcp.server import labclaw_execute_tool

        expected = BrainResult(success=False, error="Tool not found")
        with patch(
            "labclaw.mcp.server.execute",
            new_callable=AsyncMock,
            return_value=expected,
        ):
            result = await labclaw_execute_tool("nonexistent")

        parsed = json.loads(result)
        assert parsed["success"] is False
        assert parsed["error"] == "Tool not found"


# ---------------------------------------------------------------------------
# labclaw_reason
# ---------------------------------------------------------------------------


class TestReason:
    async def test_reason_success(self):
        from labclaw.mcp.server import labclaw_reason

        expected = BrainResult(success=True, data="CRISPR is a gene editing tool.")
        with patch(
            "labclaw.mcp.server.reason",
            new_callable=AsyncMock,
            return_value=expected,
        ) as mock_r:
            result = await labclaw_reason("What is CRISPR?")

        assert result == "CRISPR is a gene editing tool."
        mock_r.assert_awaited_once_with("What is CRISPR?", domain="general")

    async def test_reason_failure(self):
        from labclaw.mcp.server import labclaw_reason

        expected = BrainResult(success=False, error="No LLM configured")
        with patch(
            "labclaw.mcp.server.reason",
            new_callable=AsyncMock,
            return_value=expected,
        ):
            result = await labclaw_reason("Q?")

        assert result == "Error: No LLM configured"

    async def test_reason_with_domain(self):
        from labclaw.mcp.server import labclaw_reason

        expected = BrainResult(success=True, data="answer")
        with patch(
            "labclaw.mcp.server.reason",
            new_callable=AsyncMock,
            return_value=expected,
        ) as mock_r:
            await labclaw_reason("Q?", domain="neuroscience")

        mock_r.assert_awaited_once_with("Q?", domain="neuroscience")


# ---------------------------------------------------------------------------
# labclaw_write
# ---------------------------------------------------------------------------


class TestWrite:
    async def test_write_success(self):
        from labclaw.mcp.server import labclaw_write

        expected = BrainResult(success=True, data="Abstract text here.")
        with patch(
            "labclaw.mcp.server.write",
            new_callable=AsyncMock,
            return_value=expected,
        ) as mock_w:
            result = await labclaw_write(section="abstract", context="CRISPR study")

        assert result == "Abstract text here."
        mock_w.assert_awaited_once_with(section="abstract", context="CRISPR study")

    async def test_write_failure(self):
        from labclaw.mcp.server import labclaw_write

        expected = BrainResult(success=False, error="No LLM provider")
        with patch(
            "labclaw.mcp.server.write",
            new_callable=AsyncMock,
            return_value=expected,
        ):
            result = await labclaw_write(section="methods", context="ctx")

        assert result == "Error: No LLM provider"


# ---------------------------------------------------------------------------
# labclaw_health
# ---------------------------------------------------------------------------


class TestHealth:
    async def test_health_returns_json(self):
        from labclaw.mcp.server import labclaw_health

        expected = HealthStatus(
            status="ok",
            skills={"tooluniverse": True},
            tool_count=10,
            version="0.0.1",
        )
        with patch(
            "labclaw.mcp.server.health",
            new_callable=AsyncMock,
            return_value=expected,
        ):
            result = await labclaw_health()

        parsed = json.loads(result)
        assert parsed["status"] == "ok"
        assert parsed["tool_count"] == 10
        assert parsed["skills"]["tooluniverse"] is True
