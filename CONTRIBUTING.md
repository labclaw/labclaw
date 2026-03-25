# Contributing to LabClaw

Thank you for your interest in contributing to LabClaw!

## Development Setup

LabClaw requires **Python 3.11+** and uses [uv](https://docs.astral.sh/uv/) for dependency management.

```bash
# Clone the repository
git clone https://github.com/labclaw/labclaw.git
cd labclaw

# Install all development dependencies
make dev-install
# Or manually:
uv sync --extra dev --extra tooluniverse --extra llm

# Install pre-commit hooks
uv run pre-commit install
```

### Optional dependency groups

| Group | What it adds | Install |
|-------|-------------|---------|
| `dev` | pytest, ruff, mypy, pre-commit | `uv sync --extra dev` |
| `tooluniverse` | ToolUniverse SDK (2000+ scientific tools) | `uv sync --extra tooluniverse` |
| `llm` | Anthropic + OpenAI SDKs | `uv sync --extra llm` |

## Running Tests

```bash
# Unit tests with 100% coverage (required)
make test

# Integration tests (requires API keys)
make test-integration

# MCP server tests
make test-mcp

# Run a specific test file
PYTHONPATH=src uv run pytest tests/unit/test_config.py -v
```

## Code Style

We use [ruff](https://docs.astral.sh/ruff/) for linting and formatting.

```bash
make lint     # check only
make format   # auto-fix
```

### Rules

- **Line length:** 100 characters
- **Lint rules:** E, F, I, N, W, UP
- **Type hints** required on all public function signatures
- **Pydantic models** for all data schemas
- **`from __future__ import annotations`** in every module
- **Async** for all I/O operations

## Pull Request Process

1. Create a branch from `main`
2. Write tests first (TDD)
3. Implement the change
4. Run `make lint && make test`
5. Submit PR with a clear description

### Branch naming

| Prefix | Use |
|--------|-----|
| `feat/` | New features |
| `fix/` | Bug fixes |
| `docs/` | Documentation only |
| `refactor/` | Code restructuring |
| `test/` | Test additions or fixes |

## Questions?

Open a [discussion](https://github.com/labclaw/labclaw/discussions).
