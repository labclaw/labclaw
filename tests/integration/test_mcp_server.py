"""Integration tests for the LabClaw MCP server.

These tests verify the full MCP server endpoint behavior including:
- Tool registration and discovery
- Request/response handling
- JSON serialization
- Error handling
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from labclaw.brain.types import BrainResult, HealthStatus, ToolInfo
from labclaw.mcp.server import (
    labclaw_execute_tool,
    labclaw_health,
    labclaw_reason,
    labclaw_search_tools,
    labclaw_write,
    mcp,
)

# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_registry():
    """Reset brain module registry between tests."""
    import labclaw.brain as brain_mod

    brain_mod._registry = None
    yield
    brain_mod._registry = None


# -----------------------------------------------------------------------------
# MCP Server Integration Tests
# -----------------------------------------------------------------------------


class TestMcpServerIntegration:
    """Integration tests for MCP server endpoints."""

    async def test_search_tools_end_to_end(self):
        """Test labclaw_search_tools with full request/response cycle."""
        tools = [
            ToolInfo(name="search_pubmed", description="Search PubMed", skill="tu"),
            ToolInfo(name="run_blast", description="Run BLAST query", skill="tu"),
            ToolInfo(name="get_uniprot", description="Get UniProt entry", skill="tu"),
        ]

        with patch(
            "labclaw.mcp.server.list_tools",
            new_callable=AsyncMock,
            return_value=tools,
        ):
            # Test search without filters
            result = await labclaw_search_tools()
            parsed = json.loads(result)

            assert len(parsed) == 3
            assert all("name" in t and "description" in t for t in parsed)

            # Test search with query filter
            result = await labclaw_search_tools(query="blast")
            parsed = json.loads(result)
            assert len(parsed) == 1
            assert parsed[0]["name"] == "run_blast"

            # Test search with category filter
            result = await labclaw_search_tools(category="genomics")
            parsed = json.loads(result)
            assert isinstance(parsed, list)

    async def test_execute_tool_with_various_arguments(self):
        """Test labclaw_execute_tool handles different argument formats."""

        # Test with JSON string arguments
        with patch(
            "labclaw.mcp.server.execute",
            new_callable=AsyncMock,
            return_value=BrainResult(success=True, data={"result": "ok"}),
        ) as mock_exec:
            result = await labclaw_execute_tool(
                "search_pubmed",
                '{"query": "CRISPR", "max_results": 10}',
            )
            parsed = json.loads(result)
            assert parsed["success"] is True
            mock_exec.assert_awaited_once_with("search_pubmed", query="CRISPR", max_results=10)

        # Test with empty/default arguments
        with patch(
            "labclaw.mcp.server.execute",
            new_callable=AsyncMock,
            return_value=BrainResult(success=True, data="default result"),
        ) as mock_exec:
            result = await labclaw_execute_tool("some_tool")
            parsed = json.loads(result)
            assert parsed["success"] is True
            mock_exec.assert_awaited_once_with("some_tool")

        # Test with complex nested arguments
        with patch(
            "labclaw.mcp.server.execute",
            new_callable=AsyncMock,
            return_value=BrainResult(success=True, data={"nested": True}),
        ) as mock_exec:
            result = await labclaw_execute_tool(
                "complex_tool",
                '{"filters": {"date": "2024-01-01"}, "options": ["a", "b"]}',
            )
            parsed = json.loads(result)
            assert parsed["success"] is True
            mock_exec.assert_awaited_once_with(
                "complex_tool",
                filters={"date": "2024-01-01"},
                options=["a", "b"],
            )

    async def test_execute_tool_error_handling(self):
        """Test labclaw_execute_tool properly handles and returns errors."""

        error_cases = [
            ("Tool not found", "Tool not found"),
            ("Invalid arguments", "Invalid arguments provided"),
            ("Network error", "Failed to connect to external service"),
        ]

        for error_type, error_msg in error_cases:
            with patch(
                "labclaw.mcp.server.execute",
                new_callable=AsyncMock,
                return_value=BrainResult(success=False, error=error_msg),
            ):
                result = await labclaw_execute_tool("failing_tool", "{}")
                parsed = json.loads(result)

                assert parsed["success"] is False
                assert parsed["error"] == error_msg
                assert "data" in parsed

    async def test_health_endpoint_integration(self):
        """Test labclaw_health returns complete status information."""

        health_status = HealthStatus(
            status="ok",
            skills={"tooluniverse": True, "lifesci": True, "write": False},
            tool_count=2400,
            version="0.0.1",
        )

        with patch(
            "labclaw.mcp.server.health",
            new_callable=AsyncMock,
            return_value=health_status,
        ):
            result = await labclaw_health()
            parsed = json.loads(result)

            assert parsed["status"] == "ok"
            assert parsed["tool_count"] == 2400
            assert parsed["version"] == "0.0.1"
            assert parsed["skills"]["tooluniverse"] is True
            assert parsed["skills"]["lifesci"] is True
            assert parsed["skills"]["write"] is False

    async def test_health_degraded_status(self):
        """Test labclaw_health returns degraded when skills are unavailable."""

        health_status = HealthStatus(
            status="degraded",
            skills={"tooluniverse": False, "lifesci": False},
            tool_count=0,
            version="0.0.1",
        )

        with patch(
            "labclaw.mcp.server.health",
            new_callable=AsyncMock,
            return_value=health_status,
        ):
            result = await labclaw_health()
            parsed = json.loads(result)

            assert parsed["status"] == "degraded"
            assert parsed["tool_count"] == 0
            assert parsed["skills"]["tooluniverse"] is False

    async def test_reason_endpoint_integration(self):
        """Test labclaw_reason with different domains and error scenarios."""

        # Test successful reasoning
        with patch(
            "labclaw.mcp.server.reason",
            new_callable=AsyncMock,
            return_value=BrainResult(
                success=True,
                data=(
                    "CRISPR-Cas9 is a genome editing technology "
                    "derived from bacterial immune systems."
                ),
            ),
        ) as mock_reason:
            result = await labclaw_reason("What is CRISPR?", domain="genomics")
            assert "CRISPR-Cas9" in result
            mock_reason.assert_awaited_once_with("What is CRISPR?", domain="genomics")

        # Test reasoning with different domains
        domains = ["neuroscience", "chemistry", "general", "bioinformatics"]
        for domain in domains:
            with patch(
                "labclaw.mcp.server.reason",
                new_callable=AsyncMock,
                return_value=BrainResult(success=True, data=f"Answer for {domain}"),
            ) as mock_reason:
                result = await labclaw_reason("Test question?", domain=domain)
                assert result == f"Answer for {domain}"
                mock_reason.assert_awaited_once_with("Test question?", domain=domain)

        # Test reasoning failure
        with patch(
            "labclaw.mcp.server.reason",
            new_callable=AsyncMock,
            return_value=BrainResult(success=False, error="LLM provider not configured"),
        ):
            result = await labclaw_reason("What is DNA?")
            assert result.startswith("Error:")
            assert "LLM provider not configured" in result

    async def test_write_endpoint_integration(self):
        """Test labclaw_write with different section types."""

        sections = ["abstract", "methods", "results", "discussion", "intro"]

        for section in sections:
            with patch(
                "labclaw.mcp.server.write",
                new_callable=AsyncMock,
                return_value=BrainResult(
                    success=True,
                    data=f"Generated {section} content here.",
                ),
            ) as mock_write:
                result = await labclaw_write(
                    section=section,
                    context="We performed RNA-seq on 3 replicates of wild-type and mutant mice.",
                )
                assert result == f"Generated {section} content here."
                mock_write.assert_awaited_once_with(
                    section=section,
                    context="We performed RNA-seq on 3 replicates of wild-type and mutant mice.",
                )

        # Test write failure
        with patch(
            "labclaw.mcp.server.write",
            new_callable=AsyncMock,
            return_value=BrainResult(success=False, error="No LLM provider available"),
        ):
            result = await labclaw_write(section="abstract", context="test")
            assert result.startswith("Error:")
            assert "No LLM provider available" in result


class TestMcpServerJsonHandling:
    """Tests for JSON serialization edge cases."""

    async def test_json_serialization_with_special_characters(self):
        """Test that special characters are properly JSON encoded."""

        tools = [
            ToolInfo(
                name="tool_with_quotes",
                description='Tool with "quotes" and \\ backslashes',
                skill="tu",
            ),
        ]

        with patch(
            "labclaw.mcp.server.list_tools",
            new_callable=AsyncMock,
            return_value=tools,
        ):
            result = await labclaw_search_tools()
            parsed = json.loads(result)

            assert len(parsed) == 1
            assert '"quotes"' in parsed[0]["description"]
            assert "\\" in parsed[0]["description"]

    async def test_json_serialization_with_unicode(self):
        """Test that unicode characters are properly handled."""

        tools = [
            ToolInfo(
                name="unicode_tool",
                description="Tool with unicode: α β γ δ ε",
                skill="tu",
            ),
        ]

        with patch(
            "labclaw.mcp.server.list_tools",
            new_callable=AsyncMock,
            return_value=tools,
        ):
            result = await labclaw_search_tools()
            parsed = json.loads(result)

            assert "α β γ δ ε" in parsed[0]["description"]

    async def test_execute_with_malformed_json_arguments(self):
        """Test handling of malformed JSON in arguments."""

        # This should raise a JSON decode error
        with pytest.raises(json.JSONDecodeError):
            await labclaw_execute_tool("tool_name", "{invalid json}")


class TestMcpServerToolDiscovery:
    """Tests for MCP server tool discovery and metadata."""

    def test_mcp_server_has_registered_tools(self):
        """Verify that the MCP server has the expected tools registered."""

        registered_tools = list(mcp._tool_manager._tools.keys())

        expected_tools = [
            "labclaw_search_tools",
            "labclaw_execute_tool",
            "labclaw_reason",
            "labclaw_write",
            "labclaw_health",
        ]

        for tool_name in expected_tools:
            assert tool_name in registered_tools, f"Tool {tool_name} not registered"

    def test_mcp_server_instructions(self):
        """Verify MCP server has proper instructions."""

        assert mcp.instructions is not None
        assert "Cloud Brain" in mcp.instructions
        assert "2400" in mcp.instructions or "scientific" in mcp.instructions
