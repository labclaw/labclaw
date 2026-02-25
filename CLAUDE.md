# CLAUDE.md — LabClaw

## Project Overview

LabClaw is a self-evolving agentic system that serves as the super brain for research laboratories. It encodes the complete scientific method as an autonomous computational loop, accumulates persistent memory that makes it increasingly effective over time, and serves each team member with personalized intelligence.

**Tech stack:** Python 3.11+, FastAPI, SQLite, Redis Streams, Claude API, Streamlit, Graphiti
**Domain:** Neuroscience (first vertical) — video behavior tracking, microscopy, electrophysiology, behavioral apparatus
**Design doc:** `docs/plans/2026-02-19-labclaw-design-v2.md`

## Build & Test

```bash
# Install all dependencies
make dev-install                    # or: uv sync --extra dev --extra science

# Run tests (100% coverage required — TDD enforced)
make test                           # or: uv run pytest --cov=labclaw --cov-fail-under=100 -q

# Lint and format
make lint                           # check only
make format                         # auto-fix

# Type checking
uv run mypy src/labclaw/

# Build package
make build
```

## Architecture (5 Layers)

```
Layer 5: PERSONA & DIGITAL STAFF — Human + AI members, training, promotion
Layer 4: MEMORY                  — Lab super brain (Markdown + Knowledge Graph + Shared Blocks)
Layer 3: ENGINE                  — Scientific method loop (OBSERVE→...→CONCLUDE)
Layer 2: SOFTWARE INFRA          — Gateway, Event Bus, API, Dashboard, Edge Nodes
Layer 1: HARDWARE                — Devices, interfaces, manager, safety
```

## Code Style

- **Linter:** `ruff` — rules: E, F, I, N, W, UP — line length 100
- **Type hints** required on all public function signatures (params + return)
- **Pydantic models** for all data schemas and experiment validation
- **`from __future__ import annotations`** in every module for forward references
- **`pathlib.Path`** for all file paths, never raw strings
- **Docstrings** only on public API; no comments on obvious code
- **Async**: use `async def` for all new DB operations (aiosqlite)
- **Timestamps:** ISO 8601 format; filenames with `YYYYMMDD_HHMMSS`
- **JSON:** always cast numpy `int64`/`float64` with `int()` / `float()` before `json.dumps()`

## Key Abstractions

- **Protocol-based design** — hardware interfaces, plugins, and adapters all use `typing.Protocol`
- **Event-driven** — modules communicate via `{layer}.{module}.{action}` events on Redis Streams (or in-memory bus)
- **Pydantic schemas** — `LabEvent`, `GraphNode`, `StepContext`, `CycleResult` are the core data types in `core/schemas.py`
- **Plugin registry** — entry-point based (`labclaw.plugins` group); three types: `DevicePlugin`, `DomainPlugin`, `AnalysisPlugin`
- **Governance engine** — role-based permissions + safety rules + immutable audit log
- **Three-tier memory** — Tier A (Markdown/git), Tier B (Knowledge Graph), Tier C (Agent Shared Blocks)

## Important Rules

- **Never modify existing test fixtures** — add new ones in `tests/fixtures/`
- **Always use async** for new database operations (aiosqlite backend)
- **No credentials in code** — use environment variables via `configs/`
- **All event/graph node schemas live in `core/`** — plugins extend via the registry
- **Validate at boundaries** (API input, file parsing) — trust internal code
- **Never silently catch exceptions** — log or re-raise with specific types

## Testing Strategy: TDD + BDD Dual-Layer

- **TDD (unit tests):** 100% code coverage required (`--cov-fail-under=100`). Tests in `tests/unit/`.
- **BDD (behavior specs):** Comprehensive Gherkin `.feature` files in `tests/features/`. BDD must cover **all** high-level features, conditions, branches, edge cases, and behaviors — not just happy paths. Every behavior the system exhibits should have a corresponding BDD scenario.
- **BDD coverage rule:** When adding new features or modifying behavior, always add/update BDD scenarios to cover: (a) happy path, (b) error/failure paths, (c) edge cases and boundary conditions, (d) all significant branches in business logic.
- **BDD organization:** `tests/features/layer{N}_{name}/` with `.feature` files + step definitions in `tests/features/step_definitions/`.

## Project Structure

