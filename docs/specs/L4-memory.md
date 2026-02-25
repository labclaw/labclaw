# L4 Memory Spec

**Layer:** Memory (L4)
**Design doc reference:** Section 6 (Memory Architecture), Section 10.4 (Memory Tier Consistency)

## Purpose

The Memory layer is the lab's persistent "super brain." It stores identity (SOUL.md), history (MEMORY.md), and knowledge for every entity — lab, members, devices — and makes that knowledge searchable.

Three tiers, with Tier A as MVP:

| Tier | Pattern | Storage | Status |
|------|---------|---------|--------|
| A: Human-Readable | OpenClaw | Markdown files (git) | **This spec** |
| B: Knowledge Graph | Graphiti | FalkorDB/SQLite | Stub |
| C: Shared Blocks | Letta | In-memory + SQLite | Stub |

**Tier A is the source of truth.** Tiers B and C are derived/ephemeral and can be fully rebuilt from Tier A.

---

## Pydantic Schemas

### MemoryEntry

A single timestamped entry appended to MEMORY.md.

```python
class MemoryEntry(BaseModel):
    timestamp: datetime    # UTC, ISO 8601
    category: str          # e.g. "protocol", "analysis_error", "decision"
    detail: str            # Free-text description
```

### MarkdownDoc

Parsed representation of a SOUL.md or MEMORY.md file.

```python
class MarkdownDoc(BaseModel):
    path: Path                      # Absolute path to the file
    frontmatter: dict[str, Any]     # YAML frontmatter (between --- markers)
    content: str                    # Markdown body after frontmatter
```

### SearchResult

A single result from memory search.

```python
class SearchResult(BaseModel):
    entity_id: str    # Which entity matched
    snippet: str      # Matched text snippet
    score: float      # Relevance score (higher = better)
    source: str       # "soul" or "memory"
```

### SharedBlock (Tier C stub)

```python
class SharedBlock(BaseModel):
    block_id: str
    label: str
    value: str
    limit: int = 5000  # Character limit
```

### HybridSearchQuery (stub)

```python
class HybridSearchQuery(BaseModel):
    text: str
    limit: int = 10
    tiers: list[str] = ["a", "b"]  # Which tiers to search
    entity_filter: str | None = None
```

---

## Public Interface: TierABackend

```python
class TierABackend:
    def __init__(self, root: Path) -> None:
        """Initialize with root directory containing entity subdirectories."""

    def read_soul(self, entity_id: str) -> MarkdownDoc:
        """Read {root}/{entity_id}/SOUL.md. Raises FileNotFoundError if missing."""

    def read_memory(self, entity_id: str) -> MarkdownDoc:
        """Read {root}/{entity_id}/MEMORY.md. Raises FileNotFoundError if missing."""

    def write_soul(self, entity_id: str, doc: MarkdownDoc) -> None:
        """Write SOUL.md with frontmatter + content. Creates directory if needed.
        Emits memory.tier_a.created (new) or memory.tier_a.updated (existing)."""

    def append_memory(self, entity_id: str, entry: MemoryEntry) -> None:
        """Append a timestamped entry to MEMORY.md. Creates file if needed.
        Uses a per-file in-process lock to serialize concurrent appends.
        Emits memory.tier_a.updated."""

    def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        """Substring search across all MEMORY.md and SOUL.md files.
        Returns results ranked by match count (occurrences of query terms).
        Emits memory.search.executed."""
```

---

## Events

| Event Name | Trigger | Payload |
|------------|---------|---------|
| `memory.tier_a.created` | New SOUL.md written | `{"entity_id": str, "path": str}` |
| `memory.tier_a.updated` | SOUL.md overwritten or MEMORY.md appended | `{"entity_id": str, "path": str}` |
| `memory.search.executed` | `search()` called | `{"query": str, "result_count": int}` |

Events are registered at module import time via the global `event_registry`.

---

## Boundary Contracts

- All timestamps MUST be timezone-aware UTC.
- Entity IDs MUST match regex `[A-Za-z0-9][A-Za-z0-9._-]{0,127}`.
- SOUL.md MUST have valid YAML frontmatter between `---` markers.
- MEMORY.md entries are append-only; entries are never deleted or modified.
- File paths are `pathlib.Path` objects throughout.
- Frontmatter parsed with PyYAML (`yaml.safe_load`).
- `append_memory()` serializes read/modify/write with a per-file lock shared across
  all `TierABackend` instances in the same process.
- Concurrency guarantee scope is process-local only (no cross-process/distributed lock).

### REST API Contracts (Tier A)

- `/api/memory/{entity_id}/soul`, `/api/memory/{entity_id}/memory`,
  and `/api/memory/{entity_id}/memory` (POST) enforce the same `entity_id` regex
  and return `400` on invalid IDs.
- `/api/memory/search/query` validates `limit >= 1`; invalid limits return `422`.

---

## Error Conditions

| Condition | Exception | Message |
|-----------|-----------|---------|
| `read_soul()` for nonexistent entity | `FileNotFoundError` | Includes entity_id and expected path |
| `read_memory()` for nonexistent entity | `FileNotFoundError` | Includes entity_id and expected path |
| SOUL.md with malformed YAML frontmatter | `ValueError` | Includes parse error details |
| Empty entity_id | `ValueError` | "entity_id must be non-empty" |
| Invalid entity_id format | `ValueError` | "entity_id must match [A-Za-z0-9][A-Za-z0-9._-]{0,127}" |
| API search `limit < 1` | HTTP `422` | FastAPI validation error (query parameter `limit`) |

---

## Storage

### Directory Layout

```
{root}/
  {entity_id}/
    SOUL.md      # Identity: frontmatter (YAML) + markdown body
    MEMORY.md    # History: append-only timestamped entries
```

### SOUL.md Format

```markdown
---
name: LabClaw
type: lab
created: 2026-02-19T00:00:00Z
---

# LabClaw

Mission, values, and identity description...
```

### MEMORY.md Format

```markdown
## 2026-02-19T10:30:00+00:00

**Category:** protocol

Updated staining protocol to include 30-minute wash step.

## 2026-02-19T14:15:00+00:00

**Category:** analysis_error

Used wrong baseline for calcium signal normalization. Corrected to use first 5 seconds.
```

---

## Acceptance Criteria

- [ ] `TierABackend` reads and writes SOUL.md with valid YAML frontmatter
- [ ] `TierABackend` appends timestamped entries to MEMORY.md
- [ ] MEMORY.md is created on first append (no pre-existing file required)
- [ ] Entity directories are created on first `write_soul()` call
- [ ] `read_soul()` raises `FileNotFoundError` for missing entities
- [ ] `search()` returns ranked results across all entities
- [ ] Events `memory.tier_a.created`, `memory.tier_a.updated`, `memory.search.executed` are emitted
- [ ] All models importable from `labclaw.memory`
- [ ] Tier B and Tier C stubs raise `NotImplementedError`
