<p align="center">
  <a href="https://labclaw.org"><img src="docs/assets/logo.svg" alt="LabClaw" width="480"></a>
</p>

<p align="center">
  <em>Each lab deserves a SuperBrain.</em>
</p>

<p align="center">
  <a href="https://github.com/labclaw/labclaw/actions/workflows/ci.yml"><img src="https://github.com/labclaw/labclaw/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/labclaw/labclaw/actions/workflows/security.yml"><img src="https://github.com/labclaw/labclaw/actions/workflows/security.yml/badge.svg" alt="Security"></a>
  <img src="https://img.shields.io/badge/coverage-100%25-brightgreen.svg" alt="Coverage">
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.11%2B-blue.svg" alt="Python 3.11+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue.svg" alt="License: Apache 2.0"></a>
</p>

---

## The Problem

Labs generate mountains of data every day. But the knowledge stays trapped — in notebooks, in people's heads, in one-off scripts that nobody can reproduce. Each new experiment starts from scratch. Each new lab member re-learns the same lessons. AI tools exist. Lab instruments exist. **Nothing connects them.**

## What LabClaw Does

LabClaw is an open-source Python framework that acts as a **persistent, self-improving brain for your lab**. It connects your instruments to LLMs, automatically discovers patterns in your data, generates and tests hypotheses, and remembers everything — so your lab gets smarter with every experiment.

```
Your data files → LabClaw watches → Discovers patterns → Generates hypotheses
    → Validates statistically → Evolves its own pipelines → Remembers everything
```

Three things make LabClaw different:

1. **It runs the scientific method autonomously.** Not just chat — a 7-step loop (Observe → Ask → Hypothesize → Predict → Experiment → Analyze → Conclude) that runs continuously on your data.

2. **It evolves its own analysis.** Analysis candidates compete, mutate, and improve through evolutionary fitness scoring. The system literally gets better at analyzing your data over time.

3. **It builds persistent memory.** Three tiers of memory (human-readable Markdown, a knowledge graph, and shared agent state) survive restarts and accumulate lab-wide knowledge across experiments, projects, and people.

## How It Works

### 1. Point it at your data

```bash
labclaw serve --data-dir ./data --memory-root ./lab
```

LabClaw watches your `data/` directory for new CSV/TSV files — from behavioral tracking systems, plate readers, microscopes, or any instrument that outputs tabular data.

### 2. It discovers patterns automatically

Every 5 minutes, the discovery loop runs the scientific method on all accumulated data:

- **Observe** — Ingest and summarize new data
- **Ask** — Mine pairwise correlations, detect anomalies, find temporal trends
- **Hypothesize** — Use LLMs (or template fallback) to generate testable hypotheses
- **Predict** — Build predictive models with uncertainty estimates
- **Experiment** — Propose next experiments via Bayesian optimization
- **Analyze** — Extract features and compute statistics
- **Conclude** — Run statistical validation, generate provenance chains, write reports

### 3. It evolves its own pipelines

Every 30 minutes, the evolution loop evaluates how well the current analysis performs, proposes mutations, and promotes improvements. After 10 cycles, pipelines typically improve by 15%+ in pattern discovery.

### 4. It remembers everything

All findings, hypotheses, validations, and provenance chains are stored in a 3-tier memory system:

| Tier | What | Storage |
|------|------|---------|
| **A: Human-Readable** | Protocols, decisions, daily logs | Markdown files in git |
| **B: Knowledge Graph** | Entities, relations, temporal links | SQLite FTS5 |
| **C: Agent State** | Shared blocks, per-agent workspace | In-memory + SQLite |

Query memory at any time: `labclaw memory query "correlation between temperature and yield"`

## Quick Start

### 1. Clone and install

```bash
git clone https://github.com/labclaw/labclaw
cd labclaw

# Option A: using uv (recommended — fast, handles Python version)
uv sync --extra science

# Option B: using pip
pip install -e ".[science]"
```

> **Note:** LabClaw is in active development (v0.0.x). PyPI publishing is planned for v0.1.0.

