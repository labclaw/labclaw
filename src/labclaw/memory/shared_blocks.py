"""Tier C: Agent shared state — real-time coordination between agents.

Spec: docs/specs/L4-memory.md (Tier C stub)
Design doc: Section 6 (Memory Architecture)

Implements Letta-style shared memory blocks for multi-agent collaboration:
  - insert: append-only, concurrency-safe
  - replace: validated, prevents accidental overwrite
  - rethink: full rewrite, last-writer-wins (use carefully)

NOT YET IMPLEMENTED — raises NotImplementedError on access.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SharedBlock(BaseModel):
    """A shared memory block for multi-agent collaboration."""

    block_id: str
    label: str
    value: str
    limit: int = 5000


class HybridSearchQuery(BaseModel):
    """Query for hybrid (text + graph) memory search."""

    text: str
    entity_filter: list[str] = Field(default_factory=list)
    limit: int = 10


class TierCBackend:
    """Stub for Letta-based agent shared state."""

    def __init__(self) -> None:
        raise NotImplementedError(
            "Tier C (Shared Blocks) is not yet implemented. "
            "See docs/specs/L4-memory.md for the planned interface."
        )
