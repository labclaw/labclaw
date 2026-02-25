# Cookbook

Practical recipes for common LabClaw tasks.

---

## Setting Up LabClaw for a New Lab

### 1. Install

```bash
pip install labclaw
```

For scientific analysis features (numpy, scipy, scikit-learn):

```bash
pip install "labclaw[science]"
```

### 2. Create a project

```bash
labclaw init my-lab
cd my-lab
```

This creates:

```
my-lab/
  configs/default.yaml
  data/
  lab/SOUL.md
  lab/MEMORY.md
```

### 3. Edit lab identity

Open `lab/SOUL.md` and describe your lab:

```markdown
# My Neuroscience Lab

## Identity

Motor control and decision-making in freely moving rodents.

## Mission

Understand neural circuit dynamics during goal-directed behavior.

## Protocols

- Two-photon calcium imaging with 15-minute sessions
- Open-field behavior tracking at 60 fps
```

### 4. Configure LLM and data paths

Edit `configs/default.yaml`:

```yaml
llm:
  provider: anthropic
  model: claude-sonnet-4-6
  api_key_env: ANTHROPIC_API_KEY

edge:
  watch_paths:
    - /data/rig-1
    - /data/rig-2
```

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

### 5. Start

```bash
labclaw serve --data-dir ./data --memory-root ./lab
```

Open the dashboard at `http://localhost:18801`.

---

## Running the Demo (No API Keys Needed)

```bash
labclaw demo
```

The demo creates synthetic data, runs pattern mining, generates hypotheses,
and executes one evolution step. No API keys or external services required.

Domain-specific demos:

```bash
labclaw demo --domain neuroscience   # Animal subjects, fluorescence data
labclaw demo --domain generic        # Generic tabular data (default)
```

Keep the workspace for inspection:

```bash
labclaw demo --keep
```

---

## Adding a New Instrument

### File-Based (Camera, Open Ephys)

For instruments that write files to disk, configure the watcher to monitor
their output directory:

```yaml
# configs/default.yaml
edge:
  watch_paths:
    - /data/camera-output
```

LabClaw automatically ingests CSV/TSV files when they appear.

Register the device via API:

```bash
curl -X POST http://localhost:18800/api/devices/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Behavior Camera 1",
    "device_type": "camera",
    "model": "Basler acA1920-155um",
    "location": "Rig 1"
  }'
```

### Serial/USB Device

Create a device driver plugin (see [Plugin Development](plugin-development.md)):

```bash
labclaw plugin create my-serial-device --type device
```

Implement the `DeviceDriver` protocol with serial communication:

```python
import serial

class SerialDevice:
    def __init__(self, port: str = "/dev/ttyUSB0", baudrate: int = 9600):
        self._serial = serial.Serial(port, baudrate)

    @property
    def device_id(self) -> str:
        return "serial-lick-detector"

    @property
    def device_type(self) -> str:
        return "lick_detector"

    async def connect(self) -> bool:
        self._serial.open()
        return True

    async def read(self) -> dict[str, Any]:
        line = self._serial.readline().decode().strip()
        return {"raw": line, "timestamp": time.time()}

    async def disconnect(self) -> None:
        self._serial.close()
```

### Network API Device

For instruments with REST/gRPC APIs:

```python
import httpx

class NetworkCamera:
    def __init__(self, base_url: str = "http://192.168.1.100:8080"):
        self._client = httpx.AsyncClient(base_url=base_url)

    async def read(self) -> dict[str, Any]:
        resp = await self._client.get("/status")
        return resp.json()

    async def write(self, command: HardwareCommand) -> bool:
        resp = await self._client.post("/command", json=command.model_dump())
        return resp.status_code == 200
```

---

## Creating Custom Analysis Algorithms

Create an analysis plugin:

```bash
labclaw plugin create my-analysis --type analysis
```

Implement your algorithms:

```python
class MyAnalysis:
    metadata = PluginMetadata(
        name="my-analysis",
        version="0.1.0",
        description="Custom spectral analysis",
        plugin_type="analysis",
    )

    def get_mining_algorithms(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "wavelet_decomposition",
                "description": "Multi-scale wavelet analysis of time series",
                "function": self._wavelet_analysis,
            },
        ]

    def get_validators(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "bootstrap_ci",
                "description": "Bootstrap confidence intervals",
                "function": self._bootstrap_validate,
            },
        ]

    def _wavelet_analysis(self, data: list[dict]) -> list[dict]:
        import numpy as np
        from scipy import signal

        # Extract numeric columns and apply wavelet transform
        results = []
        # ... implementation
        return results

    def _bootstrap_validate(self, pattern: dict, data: list[dict]) -> dict:
        # ... implementation
        return {"valid": True, "ci_lower": 0.3, "ci_upper": 0.9}
```

---

## Querying Lab Memory Programmatically

### Via REST API

```bash
# Search across all memory
curl "http://localhost:18800/api/memory/search/query?q=calcium+imaging&limit=5"

# Read an entity's SOUL.md
curl http://localhost:18800/api/memory/lab/soul

# Read an entity's MEMORY.md
curl http://localhost:18800/api/memory/lab/memory

# Append a memory entry
curl -X POST http://localhost:18800/api/memory/lab/memory \
  -H "Content-Type: application/json" \
  -d '{"category": "observation", "detail": "Mouse 12 showed increased grooming"}'
```

### Via Python

```python
from pathlib import Path
from labclaw.memory.markdown import TierABackend, MemoryEntry
from datetime import datetime, UTC

# Initialize
backend = TierABackend(Path("lab"))

# Read SOUL.md
soul = backend.read_soul("lab")
print(soul.content)

# Search
results = backend.search("calcium imaging", limit=5)
for r in results:
    print(f"{r.entity_id}: {r.snippet} (score={r.score})")

# Append to memory
entry = MemoryEntry(
    timestamp=datetime.now(UTC),
    category="finding",
    detail="Significant correlation between firing rate and speed (r=-0.72, p<0.001)",
)
backend.append_memory("lab", entry)
```

