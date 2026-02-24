# LabClaw Quickstart

Get your lab's AI brain running in 5 minutes.

---

## Install

```bash
pip install labclaw
```

For development or scientific analysis extras:

```bash
pip install -e ".[dev,science]"
```

Optional extras:

| Extra | What it adds |
|-------|-------------|
| `science` | numpy, scipy, scikit-learn, scikit-optimize, umap-learn |
| `dev` | pytest, ruff, mypy, pre-commit, build tools |
| `nwb` | pynwb, hdmf, neuroconv (NWB file support) |
| `memory` | graphiti-core, sentence-transformers (embedding search) |

---

## Try the Demo

No API key required:

```bash
labclaw demo
```

This runs a full cycle against synthetic data: file ingestion, pattern mining,
hypothesis generation, and evolution step. Watch the output to see how each
layer fires.

With domain-specific sample data:

```bash
labclaw demo --domain neuroscience   # animal subjects, fluorescence data
labclaw demo --domain generic        # generic tabular data (default)
```

Add `--keep` to inspect the temporary workspace after the demo exits.

---

## Initialize a Project

```bash
labclaw init my-lab
cd my-lab
```

This creates:

```
my-lab/
  configs/default.yaml     # LLM provider, ports, watch paths
  data/                    # Drop data files here; daemon watches this
  lab/
    SOUL.md              # Lab identity and goals
    MEMORY.md            # Accumulated lab knowledge
```

---

## Configure

Edit `configs/default.yaml`:

```yaml
llm:
  provider: anthropic          # anthropic | openai | local
  model: claude-sonnet-4-6
  api_key_env: ANTHROPIC_API_KEY   # export this in your shell

edge:
  watch_paths:
    - /data/behavior-rig-1     # directories to watch for new files
    - /data/microscope-1
```

Set your API key:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

---

## Start the Daemon

```bash
labclaw serve --data-dir ./data --memory-root ./lab
```

This starts all subsystems:

- **File watcher** -- detects new data files in `--data-dir`
- **Discovery loop** -- mines patterns every 5 minutes (configurable)
- **Evolution engine** -- improves pipeline parameters every 30 minutes
- **REST API** -- listens on port 18800
- **Dashboard** -- Streamlit on port 18801

Custom ports and intervals:

```bash
labclaw serve --data-dir ./data --memory-root ./lab \
              --port 18800 --dashboard-port 18801 \
              --discovery-interval 300 --evolution-interval 1800
```

---

## View Dashboard

Open [http://localhost:18801](http://localhost:18801) in your browser.

You'll see live discoveries, evolution cycle progress, device status, and the
growing knowledge graph.

---

## Query the API

Ask a question in natural language:

```bash
curl -X POST http://localhost:18800/api/agents/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What patterns did you find today?"}'
```

Run a scientific method cycle manually:

```bash
curl -X POST http://localhost:18800/api/orchestrator/cycle \
  -H "Content-Type: application/json" \
  -d '{"data_rows": []}'
```

Check system health:

```bash
curl http://localhost:18800/api/health
```

---

## Use as MCP Server

Add LabClaw as a tool for Claude Desktop. In your MCP config:

```json
{
  "mcpServers": {
    "labclaw": {
      "command": "labclaw",
      "args": ["mcp"]
    }
  }
}
```

Claude can then query your lab's knowledge graph, list discoveries, check device
status, and propose experiments directly from the chat interface.

Or start the MCP server standalone:

```bash
labclaw mcp
```

---

## Manage Plugins

List loaded plugins:

```bash
labclaw plugin list
```

Scaffold a new plugin:

```bash
labclaw plugin create my-domain-pack --type domain
labclaw plugin create my-device-driver --type device
labclaw plugin create my-analysis-algo --type analysis
```

Each command generates a ready-to-edit Python package with the correct protocol
stubs and a `pyproject.toml` entry point so LabClaw auto-loads it on startup.

---

## CLI Commands

| Command | Description |
|---------|-------------|
| `labclaw serve` | Start the full 24/7 daemon |
| `labclaw demo` | Run interactive demo (no API keys) |
| `labclaw init <name>` | Scaffold a new project |
| `labclaw mcp` | Start MCP server (stdio transport) |
| `labclaw plugin list` | List registered plugins |
| `labclaw plugin create <name>` | Scaffold a new plugin |
| `labclaw --api [PORT]` | Launch FastAPI server only |
| `labclaw --dashboard` | Launch Streamlit dashboard only |

---

## Next Steps

| Topic | Doc |
|-------|-----|
| System architecture | [architecture.md](architecture.md) |
| All API endpoints | [api-reference.md](api-reference.md) |
| Configuration options | [configuration.md](configuration.md) |
| Writing plugins | [plugin-development.md](plugin-development.md) |
| Memory system | [memory-system.md](memory-system.md) |
| Agent system | [agents.md](agents.md) |
| Self-evolution | [self-evolution.md](self-evolution.md) |
| Practical recipes | [cookbook.md](cookbook.md) |
| Production deployment | [deployment.md](deployment.md) |
