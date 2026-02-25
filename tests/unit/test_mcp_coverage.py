"""Coverage tests for src/labclaw/mcp/server.py.

Discover exception/empty path, hypothesize, list_findings, main().
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

try:
    from labclaw.mcp.server import create_server, main

    _HAS_MCP = True
except ImportError:
    _HAS_MCP = False
    create_server = None  # type: ignore[assignment, misc]
    main = None  # type: ignore[assignment]

pytestmark = pytest.mark.skipif(not _HAS_MCP, reason="mcp package not installed")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _call_tool(server: Any, name: str, **kwargs: Any) -> str:
    """Invoke a tool by name on a FastMCP server instance."""
    tool_mgr = server._tool_manager
    tool = tool_mgr._tools[name]
    return tool.fn(**kwargs)


# ---------------------------------------------------------------------------
# discover tool — Lines 77-78, 80: exception handler sets rows=[], then early return
# ---------------------------------------------------------------------------


class TestDiscoverToolExceptionAndEmptyRows:
    def test_discover_exception_in_get_session_chronicle_returns_no_data_message(self) -> None:
        """Lines 77-78: get_session_chronicle() raises → rows=[], then early return (line 80)."""
        mock_miner = MagicMock()

        with (
            patch("labclaw.mcp.server._get_pattern_miner", return_value=mock_miner),
            patch(
                "labclaw.api.deps.get_session_chronicle",
                side_effect=RuntimeError("chronicle unavailable"),
            ),
        ):
            server = create_server()
            result = _call_tool(server, "discover")

        parsed = json.loads(result)
        assert parsed["patterns"] == []
        assert "No experiment data available" in parsed["message"]
        # Miner.mine should NOT have been called
        mock_miner.mine.assert_not_called()

    def test_discover_empty_rows_returns_no_data_message(self) -> None:
        """Line 80: when rows is falsy (e.g. empty list), returns no-data JSON."""
        mock_miner = MagicMock()
        # get_session_chronicle returns a truthy object that is not iterable as rows,
        # but the code checks `if not rows:`. We make it return an object that evaluates to False.
        falsy_chronicle = MagicMock()
        falsy_chronicle.__bool__ = MagicMock(return_value=False)

        with (
            patch("labclaw.mcp.server._get_pattern_miner", return_value=mock_miner),
            patch("labclaw.api.deps.get_session_chronicle", return_value=falsy_chronicle),
        ):
            server = create_server()
            result = _call_tool(server, "discover")

        parsed = json.loads(result)
        assert parsed["patterns"] == []
        mock_miner.mine.assert_not_called()

    def test_discover_with_session_data_runs_mining(self) -> None:
        """Lines 84-86, 99-100: sessions exist → iterate, build rows, mine."""
        mock_session = MagicMock()
        mock_session.model_dump.return_value = {"x": 1.0, "y": 2.0, "session_id": "s1"}

        mock_chronicle = MagicMock()
        mock_chronicle.list_sessions.return_value = [mock_session] * 15

        mock_result = MagicMock()
        mock_result.model_dump.return_value = {"patterns": [], "run_at": "now"}

        mock_miner = MagicMock()
        mock_miner.mine.return_value = mock_result

        with (
            patch("labclaw.mcp.server._get_pattern_miner", return_value=mock_miner),
            patch("labclaw.api.deps.get_session_chronicle", return_value=mock_chronicle),
        ):
            server = create_server()
            result = _call_tool(server, "discover")

        mock_miner.mine.assert_called_once()
        assert "patterns" in result


# ---------------------------------------------------------------------------
# hypothesize — Lines 77-78: get_latest_patterns succeeds (non-empty patterns)
# ---------------------------------------------------------------------------


class TestHypothesizeToolPaths:
    def test_hypothesize_with_context_and_constraints(self) -> None:
        """Lines 99-112: pass context and constraints, generator returns results."""
        hyp = MagicMock()
        hyp.model_dump.return_value = {
            "hypothesis_id": "h1",
            "statement": "neurons fire when stimulus",
            "confidence": 0.8,
        }
        mock_gen = MagicMock()
        mock_gen.generate.return_value = [hyp]

        with patch("labclaw.mcp.server._get_hypothesis_generator", return_value=mock_gen):
            server = create_server()
            result = _call_tool(
                server,
                "hypothesize",
                context="neuroscience domain",
                constraints="within-session,p<0.05",
            )

        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert len(parsed) == 1
        assert parsed[0]["statement"] == "neurons fire when stimulus"

    def test_hypothesize_get_latest_patterns_import_error(self) -> None:
        """Line 77-78: ImportError from get_latest_patterns → patterns = [] (empty list path)."""
        hyp = MagicMock()
        hyp.model_dump.return_value = {"hypothesis_id": "h2", "statement": "fallback"}
        mock_gen = MagicMock()
        mock_gen.generate.return_value = [hyp]

        with (
            patch("labclaw.mcp.server._get_hypothesis_generator", return_value=mock_gen),
            # Patch the import inside the tool to raise ImportError
            patch(
                "labclaw.api.deps.get_latest_patterns",
                side_effect=ImportError("no attr"),
                create=True,
            ),
        ):
            server = create_server()
            result = _call_tool(server, "hypothesize", context="", constraints="")

        parsed = json.loads(result)
        assert isinstance(parsed, list)

    def test_hypothesize_no_constraints(self) -> None:
        """Line 80: empty constraints string produces empty constraint_list."""
        mock_gen = MagicMock()
        mock_gen.generate.return_value = []

        with patch("labclaw.mcp.server._get_hypothesis_generator", return_value=mock_gen):
            server = create_server()
            result = _call_tool(server, "hypothesize", context="", constraints="")

        parsed = json.loads(result)
        assert parsed == []

        # Verify generate was called with empty constraints list
        call_args = mock_gen.generate.call_args[0][0]
        assert call_args.constraints == []

    def test_hypothesize_with_multiple_constraints(self) -> None:
        """Comma-separated constraints are split correctly."""
        mock_gen = MagicMock()
        mock_gen.generate.return_value = []

        with patch("labclaw.mcp.server._get_hypothesis_generator", return_value=mock_gen):
            server = create_server()
            _call_tool(server, "hypothesize", context="", constraints="a, b , c")

        call_args = mock_gen.generate.call_args[0][0]
        assert call_args.constraints == ["a", "b", "c"]


# ---------------------------------------------------------------------------
# list_findings — Line 103: returns matching results
# ---------------------------------------------------------------------------


class TestListFindingsTool:
    def test_list_findings_returns_results(self) -> None:
        """Line 103: list_findings searches with 'finding discovery hypothesis result'."""
        r1 = SimpleNamespace(
            entity_id="e1",
            snippet="neurons correlate with behavior",
            score=0.9,
            source_tier="a",
            source_detail="MEMORY.md",
        )
        r2 = SimpleNamespace(
            entity_id="e2",
            snippet="hypothesis confirmed at p=0.01",
            score=0.7,
            source_tier="a",
            source_detail="lab/soul",
        )
        mock_engine = MagicMock()
        mock_engine.search.return_value = [r1, r2]

        with patch("labclaw.mcp.server._get_search_engine", return_value=mock_engine):
            server = create_server()
            result = _call_tool(server, "list_findings", limit=5)

        parsed = json.loads(result)
        assert len(parsed) == 2
        assert parsed[0]["entity_id"] == "e1"
        assert parsed[1]["snippet"] == "hypothesis confirmed at p=0.01"

    def test_list_findings_empty(self) -> None:
        """list_findings with no results returns empty list."""
        mock_engine = MagicMock()
        mock_engine.search.return_value = []

        with patch("labclaw.mcp.server._get_search_engine", return_value=mock_engine):
            server = create_server()
            result = _call_tool(server, "list_findings", limit=10)

        assert json.loads(result) == []

    def test_list_findings_uses_correct_query(self) -> None:
        """list_findings passes the findings query to the search engine."""
        from labclaw.memory.search import HybridSearchQuery

        mock_engine = MagicMock()
        mock_engine.search.return_value = []

        with patch("labclaw.mcp.server._get_search_engine", return_value=mock_engine):
            server = create_server()
            _call_tool(server, "list_findings", limit=7)

        call_args = mock_engine.search.call_args[0][0]
        assert isinstance(call_args, HybridSearchQuery)
        assert "finding" in call_args.text
        assert call_args.limit == 7


# ---------------------------------------------------------------------------
# main() — Lines 201-202
# ---------------------------------------------------------------------------


class TestMainFunction:
    def test_main_calls_server_run_with_stdio(self) -> None:
        """main() creates a server and calls server.run(transport='stdio')."""
        mock_server = MagicMock()

        with patch("labclaw.mcp.server.create_server", return_value=mock_server):
            main()

        mock_server.run.assert_called_once_with(transport="stdio")


# ---------------------------------------------------------------------------
# _get_provenance_for_entity — lines 55-64
# ---------------------------------------------------------------------------


class TestGetProvenanceForEntity:
    def test_returns_chain_dict_when_found(self) -> None:
        """Line 61: chain found → model_dump(mode='json') returned."""
        from labclaw.api.routers import provenance as prov_module
        from labclaw.mcp.server import _get_provenance_for_entity
        from labclaw.validation.statistics import ProvenanceChain, ProvenanceStep

        prov_module._chains.clear()
        chain = ProvenanceChain(
            finding_id="f1",
            steps=[ProvenanceStep(node_id="n1", node_type="obs", description="d")],
        )
        prov_module._chains["f1"] = chain

        result = _get_provenance_for_entity("f1")
        assert result is not None
        assert result["finding_id"] == "f1"
        prov_module._chains.clear()

    def test_returns_none_when_not_found(self) -> None:
        """Line 60: chain is None → return None."""
        from labclaw.api.routers import provenance as prov_module
        from labclaw.mcp.server import _get_provenance_for_entity

        prov_module._chains.clear()
        result = _get_provenance_for_entity("no-such-id")
        assert result is None

    def test_returns_none_on_general_exception(self) -> None:
        """Lines 62-64: exception inside the try block → except catches, returns None."""
        from labclaw.api.routers import provenance as prov_module
        from labclaw.mcp.server import _get_provenance_for_entity
        from labclaw.validation.statistics import ProvenanceChain

        bad_chain = MagicMock(spec=ProvenanceChain)
        bad_chain.model_dump.side_effect = RuntimeError("serialisation error")
        prov_module._chains["bad-id"] = bad_chain

        result = _get_provenance_for_entity("bad-id")
        assert result is None
        prov_module._chains.clear()


# ---------------------------------------------------------------------------
# provenance MCP tool — lines 267-287
# ---------------------------------------------------------------------------


class TestProvenanceTool:
    def test_provenance_tool_no_chain_returns_message(self) -> None:
        """Lines 267-279: finding_id not registered → returns informative message."""
        from labclaw.api.routers import provenance as prov_module

        prov_module._chains.clear()
        server = create_server()
        result = _call_tool(server, "provenance", finding_id="unknown-finding")
        parsed = json.loads(result)
        assert parsed["chain"] is None
        assert "No provenance chain registered" in parsed["message"]
        assert parsed["finding_id"] == "unknown-finding"

    def test_provenance_tool_with_chain_returns_chain(self) -> None:
        """Lines 280-287: finding_id registered → chain dict returned."""
        from labclaw.api.routers import provenance as prov_module
        from labclaw.validation.statistics import ProvenanceChain, ProvenanceStep

        prov_module._chains.clear()
        chain = ProvenanceChain(
            finding_id="f-mcp",
            steps=[ProvenanceStep(node_id="n1", node_type="obs", description="raw data")],
        )
        prov_module._chains["f-mcp"] = chain

        server = create_server()
        result = _call_tool(server, "provenance", finding_id="f-mcp")
        parsed = json.loads(result)
        assert parsed["finding_id"] == "f-mcp"
        assert parsed["chain"] is not None
        assert parsed["chain"]["finding_id"] == "f-mcp"
        prov_module._chains.clear()
