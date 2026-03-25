# CLAUDE.md — LabClaw

## Project Overview

LabClaw is a unified gateway to 2400+ scientific tools, accessible via Python SDK, REST API, MCP (Claude Desktop), and CLI.

**Tech stack:** Python 3.11+, FastAPI, Pydantic 2, MCP (FastMCP), ToolUniverse SDK
**Version:** 0.0.1

## Build & Test

```bash
make dev-install
make test                    # unit tests, 100% coverage
make test-integration        # real ToolUniverse API calls
make test-mcp               # MCP stdio tests
make lint
```

## Architecture

```
src/labclaw/
├── brain/
│   ├── __init__.py          # Public API: execute, list_tools, reason, write, health
│   ├── types.py             # BrainResult, ToolInfo, HealthStatus
│   ├── skills/
│   │   ├── base.py          # CloudSkill protocol
│   │   ├── registry.py      # SkillRegistry
│   │   ├── tooluniverse.py  # 2000+ scientific tools
│   │   ├── lifesci.py       # Life science reasoning
│   │   └── write.py         # Scientific writing
│   └── server.py            # FastAPI REST gateway
├── mcp/server.py            # MCP server for Claude Desktop
├── llm/provider.py          # LLM provider protocol
├── cli.py                   # CLI: demo, brain, mcp, tools
├── config.py                # YAML config loading
└── __init__.py              # __version__
```

## Code Style

- ruff (line-length 100)
- Type hints on all public functions
- Pydantic models for all data schemas
- `from __future__ import annotations` in every module
- Async for all I/O operations

## Testing

- TDD: write failing test first
- 100% unit test coverage (`make test`)
- Integration tests with real APIs (`make test-integration`)
- MCP end-to-end tests (`make test-mcp`)

## Key Types

- `BrainResult(success, data, error)` — return type for all operations
- `ToolInfo(name, description, skill, category, parameters)` — tool metadata
- `HealthStatus(status, skills, tool_count, version)` — health report
- `CloudSkill` — Protocol for skill implementations
