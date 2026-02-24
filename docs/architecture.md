# LabClaw Architecture

LabClaw is a five-layer agentic system that encodes the scientific method as an
autonomous computational loop. It observes lab data continuously, mines patterns,
generates and tests hypotheses, and improves its own analytical strategies over time.

---

## Five-Layer Stack

```
┌──────────────────────────────────────────────────────────────────┐
│  Layer 5: PERSONA & DIGITAL STAFF                                │
│  Human members + autonomous AI staff (intern → analyst → senior) │
├──────────────────────────────────────────────────────────────────┤
│  Layer 4: MEMORY                                                  │
│  Three-tier: Markdown files · Knowledge graph · Agent blocks      │
├──────────────────────────────────────────────────────────────────┤
│  Layer 3: SCIENTIFIC METHOD ENGINE                               │
│  OBSERVE → ASK → HYPOTHESIZE → PREDICT → EXPERIMENT → CONCLUDE  │
├──────────────────────────────────────────────────────────────────┤
│  Layer 2: SOFTWARE INFRASTRUCTURE                                │
│  Gateway · Event bus · REST API · Dashboard · Edge nodes         │
├──────────────────────────────────────────────────────────────────┤
│  Layer 1: HARDWARE                                               │
│  Device registry · Interfaces · Safety checker · Drivers         │
└──────────────────────────────────────────────────────────────────┘
```

---

## Layer 1: Hardware

Every instrument is a managed resource with an identity, capabilities, and status.

**Device interfaces:**

| Type | Examples | How it works |
|------|----------|-------------|
| File-based | Cameras, Open Ephys, ScanImage | `watchdog` monitors output folders |
| Serial/USB | Arduino triggers, lick detectors | `pyserial` / `pyfirmata` |
| Network API | Hamamatsu cameras, Neuropixels | REST / gRPC / vendor SDK |
| GPIO/DAQ | National Instruments, LabJack | `nidaqmx` / `labjack-ljm` |
| Software bridge | Bonsai, PsychoPy, DeepLabCut-live | ZMQ / shared memory / socket |

**Safety layer:**

All hardware commands pass through `HardwareSafetyChecker` before execution.
Checks: device exists → status is online/in-use → action in declared capabilities.
Digital staff cannot send commands without the appropriate role permission.

---

## Layer 2: Software Infrastructure

**Key components:**

- **Gateway** — WebSocket control plane; single entry point for devices, agents, clients
- **Event bus** — Pub/sub via Redis Streams (or in-memory for single-node deploys)
- **REST API** — FastAPI on port 18800; Swagger UI at `/docs`
- **Dashboard** — Streamlit on port 18801; live activity stream, device status, graph browser
- **Edge nodes** — Local process at each instrument (`labclaw-edge`); bridges hardware to Layer 2

**Event naming convention:** `{layer}.{module}.{action}`
Examples: `hardware.safety.checked`, `discovery.pattern.found`, `infra.governance.action_approved`

---

## Layer 3: Scientific Method Engine

Each module maps to a step of the scientific method:

| Step | Module | Function |
|------|--------|----------|
| ① OBSERVE | `edge/watcher.py`, `edge/quality.py` | 24/7 data capture, real-time QC |
| ② ASK | `discovery/mining.py`, `discovery/unsupervised.py` | Pattern mining, anomaly detection, clustering |
| ③ HYPOTHESIZE | `discovery/hypothesis.py` | LLM + statistical evidence → testable hypotheses |
| ④ PREDICT | `discovery/modeling.py` | Predictive models, feature importance, uncertainty |
| ⑤ EXPERIMENT | `optimization/` | Bayesian optimization, safety constraints, human-in-the-loop approval |
| ⑥ ANALYZE | All modules (intermediate outputs) | Exhaustive feature extraction |
| ⑦ CONCLUDE | `validation/` | Effect sizes, confidence intervals, multiple-comparison correction, provenance |

Step ⑦ conclusions feed back to Step ② ASK, closing the loop. Each cycle also
updates the evolution engine, which improves the analytical strategies themselves.

---

## Layer 4: Memory

Three tiers, each optimized for a different access pattern.

### Tier A — Human-Readable Markdown

```
lab/
├── SOUL.md              # Lab identity, mission, culture, standards
├── MEMORY.md            # Persistent shared facts
├── protocols/           # Living protocols with pitfall annotations
├── decisions/           # Decision logs with reasoning
├── failures/            # Failure records to prevent repetition
└── stream/YYYY-MM-DD.md # Daily lab activity log
members/
├── <name>/SOUL.md       # Identity, expertise, work style, autonomy level
└── <name>/MEMORY.md     # Accumulated knowledge, corrections log, benchmarks
```

