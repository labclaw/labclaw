# CLAUDE.md — LabClaw

## Project Overview

LabClaw is a self-evolving agentic system that serves as the super brain for research laboratories. It encodes the complete scientific method as an autonomous computational loop, accumulates persistent memory that makes it increasingly effective over time, and serves each team member with personalized intelligence.

**Tech stack:** Python 3.11+, FastAPI, SQLite, Redis Streams, Claude API, Streamlit, Graphiti
**Domain:** Neuroscience (first vertical) — video behavior tracking, microscopy, electrophysiology, behavioral apparatus
**Design doc:** `docs/plans/2026-02-19-labclaw-design-v2.md`

## Architecture (5 Layers)

```
Layer 5: PERSONA & DIGITAL STAFF — Human + AI members, training, promotion
Layer 4: MEMORY                  — Lab super brain (Markdown + Knowledge Graph + Shared Blocks)
Layer 3: ENGINE                  — Scientific method loop (OBSERVE→...→CONCLUDE)
Layer 2: SOFTWARE INFRA          — Gateway, Event Bus, API, Dashboard, Edge Nodes
Layer 1: HARDWARE                — Devices, interfaces, manager, safety
```

## Agent Team

### Routing Table

| Task Type | Agent | When to Use |
|-----------|-------|-------------|
| Feature planning, task breakdown, multi-agent coordination | tech-lead | Any new feature, complex bug, architecture decision |
| Core system: event bus, graph, API, config, gateway, registry | platform-engineer | Building/modifying core/*, api/*, configs/ |
| Memory system: markdown, knowledge graph, search, shared blocks | memory-engineer | Building/modifying memory/*, lab/*, members/* |
| Agent runtime, orchestrator, tool calling, LLM integration | agent-engineer | Building/modifying agents/runtime, orchestrator, prompts |
| Edge nodes, file watchers, quality checks, device adapters, gateway | edge-engineer | Building/modifying edge/*, gateway, adapters/ |
| Neuroscience domain: NWB, analysis pipelines, data schemas, SAM-Behavior | neuro-specialist | NWB export, analysis pipeline design, schema definitions |
| Discovery pipeline: mining, hypothesis, modeling, optimization, validation | discovery-engineer | Building/modifying discovery/, optimization/, validation/ |
| Dashboard pages, Streamlit UI, visualization | platform-engineer | Building/modifying dashboard/ components |
| Code review, PR review, security audit | code-reviewer | All code changes before merge |

### Orchestration Protocol

1. **Tech-lead is the routing authority.** Complex tasks go to tech-lead first.
2. **Main agent never implements directly** for multi-step tasks — delegates to specialists.
3. **Handoff format:** (a) clear objective, (b) relevant file paths, (c) acceptance criteria, (d) next agent.
4. **Max 2 agents in parallel** to avoid file conflicts.
5. **Code reviewer is the quality gate** — all changes pass through code-reviewer.

### Workflow Chains

- **New Feature**: tech-lead → [specialist(s)] → code-reviewer
- **Bug Fix**: tech-lead → [specialist] → code-reviewer
- **New Plugin**: tech-lead → neuro-specialist (schema) + [specialist] (impl) → code-reviewer
- **NWB/Data**: tech-lead → neuro-specialist → code-reviewer
- **Edge Integration**: tech-lead → edge-engineer → neuro-specialist (validation) → code-reviewer
- **Discovery/Mining**: tech-lead → discovery-engineer → neuro-specialist (bio validation) → code-reviewer
- **Closed-Loop Optimization**: tech-lead → discovery-engineer + neuro-specialist (safety) → code-reviewer
- **Memory System**: tech-lead → memory-engineer → code-reviewer
- **Persona Tuning**: tech-lead → memory-engineer + neuro-specialist → code-reviewer

## Project Structure

```
src/labclaw/
├── core/           # Config, event bus, gateway, graph, registry, governance, evaluation
├── hardware/       # Device registry, manager, safety, interface adapters
├── memory/         # Markdown memory, knowledge graph (Graphiti), shared blocks, search
├── discovery/      # Mining, unsupervised, hypothesis generation, predictive modeling
├── optimization/   # Bayesian optimization, safety constraints, proposal, approval
├── validation/     # Statistics, cross-validation, provenance, report generation
├── agents/         # Agent runtime, orchestrator
├── edge/           # File watchers, quality checks, device adapters, CLI
├── api/            # REST API (FastAPI)
└── dashboard/      # Streamlit dashboard
lab/                # Lab memory — Tier A: human-readable (SOUL.md, MEMORY.md, protocols/, etc.)
members/            # Per-member profiles — human + digital (SOUL.md, MEMORY.md)
devices/            # Per-device profiles (SOUL.md, MEMORY.md)
plugins/            # Extension plugins (devices, analysis, metrics, schemas)
tests/              # Unit, integration, replay tests
configs/            # Environment configs (YAML)
```

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

## Coding Standards

- Python 3.11+, type hints required on all public functions
- Pydantic models for all data schemas and experiment validation
- `ruff` for linting (E, F, I, N, W, UP rules)
- `pytest` for testing; async tests with `pytest-asyncio`
- Docstrings only on public API; no comments on obvious code
- All event/graph node schemas in `core/` — plugins extend via registry
- File paths as `pathlib.Path`, never raw strings
- JSON serialization: always cast numpy types with `int()` / `float()`
- No credentials in code; use environment variables via config
- Timestamps in ISO 8601 format; filenames with `YYYYMMDD_HHMMSS`

## Key Dependencies

- **Graphiti**: `graphiti-core` — temporal knowledge graph for lab memory
- **NWB**: `pynwb` + `hdmf` — Neurodata Without Borders export
- **NeuroConv**: Format conversion from 47+ neuroscience formats
- **SAM-Behavior**: Zero-shot multi-animal pose estimation (Shen Lab)
- **watchdog**: File system monitoring for edge nodes
- **scikit-optimize**: Bayesian optimization engine
- **sentence-transformers**: Embedding model for memory search

## Available Skills

- `/build-and-test` — Build the project and run the test suite
- `/run-edge-demo` — Launch edge watcher demo on sample data
- `/review-checklist` — Generate a domain-specific code review checklist

## TODO

- [ ] Copy `.mcp.json.example` to `.mcp.json` and update paths for your machine
