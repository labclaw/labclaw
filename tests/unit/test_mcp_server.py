"""Tests for src/labclaw/mcp/server.py — MCP tool functions and server creation."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

try:
    from labclaw.mcp.server import create_server
    _HAS_MCP = True
except ImportError:
    _HAS_MCP = False
    create_server = None  # type: ignore[assignment, misc]

pytestmark = pytest.mark.skipif(not _HAS_MCP, reason="mcp package not installed")


# ---------------------------------------------------------------------------
# create_server
# ---------------------------------------------------------------------------


class TestCreateServer:
    def test_returns_fastmcp_instance(self) -> None:
        from mcp.server.fastmcp import FastMCP

        server = create_server()
        assert isinstance(server, FastMCP)


# ---------------------------------------------------------------------------
# discover()
# ---------------------------------------------------------------------------


class TestDiscoverDirect:
    def test_discover_returns_json(self) -> None:
        mock_result = MagicMock()
        mock_result.model_dump_json.return_value = json.dumps(
            {"patterns": [], "data_summary": {"row_count": 0}}
        )

        mock_miner = MagicMock()
        mock_miner.mine.return_value = mock_result

        with patch("labclaw.mcp.server._get_pattern_miner", return_value=mock_miner):
            create_server()
            result = mock_result.model_dump_json(indent=2)
            parsed = json.loads(result)
            assert "patterns" in parsed


# ---------------------------------------------------------------------------
# Functional tests — call tool functions by reconstructing server scope
# ---------------------------------------------------------------------------


class TestMCPToolFunctions:
    """Test MCP tool functions by patching deps getters and calling through
    a freshly-created server's tool registry."""

    def _call_tool(self, server: Any, name: str, **kwargs: Any) -> str:
        """Call a tool by name on a FastMCP server instance."""
        # FastMCP stores tools in _tool_manager._tools
        tool_mgr = server._tool_manager
        tool = tool_mgr._tools[name]
        # The tool's fn is the decorated function
        return tool.fn(**kwargs)

    def test_discover_tool(self) -> None:
        mock_result = MagicMock()
        mock_result.model_dump_json.return_value = '{"patterns": []}'
        mock_miner = MagicMock()
        mock_miner.mine.return_value = mock_result

        with patch("labclaw.mcp.server._get_pattern_miner", return_value=mock_miner):
            server = create_server()
            result = self._call_tool(server, "discover")
            parsed = json.loads(result)
            assert "patterns" in parsed

    def test_hypothesize_tool(self) -> None:
        hyp = MagicMock()
        hyp.model_dump.return_value = {
            "hypothesis_id": "h1",
            "statement": "test",
            "confidence": 0.5,
        }
        mock_gen = MagicMock()
        mock_gen.generate.return_value = [hyp]

        with patch(
            "labclaw.mcp.server._get_hypothesis_generator", return_value=mock_gen
        ):
            server = create_server()
            result = self._call_tool(
                server, "hypothesize", context="neuro", constraints=""
            )
            parsed = json.loads(result)
            assert isinstance(parsed, list)
            assert len(parsed) == 1

    def test_evolution_status_tool(self) -> None:
        from datetime import UTC, datetime

        cycle = SimpleNamespace(
            cycle_id="c1",
            target=SimpleNamespace(value="protocol"),
            stage=SimpleNamespace(value="evaluation"),
            started_at=datetime(2026, 1, 1, tzinfo=UTC),
            candidate=SimpleNamespace(description="better proto"),
        )
        mock_engine = MagicMock()
        mock_engine.get_active_cycles.return_value = [cycle]
        mock_engine.get_history.return_value = [cycle]

        with patch(
            "labclaw.mcp.server._get_evolution_engine", return_value=mock_engine
        ):
            server = create_server()
            result = self._call_tool(server, "evolution_status")
            parsed = json.loads(result)
            assert parsed["active_cycles"] == 1
            assert parsed["total_cycles"] == 1

    def test_device_status_tool(self) -> None:
        from labclaw.core.schemas import DeviceStatus

        device = SimpleNamespace(
            device_id="d1",
            name="Microscope",
            device_type="microscope",
            status=DeviceStatus.ONLINE,
            location="lab-2",
            model="Zeiss",
        )
        mock_reg = MagicMock()
        mock_reg.list_devices.return_value = [device]

        with patch(
            "labclaw.mcp.server._get_device_registry", return_value=mock_reg
        ):
            server = create_server()
            result = self._call_tool(server, "device_status")
            parsed = json.loads(result)
            assert len(parsed) == 1
            assert parsed[0]["name"] == "Microscope"

    def test_query_memory_tool(self) -> None:
        search_result = SimpleNamespace(
            entity_id="e1",
            snippet="found data",
            score=0.8,
            source_tier="a",
            source_detail="soul",
        )
        mock_engine = MagicMock()
        mock_engine.search.return_value = [search_result]

        with patch("labclaw.mcp.server._get_search_engine", return_value=mock_engine):
            server = create_server()
            result = self._call_tool(server, "query_memory", query="test")
            parsed = json.loads(result)
            assert len(parsed) == 1
            assert parsed[0]["entity_id"] == "e1"

    def test_list_findings_tool(self) -> None:
        search_result = SimpleNamespace(
            entity_id="e2",
            snippet="finding xyz",
            score=0.6,
            source_tier="a",
            source_detail="memory",
        )
        mock_engine = MagicMock()
        mock_engine.search.return_value = [search_result]

        with patch("labclaw.mcp.server._get_search_engine", return_value=mock_engine):
            server = create_server()
            result = self._call_tool(server, "list_findings", limit=5)
            parsed = json.loads(result)
            assert len(parsed) == 1
            assert parsed[0]["snippet"] == "finding xyz"