Files are the source of truth — readable and editable with any text editor,
version-controlled in Git. Search: BM25 keyword + vector semantic + temporal decay.

### Tier B — Knowledge Graph (SQLite / Graphiti)

Temporal knowledge graph for structured entities and relationships:

- **Entities:** People, Samples, Protocols, Devices, Parameters, Findings
- **Edges are temporal** — track when facts become true and when they change
- **Bi-temporal:** event time (when it happened) + ingestion time (when learned)
- **Entity resolution:** LLM-powered disambiguation (`"C57"` = `"C57BL/6"` = `"black six"`)

### Tier C — Agent Coordination Blocks

Real-time shared state between concurrent agents:

- **Shared blocks** — multiple agents read/write the same memory block
- **Concurrency modes:** `insert` (append, no conflict) · `replace` (validated) · `rethink` (full rewrite)
- **Four tiers per agent:** Core (always loaded) → Message (recent) → Archival (searchable) → Recall (history)

---

## Self-Evolution Engine

The system improves its own analytical strategies without human intervention.

**Evolution targets:**

| Target | What changes |
|--------|-------------|
| `analysis_params` | Mining thresholds, clustering parameters |
| `prompts` | LLM system prompts for hypothesis generation |
| `routing` | Which analysis module handles which data type |
| `heuristics` | Decision rules for anomaly flagging |
| `strategy` | High-level experiment selection logic |

**Promotion pipeline** (one candidate at a time):

```
BACKTEST → SHADOW → CANARY → PROMOTED
                               ↓ (if fitness drops)
                           ROLLED_BACK
```

- **Backtest:** Replay historical data through candidate config; compare fitness metrics
- **Shadow:** Run production + candidate in parallel on live data; no production impact
- **Canary:** Route a fraction of live traffic to candidate
- **Promote:** Candidate becomes production config

Rollback triggers automatically if fitness drops more than `rollback_threshold` (default 10%).

---

## Plugin System

Three plugin types extend LabClaw without modifying core:

| Type | Protocol | Adds |
|------|----------|------|
| `device` | `DevicePlugin` | New hardware drivers |
| `domain` | `DomainPlugin` | Domain-specific sample nodes, sentinel rules, hypothesis templates |
| `analysis` | `AnalysisPlugin` | New mining algorithms and validators |

Plugins are discovered via Python entry points (`labclaw.plugins` group in `pyproject.toml`)
and loaded at startup by `PluginLoader`.

**Built-in domain plugins:**

- `generic` — no domain-specific logic; works for any tabular data
- `neuroscience` — `AnimalSampleNode`, fluorescence sentinels, neuro hypothesis templates

Scaffold a new plugin:

```bash
labclaw plugin create my-pack --type domain
```

---

## Governance & Safety

**Two-layer safety:**

1. **Hardware layer** (`HardwareSafetyChecker`) — blocks commands to offline/errored devices
2. **Governance layer** (`GovernanceEngine`) — role-based permissions + registered safety rules + immutable audit log

**Roles and permissions:**

| Role | Permitted actions |
|------|------------------|
| `pi` | Everything |
| `postdoc` | read, write, execute, approve |
| `graduate` | read, write, execute |
| `undergraduate` | read, write |
| `technician` | read, write, calibrate |
| `digital_intern` | read |
| `digital_analyst` | read, analyze |
| `digital_specialist` | read, analyze, propose |

Every action is recorded in an append-only audit log (JSON Lines on disk).

---

## Layer 5: Persona & Digital Staff

Human and digital members share the same structure. The lab is a team.

**Digital staff levels:**

| Level | Autonomy | Key capabilities |
|-------|----------|-----------------|
| `digital_intern` | Supervised — all outputs reviewed | File logging, metadata extraction, basic QC |
| `digital_analyst` | Semi-autonomous — spot-checked | Independent analysis, pattern mining, reports |
| `digital_senior` | Autonomous — human approval for experiments | Hypothesis generation, cross-experiment discovery |
| `digital_specialist` | Autonomous within domain | Domain-specific expert tasks |

Promotion requires passing monthly benchmarks (QC precision/recall, analysis agreement,
hypothesis detection rate) above threshold for 3 consecutive months, plus PI review.

---

## Data Flow (end to end)

