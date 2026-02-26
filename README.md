<p align="center">
  <a href="https://labclaw.org"><img src="docs/assets/logo.svg" alt="LabClaw" width="480"></a>
</p>

<p align="center">
  <em>Open-source Python framework that connects LLMs to your lab instruments, persistent memory, and governance — so your lab learns from every experiment.</em>
</p>

<p align="center">
  <a href="https://github.com/labclaw/labclaw/actions/workflows/ci.yml"><img src="https://github.com/labclaw/labclaw/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/labclaw/labclaw/actions/workflows/security.yml"><img src="https://github.com/labclaw/labclaw/actions/workflows/security.yml/badge.svg" alt="Security"></a>
  <a href="https://codecov.io/gh/labclaw/labclaw"><img src="https://img.shields.io/badge/coverage-100%25-brightgreen.svg" alt="Coverage"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.11%2B-blue.svg" alt="Python 3.11+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue.svg" alt="License: Apache 2.0"></a>
</p>

---

**Labs have AI. Labs have tools. Nothing connects them. LabClaw does.**

LabClaw encodes the complete scientific method as an autonomous loop: observe data, mine patterns, generate hypotheses, design experiments, validate results, and evolve its own analysis pipelines — all while building persistent memory that makes it smarter over time.

## Features

- **Autonomous Discovery** — Pattern mining, anomaly detection, and hypothesis generation across all your experimental data
- **Self-Evolving Pipelines** — Analysis candidates compete, mutate, and improve through evolutionary fitness scoring
- **Persistent Lab Memory** — Three-tier memory (Markdown + Knowledge Graph + Shared Blocks) that survives restarts and accumulates knowledge
- **Instrument Integration** — Connect any lab device through a protocol-based adapter system with safety constraints
- **Bayesian Optimization** — AI-guided experiment proposals with safety boundaries and human-in-the-loop approval
- **Full Provenance** — Every finding traces back through the complete chain: raw data → analysis → statistical validation → report

## Architecture

Five layers, one unified stack:

```
Layer 5  PERSONA        Agent identities & goals — human + AI lab members with role-based access
Layer 4  MEMORY         3-tier persistent store — Markdown + Knowledge Graph + Shared Blocks
Layer 3  ENGINE         Scientific method loop — Observe → Hypothesize → Validate → Evolve
Layer 2  PLATFORM       Event bus, REST API, dashboard, edge nodes
Layer 1  HARDWARE       Instrument adapters, safety manager, device registry
```

## Quick Start

```bash
# Clone and install
git clone https://github.com/labclaw/labclaw
cd labclaw
uv sync --extra dev --extra science

# Run the daemon (API + file watcher + discovery loop + evolution loop)
uv run labclaw-daemon --data-dir ./data --memory-root ./lab
```

The daemon starts four services:
- **REST API** on port `18800` — experiment management, memory queries, plugin control
- **File Watcher** — monitors your data directory for new recordings
- **Discovery Loop** — continuous pattern mining and hypothesis generation
- **Evolution Loop** — pipeline fitness evaluation and candidate promotion

## Use Cases

| Domain | What LabClaw Does |
|--------|-------------------|
| **Behavioral Neuroscience** | Automate video tracking, pose estimation, and trial management across multi-animal experiments |
| **Wet Lab Automation** | Connect liquid handlers, plate readers, and incubators into self-optimizing protocols |
| **Chemistry & Materials** | Drive synthesis robots and characterization instruments with AI-guided exploration |

## Core Modules

| Module | Path | Description |
|--------|------|-------------|
| Edge | `edge/` | File watching, quality checks, session chronicle |
| Discovery | `discovery/` | Pattern mining, clustering, hypothesis generation, predictive modeling |
| Optimization | `optimization/` | Bayesian experiment proposal, safety constraints |
| Validation | `validation/` | Statistical tests, cross-validation, provenance, reports |
| Evolution | `evolution/` | Self-improving analysis candidates, fitness scoring |
| Memory | `memory/` | Tier-A markdown, Tier-B knowledge graph, Tier-C shared blocks |
| API | `api/` | FastAPI REST endpoints |
| Dashboard | `dashboard/` | Streamlit visualization |

## Development

```bash
# Run the full test suite (100% coverage required)
uv run pytest --cov=labclaw --cov-fail-under=100 -q

# Lint + format
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/

# Type checking
uv run mypy src/labclaw/
```

## Documentation

| Resource | Link |
|----------|------|
| Architecture overview | [docs/architecture.md](docs/architecture.md) |
| Quick start guide | [docs/quickstart.md](docs/quickstart.md) |
| Integration stack | [docs/awesome-ai-for-science.md](docs/awesome-ai-for-science.md) |
| API reference | [docs/api-reference.md](docs/api-reference.md) |
| Plugin development | [docs/plugin-development.md](docs/plugin-development.md) |
| Deployment guide | [deploy/](deploy/) |
| Specifications | [docs/specs/](docs/specs/) |

## Roadmap

See [ROADMAP.md](ROADMAP.md) for the development plan.

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

[Apache 2.0](LICENSE)
