"""Cover mcp/server.py uncovered line 55.

Line 55: main() calls mcp.run(transport="stdio").
"""

from __future__ import annotations

from unittest.mock import patch


class TestMcpMain:
    """main() invokes mcp.run with stdio transport."""

    def test_main_calls_mcp_run(self) -> None:
        from labclaw.mcp import server

        with patch.object(server.mcp, "run") as mock_run:
            server.main()
            mock_run.assert_called_once_with(transport="stdio")
