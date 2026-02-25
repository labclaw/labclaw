# Memory System

LabClaw uses a three-tier memory architecture. Each tier is optimized for a
different access pattern: human readability, structured queries, and agent
working state.

---

## Overview

| Tier | Name | Storage | Purpose |
|------|------|---------|---------|
| A | Human-Readable | Markdown files (git) | Lab identity, protocols, decisions, daily stream |
| B | Knowledge Graph | SQLite + FTS5 | Structured entities, relations, temporal tracking |
| C | Agent Working Memory | SQLite key-value | Per-agent state, shared blocks between agents |

Data flows downward: Tier A is the source of truth, Tier B indexes structured
facts extracted from it, and Tier C holds transient agent state.

---

## Tier A: Markdown Memory

### Concept

Tier A stores lab knowledge as plain markdown files. These are the source of truth
-- readable and editable with any text editor, version-controlled in git.

### File Layout

```
{memory_root}/
  {entity_id}/
    SOUL.md       # Identity, mission, capabilities
    MEMORY.md     # Append-only timestamped log
```

Entities include the lab itself, team members (human and digital), and devices.

### SOUL.md

Contains YAML frontmatter and markdown body describing an entity's identity:

```markdown
---
name: LabClaw
type: lab
created: 2026-01-15
---

# LabClaw

## Identity

Motor control and decision-making in freely moving rodents.

## Mission

Understand neural circuit dynamics during goal-directed behavior.
```

### MEMORY.md

Append-only log of timestamped entries:

```markdown
## 2026-02-20T14:30:00+00:00

**Category:** discovery

Cycle abc123: 5 patterns, 2 hypotheses

## 2026-02-20T15:00:00+00:00

**Category:** evolution

New cycle def456 started
```

### Python API

```python
from pathlib import Path
from datetime import datetime, UTC
from labclaw.memory.markdown import TierABackend, MemoryEntry, MarkdownDoc

backend = TierABackend(Path("lab"))

# Read SOUL.md
soul = backend.read_soul("lab")
print(soul.frontmatter)  # {"name": "LabClaw", "type": "lab", ...}
print(soul.content)       # Markdown body

# Write SOUL.md
doc = MarkdownDoc(
    path=Path("lab/new-member/SOUL.md"),
    frontmatter={"name": "Alice", "role": "graduate"},
    content="# Alice\n\nPhD student studying motor cortex.",
)
backend.write_soul("new-member", doc)

# Append to MEMORY.md
entry = MemoryEntry(
    timestamp=datetime.now(UTC),
    category="observation",
    detail="Mouse 12 showed increased grooming behavior.",
)
backend.append_memory("lab", entry)

# Read MEMORY.md
memory = backend.read_memory("lab")
print(memory.content)
```

### Search

Tier A search uses substring matching with term-frequency scoring:

```python
results = backend.search("calcium imaging", limit=5)
for r in results:
    print(f"  {r.entity_id}/{r.source}: {r.snippet} (score={r.score})")
```

Search scans all SOUL.md and MEMORY.md files, scoring by case-insensitive
term count. Results include a snippet around the first match.

### Thread Safety

`append_memory` uses per-file locking to prevent lost entries when multiple
threads or the daemon's concurrent loops write simultaneously.

---

## Tier B: Knowledge Graph

### Concept

Tier B stores structured entities and relationships in a SQLite database with
FTS5 (full-text search) indexing. It provides temporal tracking for when facts
were created and updated.

### Schema

**Nodes table:**

| Column | Type | Description |
|--------|------|-------------|
| `node_id` | TEXT (PK) | Unique node identifier |
| `node_type` | TEXT | Node type (e.g. "session", "recording", "finding") |
| `data_json` | TEXT | Full node data as JSON |
| `created_at` | TEXT | ISO 8601 creation timestamp |
| `updated_at` | TEXT | ISO 8601 last update timestamp |

**Edges table:**

| Column | Type | Description |
|--------|------|-------------|
| `edge_id` | TEXT (PK) | Unique edge identifier |
| `source_id` | TEXT (FK) | Source node ID |
| `target_id` | TEXT (FK) | Target node ID |
| `relation` | TEXT | Relationship type (e.g. "produced_by", "supports") |
| `properties_json` | TEXT | Edge properties as JSON |
| `created_at` | TEXT | ISO 8601 creation timestamp |

**FTS5 index:**

A virtual table `nodes_fts` indexes all node content using the Porter stemmer
for full-text search.

### Built-in Node Types

| Type | Class | Description |
|------|-------|-------------|
| `session` | `SessionNode` | An experimental session |
| `recording` | `RecordingNode` | A data file from a session |
| `analysis` | `AnalysisNode` | An analysis result |
| `parameter` | `ParameterNode` | An experimental parameter |
| `finding` | `FindingNode` | A discovered finding |

### Python API

