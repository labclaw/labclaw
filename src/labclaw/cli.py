"""LabClaw CLI — main entry point."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="labclaw",
        description="Cloud Brain — 2400+ scientific tools",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("demo", help="Run a real ToolUniverse query")

    brain_p = sub.add_parser("brain", help="Start Cloud Brain REST API")
    brain_p.add_argument("--port", type=int, default=18802)

    sub.add_parser("mcp", help="Start MCP server for Claude Desktop")

    tools_p = sub.add_parser("tools", help="List available tools")
    tools_p.add_argument("--category", default="")

    args = parser.parse_args()

    if args.command == "demo":
        asyncio.run(_demo())
    elif args.command == "brain":
        _start_brain(args.port)
    elif args.command == "mcp":
        _start_mcp()
    elif args.command == "tools":
        asyncio.run(_list_tools(args.category))
    else:
        parser.print_help()
        sys.exit(1)


async def _demo() -> None:
    """Run a demo ToolUniverse query."""
    from labclaw.brain import execute

    print("Cloud Brain Demo — searching PubMed for CRISPR...")
    result = await execute("search_pubmed", query="CRISPR")
    print(json.dumps(result.model_dump(), indent=2, default=str))


def _start_brain(port: int) -> None:
    """Start the Cloud Brain REST API server."""
    import uvicorn

    from labclaw.brain.server import app

    print(f"Starting Cloud Brain on port {port}...")
    uvicorn.run(app, host="127.0.0.1", port=port)


def _start_mcp() -> None:
    """Start the MCP server (stdio transport)."""
    from labclaw.mcp.server import mcp

    mcp.run(transport="stdio")


async def _list_tools(category: str) -> None:
    """List available tools in terminal."""
    from labclaw.brain import list_tools

    tools = await list_tools(category=category)
    if not tools:
        print("No tools available.")
        return
    print(f"{'TOOL':<35} {'SKILL':<15} {'CATEGORY':<15} DESCRIPTION")
    print("-" * 100)
    for t in tools:
        desc = t.description[:35] if len(t.description) > 35 else t.description
        print(f"{t.name:<35} {t.skill:<15} {t.category:<15} {desc}")
    print(f"\nTotal: {len(tools)} tools")


if __name__ == "__main__":
    main()