### Tier B: Knowledge Graph

```python
from pathlib import Path
from labclaw.memory.sqlite_backend import SQLiteTierBBackend
from labclaw.core.graph import GraphNode

backend = SQLiteTierBBackend(Path("data/labclaw.db"))
await backend.init_db()

# Add a node
node = GraphNode(node_type="finding", name="Speed-accuracy tradeoff")
await backend.add_node(node)

# Full-text search
results = await backend.search("speed accuracy")
for r in results:
    print(f"{r.node.name}: score={r.score}")

# Get neighbors
neighbors = await backend.get_neighbors(node.node_id, relation="supports")
```

### Tier C: Agent Working Memory

```python
from labclaw.memory.shared_blocks import TierCBackend

blocks = TierCBackend(Path("data/blocks.db"))
await blocks.init_db()

# Store a block
await blocks.set_block("current_hypothesis", {"text": "...", "confidence": 0.8}, agent_id="lab-assistant")

# Retrieve
block = await blocks.get_block("current_hypothesis")
print(block)
```

---

## Connecting to Claude/GPT via MCP

LabClaw includes an MCP (Model Context Protocol) server that exposes lab intelligence
as tools for any MCP-compatible AI client.

### Configure Claude Desktop

Add to your Claude Desktop MCP configuration:

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

### Available MCP Tools

| Tool | Description |
|------|-------------|
| `discover` | Run pattern mining on lab data |
| `hypothesize` | Generate hypotheses from patterns |
| `evolution_status` | Get self-evolution cycle status |
| `device_status` | List all lab devices and status |
| `query_memory` | Search lab memory |
| `list_findings` | List recent scientific findings |

### Start Standalone

```bash
labclaw mcp
```

This starts the MCP server on stdio transport, ready for Claude Desktop or
other MCP clients.

---

## Running Evolution Experiments

### Via the Daemon

The daemon runs evolution automatically every 30 minutes. Configure the interval:

```bash
labclaw serve --data-dir ./data --memory-root ./lab --evolution-interval 600
```

### Via API

Manually trigger an evolution cycle:

```bash
# Start a cycle for analysis_params
curl -X POST http://localhost:18800/api/evolution/cycle \
  -H "Content-Type: application/json" \
  -d '{"target": "analysis_params"}'

# Check status
curl http://localhost:18800/api/evolution/history
```

### Via Python

```python
from labclaw.evolution.engine import EvolutionEngine
from labclaw.core.schemas import EvolutionTarget

engine = EvolutionEngine()

# Measure baseline
baseline = engine.measure_fitness(
    target=EvolutionTarget.ANALYSIS_PARAMS,
    metrics={"pattern_count": 10.0, "coverage": 0.7},
)

# Propose candidates
candidates = engine.propose_candidates(EvolutionTarget.ANALYSIS_PARAMS, n=3)

# Start cycle
cycle = engine.start_cycle(candidates[0], baseline)

# Advance through stages
new_fitness = engine.measure_fitness(
    target=EvolutionTarget.ANALYSIS_PARAMS,
    metrics={"pattern_count": 14.0, "coverage": 0.85},
)
cycle = engine.advance_stage(cycle.cycle_id, new_fitness)
print(f"Stage: {cycle.stage}")
```

---

## Setting Up Safety Rules

### Register Rules via Governance Engine

```python
from labclaw.core.governance import GovernanceEngine, SafetyRule

gov = GovernanceEngine(audit_path=Path("logs/audit.jsonl"))

# Block dangerous actions
gov.register_rule(SafetyRule(
    name="no_laser_without_approval",
    description="Laser activation requires PI approval",
    check="require_approval_if",
    condition={"action": "execute", "device_type": "laser"},
))

gov.register_rule(SafetyRule(
    name="no_delete_raw_data",
    description="Raw data files cannot be deleted",
    check="deny_if",
    condition={"action": "delete", "target_type": "raw_data"},
))

# Check permissions
decision = gov.check(
    action="execute",
    actor="alice",
    role="graduate",
    context={"device_type": "laser"},
)
print(decision.allowed)          # True (graduate can execute)
print(decision.safety_level)     # REQUIRES_APPROVAL
print(decision.required_approvals)  # ["pi"]
```

### Built-in Roles

| Role | Permissions |
|------|------------|
| `pi` | Everything (`*`) |
| `postdoc` | read, write, execute, approve |
| `graduate` | read, write, execute |
| `undergraduate` | read, write |
| `technician` | read, write, calibrate |
| `digital_intern` | read |
| `digital_analyst` | read, analyze |
| `digital_specialist` | read, analyze, propose |

### Audit Log

Every governance check is recorded in an append-only JSON Lines audit log:

```python
# Query audit log
entries = gov.audit_log.query(actor="alice", limit=10)
for entry in entries:
    print(f"{entry.timestamp}: {entry.action} -> {entry.decision.allowed}")
```

---

## Monitoring with Health Checks

### Health Endpoint

```bash
curl http://localhost:18800/api/health
# {"status": "ok", "version": "0.0.2"}
```

### Status Endpoint

```bash
curl http://localhost:18800/api/status
# {"status": "ok", "version": "0.0.2", "registered_events": 42, "registered_devices": 3}
```

### Docker Health Check

The Dockerfile includes a built-in health check:

```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:18800/health')"
```

### Monitoring with systemd

When deployed as a systemd service, check status with:

```bash
systemctl status labclaw
journalctl -u labclaw -f
```