```python
from pathlib import Path
from labclaw.memory.sqlite_backend import SQLiteTierBBackend
from labclaw.core.graph import GraphNode, SessionNode

backend = SQLiteTierBBackend(Path("data/labclaw.db"))
await backend.init_db()

# Add nodes
session = SessionNode(name="Session 001", operator="alice")
await backend.add_node(session)

# Get node
node = await backend.get_node(session.node_id)

# Update node
updated = await backend.update_node(session.node_id, name="Session 001 (updated)")

# Add edges
await backend.add_edge(
    source_id=session.node_id,
    target_id=recording.node_id,
    relation="contains",
    properties={"modality": "ephys"},
)

# Query nodes
from labclaw.memory.knowledge_graph import KGQueryFilter
results = await backend.query_nodes(KGQueryFilter(
    node_type="session",
    tags=["neuroscience"],
))

# Get neighbors
neighbors = await backend.get_neighbors(session.node_id, direction="outgoing")
for node, edge in neighbors:
    print(f"  {edge.relation} -> {node.name}")

# Full-text search
results = await backend.search("firing rate correlation")
for r in results:
    print(f"  {r.node.name}: score={r.score}")

# Statistics
print(f"Nodes: {await backend.node_count()}")
print(f"Edges: {await backend.edge_count()}")

await backend.close()
```

### Query Filters

`KGQueryFilter` supports:

| Field | Type | Description |
|-------|------|-------------|
| `node_type` | string | Filter by node type |
| `created_after` | datetime | Nodes created after this time |
| `created_before` | datetime | Nodes created before this time |
| `tags` | list of strings | All specified tags must be present |
| `metadata_filter` | dict | All key-value pairs must match |

---

## Tier C: Agent Working Memory

### Concept

Tier C is a key-value store for agent working memory. Agents use it to persist
state between conversations and share data with other agents. Backed by SQLite
when a path is provided, or in-memory for testing.

### Schema

| Column | Type | Description |
|--------|------|-------------|
| `key` | TEXT (PK) | Block key (e.g. "current_hypothesis") |
| `value_json` | TEXT | Block value as JSON |
| `agent_id` | TEXT | Agent that owns this block |
| `created_at` | TEXT | ISO 8601 creation timestamp |
| `updated_at` | TEXT | ISO 8601 last update timestamp |

### Python API

```python
from pathlib import Path
from labclaw.memory.shared_blocks import TierCBackend

blocks = TierCBackend(Path("data/blocks.db"))
await blocks.init_db()

# Set a block
await blocks.set_block(
    "current_hypothesis",
    {"text": "Firing rate predicts accuracy", "confidence": 0.85},
    agent_id="lab-assistant",
)

# Get a block
block = await blocks.get_block("current_hypothesis")
# {"text": "...", "confidence": 0.85, "_meta": {"agent_id": "lab-assistant", ...}}

# List blocks
all_keys = await blocks.list_blocks()
agent_keys = await blocks.list_blocks(agent_id="lab-assistant")

# Get all blocks as dict
all_blocks = await blocks.get_all_blocks()

# Delete a block
existed = await blocks.delete_block("current_hypothesis")

await blocks.close()
```

### In-Memory Mode

Omit the `db_path` for a pure in-memory store (useful for testing):

```python
blocks = TierCBackend()  # No db_path = in-memory
# No init_db() needed
await blocks.set_block("test", {"value": 1})
```

---

## How Tiers Relate

```
   Tier A (Markdown)          Tier B (Knowledge Graph)        Tier C (Agent State)
  ┌───────────────────┐      ┌──────────────────────┐      ┌──────────────────┐
  │  SOUL.md           │      │  Nodes               │      │  Key-Value Store │
  │  MEMORY.md         │ ───> │  Edges               │      │  Per-agent blocks│
  │  protocols/        │      │  FTS5 Search          │      │  Shared state    │
  └───────────────────┘      └──────────────────────┘      └──────────────────┘
        │                           │                              │
        │  Source of truth          │  Structured queries          │  Real-time state
        │  Git-tracked              │  Temporal tracking           │  Agent coordination
        │  Human-editable           │  Relationship traversal      │  Fast read/write
```

- **Tier A -> Tier B**: The daemon extracts structured facts from markdown files
  and indexes them as graph nodes. Findings from the scientific loop are written
  to both tiers.

- **Tier B -> Tier C**: Agents query the knowledge graph for context and store
  working conclusions in Tier C blocks.

- **Tier C -> Tier A**: When agents reach conclusions, they write summaries
  back to Tier A MEMORY.md for human review.

---

## Memory Search Across Tiers

The `HybridSearchEngine` provides unified search across all tiers:

```python
from labclaw.memory.search import HybridSearchEngine, HybridSearchQuery

engine = HybridSearchEngine(tier_a=tier_a_backend)

results = engine.search(HybridSearchQuery(
    text="calcium imaging fluorescence",
    limit=10,
))

for r in results:
    print(f"  [{r.source_tier}] {r.entity_id}: {r.snippet} (score={r.score})")
```

MCP tools and agent tools use this engine internally.