```
New data file dropped in watch path
        │
        ▼
Edge node detects file (watchdog)
        │
        ▼
Quality check → flag or pass
        │
        ▼
Graph node created (RecordingNode / AnalysisNode)
        │
        ▼
Discovery loop mines patterns → PatternRecord emitted
        │
        ▼
Hypothesis generator proposes hypotheses → FindingNode
        │
        ▼
Optimization engine proposes next experiment (with human approval gate)
        │
        ▼
Validation engine scores result → conclusion written to Memory
        │
        ▼
Evolution engine updates fitness → may promote new candidate config
        │
        └──────────────────────────────────────────────────────────▶ next cycle
```

---

## Orchestrator

The `ScientificLoop` orchestrator (`orchestrator/loop.py`) executes one full cycle
of the scientific method as a state machine:

```
OBSERVE → ASK → HYPOTHESIZE → PREDICT → EXPERIMENT → ANALYZE → CONCLUDE
```

Each step is implemented in `orchestrator/steps.py` as an independent function.
Steps that fail or have insufficient data are skipped gracefully. A `CycleResult`
records which steps completed, how many patterns/hypotheses were generated, and
total duration.

The daemon runs the orchestrator periodically (default: every 5 minutes). It can
also be triggered manually via `POST /api/orchestrator/cycle`.

---

## Agent System

Two built-in agents interact with the lab through registered tools:

- **Lab Assistant** -- general-purpose Q&A about lab data, patterns, findings.
- **Experiment Designer** -- plans next experiments based on hypotheses and constraints.

Both use a ReAct-style loop: the LLM reasons about the question, calls tools
(memory search, pattern mining, device status, evolution status), and synthesizes
a response. The `AgentRuntime` supports up to 10 tool-call rounds per conversation.

Custom agents can be created by providing a system prompt and additional tools.
See [agents.md](agents.md) for the full guide.

---

## MCP Server

LabClaw exposes its capabilities via the Model Context Protocol (MCP), allowing
external AI clients (Claude Desktop, etc.) to:

- Run pattern mining (`discover`)
- Generate hypotheses (`hypothesize`)
- Query lab memory (`query_memory`)
- List findings (`list_findings`)
- Check evolution status (`evolution_status`)
- View device status (`device_status`)

Start with `labclaw mcp` (stdio transport). See [agents.md](agents.md#mcp-server-for-external-ai-integration) for setup details.

---

## Daemon

The `LabClawDaemon` is the production entry point that runs all subsystems as a
single long-lived process:

| Component | Thread | Interval |
|-----------|--------|----------|
| REST API (uvicorn) | Main thread | Continuous |
| Edge file watcher | Watchdog thread | Real-time |
| Discovery loop | Background thread | 5 min (configurable) |
| Evolution loop | Background thread | 30 min (configurable) |
| Streamlit dashboard | Subprocess | Continuous |

Data flows: file watcher detects new CSV/TSV files, the `DataAccumulator` ingests
rows, the discovery loop runs the orchestrator on accumulated data, and the
evolution loop measures fitness and advances candidate cycles.

Start with `labclaw serve --data-dir ./data --memory-root ./lab`.

---

## Source Layout

```
src/labclaw/
├── core/           # Schemas, events, graph nodes, governance, evaluation
├── hardware/       # Device registry, safety checker, drivers
├── edge/           # File watcher, quality monitor, edge CLI
├── discovery/      # Pattern mining, unsupervised learning, hypothesis gen, modeling
├── optimization/   # Bayesian optimizer, proposals, safety, approval
├── validation/     # Statistics, cross-validation, provenance, reports
├── memory/         # Tier A (markdown), Tier B (graph), Tier C (agent blocks)
├── evolution/      # Evolution engine, schemas, evaluation harness
├── persona/        # Member profiles, persona engine
├── orchestrator/   # Top-level state machine
├── plugins/        # Plugin loader, registry, protocols, domain packs
├── llm/            # LLM provider abstraction (Anthropic, OpenAI, local)
├── agents/         # Agent runtime, tool definitions
├── api/            # FastAPI routers
├── dashboard/      # Streamlit pages
├── demo/           # Demo runner (synthetic data + full cycle)
└── mcp/            # MCP server (labclaw-mcp)
```

---

## Related Documentation

| Topic | Doc |
|-------|-----|
| Getting started | [quickstart.md](quickstart.md) |
| All API endpoints | [api-reference.md](api-reference.md) |
| Configuration options | [configuration.md](configuration.md) |
| Three-tier memory | [memory-system.md](memory-system.md) |
| Agent system and MCP | [agents.md](agents.md) |
| Self-evolution engine | [self-evolution.md](self-evolution.md) |
| Writing plugins | [plugin-development.md](plugin-development.md) |
| Practical recipes | [cookbook.md](cookbook.md) |
| Production deployment | [deployment.md](deployment.md) |
