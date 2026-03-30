"""Tests for MCP server main() function.

Covers line 55: mcp.run(transport="stdio") inside main().
"""

from __future__ import annotations

from unittest.mock import patch


class TestMcpServerMain:
    """Cover line 55: main() calls mcp.run()."""

    def test_main_calls_mcp_run(self) -> None:
        """main() delegates to mcp.run(transport='stdio')."""
        with patch("labclaw.mcp.server.mcp") as mock_mcp:
            from labclaw.mcp.server import main

            main()
            mock_mcp.run.assert_called_once_with(transport="stdio")
