# Contributing to LabClaw

Thank you for your interest in contributing to LabClaw! This guide will help you get started.

## Table of Contents

- [Development Setup](#development-setup)
- [Running Tests](#running-tests)
- [Code Style](#code-style)
- [Type Checking](#type-checking)
- [Pull Request Process](#pull-request-process)
- [Architecture Overview](#architecture-overview)
- [Plugin Development](#plugin-development)
- [Code Review Expectations](#code-review-expectations)
- [Good First Contributions](#good-first-contributions)

## Development Setup

LabClaw requires **Python 3.11+** and uses [uv](https://docs.astral.sh/uv/) for dependency management.

```bash
# Clone the repository
git clone https://github.com/labclaw/labclaw.git
cd labclaw

# Install with dev and science dependencies
uv sync --extra dev --extra science

# Or use make
make dev-install

# Install pre-commit hooks
uv run pre-commit install
```

### Optional dependency groups

| Group | What it adds | Install |
|-------|-------------|---------|
| `dev` | pytest, ruff, mypy, pre-commit | `uv sync --extra dev` |
| `science` | numpy, scipy, scikit-learn, statsmodels, umap | `uv sync --extra science` |
| `nwb` | pynwb, hdmf, neuroconv | `uv sync --extra nwb` |
| `memory` | graphiti-core, sentence-transformers | `uv sync --extra memory` |

For full development, use:

```bash
uv sync --extra dev --extra science
```

## Running Tests

```bash
# Full test suite with coverage (100% minimum enforced)
make test

# Quick run without coverage
uv run pytest -q

# Run specific test file
uv run pytest tests/unit/core/test_graph.py -v

# Run only BDD feature tests
uv run pytest tests/features/ -v

# Run only fast tests (skip slow/integration)
uv run pytest -m "not slow and not integration" -q

# Generate HTML coverage report
make coverage-html
```

Test files mirror the source structure:

```
src/labclaw/core/graph.py      → tests/unit/core/test_graph.py
src/labclaw/memory/search.py   → tests/unit/memory/test_search.py
```

BDD features live under `tests/features/layer{N}_{name}/`.

## Code Style

We use [ruff](https://docs.astral.sh/ruff/) for linting and formatting.

```bash
# Check for lint errors
make lint

# Auto-fix and format
make format
```

### Rules

- **Line length:** 100 characters
- **Lint rules:** E, F, I, N, W, UP (see `pyproject.toml` for per-file overrides)
- **Import order:** standard library → third-party → local (ruff isort-compatible)
- **Type hints** required on all public function signatures (parameters + return type)
- **Pydantic models** for all data schemas
- **`pathlib.Path`** for file paths, never raw strings
- **`from __future__ import annotations`** in every module
- **Docstrings** on public API only; no comments on obvious code
- **Timestamps:** ISO 8601; filenames use `YYYYMMDD_HHMMSS`

## Type Checking

```bash
# Run mypy
uv run mypy src/labclaw/

# Run on a specific module
uv run mypy src/labclaw/core/
```

Key typing conventions:

- Use `X | None` instead of `Optional[X]`
- Use `collections.abc` types (`Sequence`, `Mapping`) over `typing` equivalents
- Use `typing.Protocol` for interface definitions

## Pull Request Process

1. **Create a branch** from `main`:
   ```bash
   git checkout -b feat/my-feature main
   ```

2. **Write tests first** — all new behavior needs test coverage.

3. **Implement the change** — keep PRs focused and small.

4. **Run the full check suite:**
   ```bash
   make lint && make test
   ```

5. **Write a clear PR description:**
   - Use the PR template (filled automatically)
   - Title format: `module: short summary` (e.g., `discovery: add temporal pattern mining`)
   - Describe *what* changed and *why*

6. **Respond to review feedback** — all PRs require at least one approval.

### Branch naming

| Prefix | Use |
|--------|-----|
| `feat/` | New features |
| `fix/` | Bug fixes |
| `docs/` | Documentation only |
| `refactor/` | Code restructuring (no behavior change) |
| `test/` | Test additions or fixes |

## Architecture Overview

LabClaw is organized as a 5-layer stack:

```
Layer 5: PERSONA & DIGITAL STAFF — Human + AI members
Layer 4: MEMORY                  — Three-tier memory system
Layer 3: ENGINE                  — Scientific method loop
Layer 2: SOFTWARE INFRA          — API, event bus, dashboard
Layer 1: HARDWARE                — Device interfaces, safety
```

Key design principles:

- **Protocol-based interfaces** — hardware adapters, plugins, and providers implement `typing.Protocol`
- **Event-driven communication** — modules publish/subscribe via `{layer}.{module}.{action}` events
- **Pydantic-first schemas** — `LabEvent`, `GraphNode`, `StepContext` in `core/schemas.py`
- **Plugin extensibility** — entry-point based discovery (`labclaw.plugins` group)

For the full architecture document, see [docs/architecture.md](docs/architecture.md).

## Plugin Development

LabClaw supports three plugin types:

| Type | Protocol | What it adds |
|------|----------|-------------|
| `device` | `DevicePlugin` | New hardware drivers |
| `domain` | `DomainPlugin` | Domain-specific schemas, sentinel rules, hypothesis templates |
| `analysis` | `AnalysisPlugin` | New mining algorithms and validators |

Scaffold a new plugin:

```bash
labclaw plugin create my-pack --type domain
```

Plugins are discovered via Python entry points. Register in your `pyproject.toml`:

```toml
[project.entry-points."labclaw.plugins"]
my_plugin = "my_package:create_plugin"
```

See `src/labclaw/plugins/` for the plugin loader and protocol definitions.

## Code Review Expectations

All PRs go through code review. Reviewers look for:

- **Correctness** — does the code do what it claims?
- **Test coverage** — are edge cases tested? Is coverage = 100%?
- **Type safety** — are public functions properly annotated?
- **Schema validation** — are new data types using Pydantic models?
- **Error handling** — no bare `except`, no silently swallowed errors
- **Security** — no credentials in code, validate at boundaries
- **Simplicity** — is this the simplest solution that works?

## Good First Contributions

If you're new to the project, these are good starting points:

- Add tests for uncovered edge cases (check `make coverage-html` for gaps)
- Improve error messages in API endpoints
- Add examples for new lab modalities or instruments
- Write BDD feature tests for existing behavior
- Fix documentation typos or add clarifications

Look for issues labeled [`good first issue`](https://github.com/labclaw/labclaw/labels/good%20first%20issue).

## Questions?

Open a [discussion](https://github.com/labclaw/labclaw/discussions) for questions, ideas, or design proposals.
