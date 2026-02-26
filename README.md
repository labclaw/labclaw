# LabClaw

[![CI](https://github.com/labclaw/labclaw/actions/workflows/ci.yml/badge.svg)](https://github.com/labclaw/labclaw/actions/workflows/ci.yml)
[![Security](https://github.com/labclaw/labclaw/actions/workflows/security.yml/badge.svg)](https://github.com/labclaw/labclaw/actions/workflows/security.yml)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

Open-source AI infrastructure for scientific laboratories. LabClaw encodes the complete scientific method as an autonomous computational loop: **observe** experimental data, **discover** patterns, **generate** hypotheses, **optimize** experiments, **validate** results, and **evolve** its own analysis capabilities over time.

## Architecture

```
Layer 5  PERSONAS       Human + AI lab members with role-based access
Layer 4  MEMORY         Three-tier persistent lab knowledge (Markdown + Graph + Shared Blocks)
Layer 3  ENGINE         Scientific method loop (Observe → Ask → Hypothesize → Predict → Experiment → Analyze → Conclude)
Layer 2  SOFTWARE       Event bus, REST API, dashboard, edge nodes
Layer 1  HARDWARE       Device interfaces, safety manager, instrument adapters
```

## Key Features

- **24/7 autonomous monitoring** — file watchers detect new experimental data and run quality checks in real time
- **Pattern discovery** — exhaustive correlation mining, anomaly detection, temporal trend analysis, unsupervised clustering
- **Hypothesis generation** — LLM-powered hypothesis engine grounded in statistical evidence
- **Bayesian optimization** — propose next experiments with safety constraints and human approval
- **Statistical validation** — cross-validation, provenance chains, reproducibility reports
- **Self-evolution** — candidate analysis strategies are proposed, tested, scored, and promoted automatically
- **Persistent memory** — lab knowledge accumulates across sessions (protocols, failures, discoveries)

## Quick Start

```bash
# Install
uv sync --extra dev --extra science

# Run the daemon (API + file watcher + discovery loop + evolution loop)
uv run labclaw-daemon --data-dir ./data --memory-root ./lab

# Or run components individually
uv run labclaw serve --port 18800          # API only
uv run labclaw --dashboard                 # Dashboard only
```

## Core Modules

| Module | Path | Function |
|--------|------|----------|
| Edge | `edge/` | File watching, quality checks, session chronicle |
| Discovery | `discovery/` | Pattern mining, clustering, hypothesis generation, predictive modeling |
| Optimization | `optimization/` | Bayesian experiment proposal, safety constraints |
| Validation | `validation/` | Statistical tests, cross-validation, provenance, reports |
| Evolution | `evolution/` | Self-improving analysis candidates, fitness scoring |
| Memory | `memory/` | Tier-A markdown, Tier-B knowledge graph, Tier-C shared blocks |
| API | `api/` | FastAPI REST endpoints (port 18800) |
| Dashboard | `dashboard/` | Streamlit visualization (port 18801) |

## API

```bash
curl http://127.0.0.1:18800/api/health
curl http://127.0.0.1:18800/api/status
```

See `docs/specs/` for full API documentation.

## Testing

```bash
# Full test suite (100% coverage required)
uv run pytest --cov=labclaw --cov-fail-under=100 -q

# Lint + format
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
```

## Documentation

- [Architecture overview](docs/architecture.md)
- [Integration stack](docs/awesome-ai-for-science.md) — tools and MCP servers LabClaw integrates with
- [Deployment guide](deploy/)
- [Specifications](docs/specs/)

## Roadmap

See [ROADMAP.md](ROADMAP.md).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). PRs and issues are welcome.

## License

[Apache 2.0](LICENSE)
