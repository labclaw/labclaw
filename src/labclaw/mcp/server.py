"""LabClaw MCP Server — expose Cloud Brain as MCP tools for Claude Desktop."""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from labclaw.brain import execute, health, list_tools, reason, write

mcp = FastMCP("labclaw", instructions="Cloud Brain — 2400+ scientific tools")


@mcp.tool()
async def labclaw_search_tools(query: str = "", category: str = "") -> str:
    """Find available scientific tools by keyword or category."""
    tools = await list_tools(category=category)
    if query:
        q = query.lower()
        tools = [t for t in tools if q in t.name.lower() or q in t.description.lower()]
    return json.dumps([t.model_dump() for t in tools], indent=2)


@mcp.tool()
async def labclaw_execute_tool(tool_name: str, arguments: str = "{}") -> str:
    """Execute a scientific tool by name. Pass arguments as JSON string."""
    args = json.loads(arguments) if isinstance(arguments, str) else arguments
    result = await execute(tool_name, **args)
    return json.dumps(result.model_dump(), indent=2)


@mcp.tool()
async def labclaw_reason(question: str, domain: str = "general") -> str:
    """Ask a life science domain question. Returns expert-level reasoning."""
    result = await reason(question, domain=domain)
    return result.data if result.success else f"Error: {result.error}"


@mcp.tool()
async def labclaw_write(section: str, context: str) -> str:
    """Generate a scientific writing section (abstract, methods, results, discussion)."""
    result = await write(section=section, context=context)
    return result.data if result.success else f"Error: {result.error}"


@mcp.tool()
async def labclaw_health() -> str:
    """Check Cloud Brain health and available skills."""
    status = await health()
    return json.dumps(status.model_dump(), indent=2)


def main() -> None:
    """Run MCP server via stdio transport."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
