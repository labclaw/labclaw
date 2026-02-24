"""LabClaw MCP Server — expose lab intelligence as MCP tools."""

from __future__ import annotations


def __getattr__(name: str):  # noqa: ANN001, ANN202
    if name == "create_server":
        from labclaw.mcp.server import create_server
        return create_server
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["create_server"]