### 2. Run the demo (no API keys needed)

```bash
labclaw demo                         # generic sample data
labclaw demo --domain neuroscience   # pose estimation, trial metrics
labclaw demo --domain chemistry      # reaction yields, conditions
```

This runs a full discovery cycle on built-in sample data — pattern mining, hypothesis generation, statistical validation, and evolution — all in your terminal.

### 3. Start your own project

```bash
labclaw init my-lab    # scaffolds config, data dir, and memory files
cd my-lab
```

### 4. Drop your data and run

```bash
# Copy your CSV/TSV files into the data directory
cp /path/to/experiment_results.csv data/

# Option A: run one analysis cycle
labclaw pipeline --once --data-dir ./data

# Option B: start the 24/7 daemon (watches for new files continuously)
labclaw serve --data-dir ./data --memory-root ./lab
```

LabClaw auto-detects numeric columns. Any CSV with numeric data works — no schema configuration needed.

## Architecture

Five layers, one unified stack — each layer is modular, swappable, and independently testable:

```
Layer 5  PERSONA        Agent identities & goals — human + AI lab members with role-based access
Layer 4  MEMORY         3-tier persistent store — Markdown + Knowledge Graph + Shared Blocks
Layer 3  ENGINE         Scientific method loop — Observe → Hypothesize → Validate → Evolve
Layer 2  PLATFORM       Event bus, REST API, dashboard, edge nodes
Layer 1  HARDWARE       Instrument adapters, safety manager, device registry
```

## Use Cases

**Behavioral Neuroscience** — Automate video tracking, pose estimation, and trial management across multi-animal experiments. LabClaw watches recording directories, extracts behavioral metrics, and discovers correlations between conditions.

**Wet Lab Automation** — Connect liquid handlers, plate readers, and incubators into self-optimizing protocols. The system learns which conditions produce the best results and proposes the next experiment.

**Chemistry & Materials** — Drive synthesis robots and characterization instruments with AI-guided exploration. Bayesian optimization navigates the parameter space while respecting safety constraints.

## CLI Reference

```
labclaw demo                     Try it now — no API keys needed
labclaw init <name>              Scaffold a new project
labclaw serve                    Start the full 24/7 daemon
labclaw pipeline --once          Run one discovery cycle on your data
labclaw ablation                 Compare full vs no-evolution performance
labclaw memory query "term"      Search stored findings
labclaw memory stats             Show memory statistics
labclaw export --format nwb      Export findings to NWB or JSON
labclaw reproduce                Verify deterministic output
labclaw plugin list              List registered plugins
labclaw plugin create <name>     Scaffold a new plugin
labclaw mcp                      Start MCP server (Claude Desktop integration)
labclaw --dashboard              Launch Streamlit dashboard
labclaw --api [PORT]             Launch REST API only
```

## The Daemon

When you run `labclaw serve`, four services start:

| Service | Default | What It Does |
|---------|---------|-------------|
| REST API | port 18800 | Experiment management, memory queries, plugin control |
| File Watcher | — | Monitors `data/` and auto-ingests new CSV/TSV files |
| Discovery Loop | every 5 min | Runs the full scientific method cycle |
| Evolution Loop | every 30 min | Evaluates and improves analysis pipelines |

All intervals are configurable. Run `labclaw serve --help` for options.

## Development

```bash
make test       # 2000+ tests, 100% coverage required
make lint       # ruff check
make format     # ruff format
```

## Documentation

- [Architecture Overview](docs/architecture.md)
- [Quick Start Guide](docs/quickstart.md)
- [Configuration](docs/configuration.md)
- [API Reference](docs/api-reference.md)
- [Plugin Development](docs/plugin-development.md)
- [Memory System](docs/memory-system.md)
- [Self-Evolution](docs/self-evolution.md)
- [Integration Stack](docs/awesome-ai-for-science.md)
- [Deployment Guide](deploy/)

## Roadmap

See [ROADMAP.md](ROADMAP.md).

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[Apache 2.0](LICENSE)
