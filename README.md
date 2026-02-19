# Jarvis Mesh

Distributed agentic architecture for self-documenting, self-improving neuroscience laboratories.

## Overview

Jarvis Mesh is a plugin-based system that upgrades existing neuroscience labs with:
- **Session Chronicle** — automated experiment tracking and metadata capture
- **Sentinel** — real-time data quality monitoring across modalities
- **Conductor** — orchestrated analysis pipeline execution with full provenance

Three-layer architecture: Personal Jarvis (user-facing) + Central Jarvis (control plane) + Distributed Jarvis (edge nodes at instruments).

## Quick Start

```bash
pip install -e ".[dev]"
```

## Project Structure

```
src/jarvis_mesh/
├── core/        # Event bus, graph DB, plugin registry
├── agents/      # Agent runtime + role configs
├── edge/        # Distributed edge runtime
├── api/         # REST API (FastAPI)
└── dashboard/   # Streamlit dashboard
plugins/         # Extension plugins (devices, analysis, metrics, schemas)
```

## License

MIT