```
src/labclaw/
├── core/           # Config, event bus, gateway, graph, registry, governance, evaluation
├── hardware/       # Device registry, manager, safety, interface adapters
├── memory/         # Markdown memory, knowledge graph (Graphiti), shared blocks, search
├── discovery/      # Mining, unsupervised, hypothesis generation, predictive modeling
├── optimization/   # Bayesian optimization, safety constraints, proposal, approval
├── validation/     # Statistics, cross-validation, provenance, report generation
├── evolution/      # Self-evolution engine, fitness scoring, candidate promotion
├── agents/         # Agent runtime, orchestrator, tool definitions
├── orchestrator/   # Top-level scientific method state machine
├── plugins/        # Plugin loader, registry, protocols, domain packs
├── llm/            # LLM provider abstraction (Anthropic, OpenAI, local)
├── edge/           # File watchers, quality checks, device adapters, CLI
├── api/            # REST API (FastAPI) on port 18800
├── dashboard/      # Streamlit dashboard on port 18801
└── mcp/            # MCP server (labclaw-mcp)
lab/                # Lab memory — Tier A: human-readable (SOUL.md, MEMORY.md, protocols/)
members/            # Per-member profiles — human + digital (SOUL.md, MEMORY.md)
devices/            # Per-device profiles (SOUL.md, MEMORY.md)
plugins/            # Extension plugins (devices, analysis, metrics, schemas)
tests/              # TDD unit tests + BDD behavior specs (dual-layer)
configs/            # Environment configs (YAML)
```

## File Naming Conventions

- Source mirrors: `src/labclaw/core/graph.py` → `tests/unit/core/test_graph.py`
- BDD features: `tests/features/layer{N}_{name}/test_{feature}.feature`
- Step definitions: `tests/features/step_definitions/{module}_steps.py`
- Integration tests: `tests/integration/test_{feature}.py`
- Config files: `configs/{environment}.yaml`

## PR Checklist

Before submitting a pull request, verify:

- [ ] `make lint` passes with no errors
- [ ] `make test` passes with 100% coverage
- [ ] Type hints on all new public functions
- [ ] Pydantic models for any new data schemas
- [ ] New tests for all behavior changes
- [ ] No credentials, tokens, or `.env` files committed
- [ ] Existing test fixtures unchanged (add new ones if needed)
- [ ] Docs updated if API or behavior changed

## Agent Team

### Routing Table

| Task Type | Agent | When to Use |
|-----------|-------|-------------|
| Feature planning, task breakdown, multi-agent coordination | tech-lead | Any new feature, complex bug, architecture decision |
| Core system: event bus, graph, API, config, gateway, registry | platform-engineer | Building/modifying core/*, api/*, configs/ |
| Memory system: markdown, knowledge graph, search, shared blocks | memory-engineer | Building/modifying memory/*, lab/*, members/* |
| Agent runtime, orchestrator, tool calling, LLM integration | agent-engineer | Building/modifying agents/runtime, orchestrator, prompts |
| Edge nodes, file watchers, quality checks, device adapters, gateway | edge-engineer | Building/modifying edge/*, gateway, adapters/ |
| Neuroscience domain: NWB, analysis pipelines, data schemas | neuro-specialist | NWB export, analysis pipeline design, schema definitions |
| Discovery pipeline: mining, hypothesis, modeling, optimization, validation | discovery-engineer | Building/modifying discovery/, optimization/, validation/ |
| Dashboard pages, Streamlit UI, visualization | platform-engineer | Building/modifying dashboard/ components |
| Code review, PR review, security audit | code-reviewer | All code changes before merge |

### Orchestration Protocol

1. **Tech-lead is the routing authority.** Complex tasks go to tech-lead first.
2. **Main agent never implements directly** for multi-step tasks — delegates to specialists.
3. **Handoff format:** (a) clear objective, (b) relevant file paths, (c) acceptance criteria, (d) next agent.
4. **Max 2 agents in parallel** to avoid file conflicts.
5. **Code reviewer is the quality gate** — all changes pass through code-reviewer.

## Scientific Method Mapping

| Step | Code Module | Function |
|------|-------------|----------|
| OBSERVE | edge/watcher, edge/quality | 24/7 capture + real-time QC |
| ASK | discovery/mining, discovery/unsupervised | Pattern mining, clustering |
| HYPOTHESIZE | discovery/hypothesis | LLM + stats → testable hypotheses |
| PREDICT | discovery/modeling | Predictive models, uncertainty |
| EXPERIMENT | optimization/* | Bayesian opt, safety, human approval |
| ANALYZE | all modules | Feature extraction |
| CONCLUDE | validation/* | Statistics, cross-val, provenance, reports |

## Memory Architecture

| Tier | Pattern | Purpose | Storage |
|------|---------|---------|---------|
| A: Human-Readable | OpenClaw | Protocols, decisions, failures, daily stream | Markdown files (git) |
| B: Knowledge Graph | Graphiti | Entities, relations, temporal tracking | FalkorDB/SQLite |
| C: Agent State | Letta | Shared blocks, per-agent workspace | In-memory + SQLite |

## Key Dependencies

- **Graphiti**: `graphiti-core` — temporal knowledge graph for lab memory
- **NWB**: `pynwb` + `hdmf` — Neurodata Without Borders export
- **NeuroConv**: Format conversion from 47+ neuroscience formats
- **watchdog**: File system monitoring for edge nodes
- **scikit-optimize**: Bayesian optimization engine
- **sentence-transformers**: Embedding model for memory search

## Available Skills

- `/build-and-test` — Build the project and run the test suite
- `/run-edge-demo` — Launch edge watcher demo on sample data
- `/review-checklist` — Generate a domain-specific code review checklist
