"""Tests for the LabClaw CLI."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from labclaw.brain.types import BrainResult, ToolInfo

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
# --help
# ---------------------------------------------------------------------------


class TestHelp:
    def test_help_exits_zero(self):
        from labclaw.cli import main

        with patch("sys.argv", ["labclaw", "--help"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

    def test_no_command_exits_one(self):
        from labclaw.cli import main

        with patch("sys.argv", ["labclaw"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# demo
# ---------------------------------------------------------------------------


class TestDemo:
    def test_demo_calls_execute(self):
        from labclaw.cli import main

        expected = BrainResult(success=True, data={"pmids": [1]})
        with (
            patch("sys.argv", ["labclaw", "demo"]),
            patch(
                "labclaw.brain.execute",
                new_callable=AsyncMock,
                return_value=expected,
            ) as mock_ex,
            patch("builtins.print"),
        ):
            main()

        mock_ex.assert_awaited_once_with("search_pubmed", query="CRISPR")

    def test_demo_prints_result(self, capsys):
        from labclaw.cli import main

        expected = BrainResult(success=True, data="demo output")
        with (
            patch("sys.argv", ["labclaw", "demo"]),
            patch(
                "labclaw.brain.execute",
                new_callable=AsyncMock,
                return_value=expected,
            ),
        ):
            main()

        captured = capsys.readouterr()
        assert "demo output" in captured.out


# ---------------------------------------------------------------------------
# tools
# ---------------------------------------------------------------------------


class TestTools:
    def test_tools_lists_tools(self, capsys):
        from labclaw.cli import main

        tools = [
            ToolInfo(
                name="search_pubmed",
                description="Search PubMed",
                skill="tooluniverse",
                category="literature",
            ),
        ]
        with (
            patch("sys.argv", ["labclaw", "tools"]),
            patch(
                "labclaw.brain.list_tools",
                new_callable=AsyncMock,
                return_value=tools,
            ),
        ):
            main()

        captured = capsys.readouterr()
        assert "search_pubmed" in captured.out
        assert "Total: 1 tools" in captured.out

    def test_tools_passes_category(self):
        from labclaw.cli import main

        with (
            patch("sys.argv", ["labclaw", "tools", "--category", "biology"]),
            patch(
                "labclaw.brain.list_tools",
                new_callable=AsyncMock,
                return_value=[],
            ) as mock_lt,
            patch("builtins.print"),
        ):
            main()

        mock_lt.assert_awaited_once_with(category="biology")

    def test_tools_empty_output(self, capsys):
        from labclaw.cli import main

        with (
            patch("sys.argv", ["labclaw", "tools"]),
            patch(
                "labclaw.brain.list_tools",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            main()

        captured = capsys.readouterr()
        assert "No tools available" in captured.out


# ---------------------------------------------------------------------------
# brain
# ---------------------------------------------------------------------------


class TestBrain:
    def test_brain_starts_uvicorn(self):
        from labclaw.cli import main

        with (
            patch("sys.argv", ["labclaw", "brain", "--port", "9999"]),
            patch("uvicorn.run") as mock_run,
            patch("builtins.print"),
        ):
            main()

        mock_run.assert_called_once()
        _, kwargs = mock_run.call_args
        assert kwargs["port"] == 9999

    def test_brain_default_port(self):
        from labclaw.cli import main

        with (
            patch("sys.argv", ["labclaw", "brain"]),
            patch("uvicorn.run") as mock_run,
            patch("builtins.print"),
        ):
            main()

        mock_run.assert_called_once()
        _, kwargs = mock_run.call_args
        assert kwargs["port"] == 18802


# ---------------------------------------------------------------------------
# mcp
# ---------------------------------------------------------------------------


class TestMcp:
    def test_mcp_starts_server(self):
        from labclaw.cli import main

        with (
            patch("sys.argv", ["labclaw", "mcp"]),
            patch("labclaw.mcp.server.mcp") as mock_mcp,
        ):
            mock_mcp.run = lambda **kw: None
            main()
