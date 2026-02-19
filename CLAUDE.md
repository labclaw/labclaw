# CLAUDE.md — Jarvis Mesh

## Project Overview

Jarvis Mesh is a distributed agentic architecture for self-documenting, self-improving neuroscience laboratories. It provides automated experiment tracking, real-time data quality monitoring, and orchestrated analysis pipelines for behavior + imaging labs.

**Tech stack:** Python 3.11+, FastAPI, SQLite, Redis Streams, Claude API, Streamlit
**Domain:** Neuroscience — video behavior tracking, microscopy, electrophysiology, behavioral apparatus

## Agent Team

### Routing Table

| Task Type | Agent | When to Use |
|-----------|-------|-------------|
| Feature planning, task breakdown, multi-agent coordination | tech-lead | Any new feature, complex bug, architecture decision |
| Core system: event bus, graph DB, API, config, plugin registry | platform-engineer | Building/modifying events.py, graph.py, registry.py, app.py, config |
| Agent runtime, orchestrator, tool calling, LLM integration | agent-engineer | Building/modifying runtime.py, orchestrator.py, role configs, prompts |
| Edge nodes, file watchers, quality checks, device adapters | edge-engineer | Building/modifying watcher.py, quality.py, adapters/, sensor code |
| Neuroscience domain: NWB, analysis pipelines, data schemas, SAM-Behavior | neuro-specialist | NWB export, analysis pipeline design, schema definitions, domain logic |
| Discovery pipeline: pattern mining, hypothesis generation, predictive modeling, Bayesian optimization, statistical validation | discovery-engineer | Building/modifying discovery/, optimization/, validation/ modules |
| Dashboard pages, Streamlit UI, visualization | platform-engineer | Building/modifying dashboard/ components, data display |
| Code review, PR review, security audit | code-reviewer | All code changes before merge |

### Orchestration Protocol

1. **Tech-lead is the routing authority.** When a complex task arrives, tech-lead analyzes it and delegates to the appropriate specialist(s).
2. **Main agent never implements directly** for multi-step tasks — it delegates to specialists via Task tool.
3. **Handoff format:** When delegating, provide: (a) clear objective, (b) relevant file paths, (c) acceptance criteria, (d) which agent to hand off to next.
4. **Max 2 agents in parallel** for complex tasks to avoid file conflicts.
5. **Code reviewer is the quality gate** — all code changes pass through code-reviewer before completion.

### Workflow Chains

- **New Feature**: tech-lead → [specialist(s)] → code-reviewer
- **Bug Fix**: tech-lead → [specialist] → code-reviewer
- **New Plugin**: tech-lead → neuro-specialist (schema) + [specialist] (implementation) → code-reviewer
- **NWB/Data**: tech-lead → neuro-specialist → code-reviewer
- **Edge Integration**: tech-lead → edge-engineer → neuro-specialist (validation) → code-reviewer
- **Discovery/Mining**: tech-lead → discovery-engineer → neuro-specialist (biological validation) → code-reviewer
- **Closed-Loop Optimization**: tech-lead → discovery-engineer (optimizer) + neuro-specialist (safety/domain) → code-reviewer

## Project Structure

```
src/jarvis_mesh/
├── core/           # Event bus, graph DB, plugin registry, config, governance, evaluation
├── agents/         # Agent runtime, orchestrator, role configs
├── edge/           # File watchers, quality checks, device adapters
├── discovery/      # Pattern mining, hypothesis generation, predictive modeling
├── optimization/   # Bayesian optimization, safety constraints, approval workflow
├── validation/     # Statistics, cross-validation, provenance, report generation
├── api/            # REST API (FastAPI)
└── dashboard/      # Streamlit dashboard
plugins/            # Extension plugins (devices, analysis, metrics, schemas)
tests/              # Unit, integration, replay tests
configs/            # Environment configs (YAML)
```

## Coding Standards

- Python 3.11+, type hints required on all public functions
- Pydantic models for all data schemas
- `ruff` for linting (E, F, I, N, W, UP rules)
- `pytest` for testing; async tests with `pytest-asyncio`
- Docstrings only on public API; no comments on obvious code
- All event/graph node schemas in `core/` — plugins extend via registry
- File paths as `pathlib.Path`, never raw strings
- JSON serialization: always cast numpy types with `int()` / `float()`
- No credentials in code; use environment variables via config
- Timestamps in ISO 8601 format; filenames with `YYYYMMDD_HHMMSS`

## Available Skills

- `/build-and-test` — Build the project and run the test suite
- `/run-edge-demo` — Launch edge watcher demo on sample data
- `/review-checklist` — Generate a domain-specific code review checklist

## Key Dependencies

- **NWB**: `pynwb` + `hdmf` for Neurodata Without Borders export
- **NeuroConv**: Format conversion from 47+ neuroscience formats
- **SAM-Behavior**: Zero-shot multi-animal pose estimation (Shen Lab)
- **watchdog**: File system monitoring for edge nodes

## TODO

- [ ] Copy `.mcp.json.example` to `.mcp.json` and update paths for your machine
