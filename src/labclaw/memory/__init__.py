"""Memory — the lab's super brain.

Spec: docs/specs/L4-memory.md
Design doc: Section 6 (Memory Architecture)

Three-tier architecture:
  Tier A: Human-readable markdown (OpenClaw pattern) — implemented
  Tier B: Temporal knowledge graph (in-memory) — implemented
  Tier C: Agent shared state (Letta pattern) — stub
"""

from __future__ import annotations

from labclaw.memory.knowledge_graph import (
    KGEdge,
    KGQueryFilter,
    KGSearchResult,
    TierBBackend,
)
from labclaw.memory.markdown import (
    MarkdownDoc,
    MemoryEntry,
    SearchResult,
    TierABackend,
)
from labclaw.memory.search import (
    HybridSearchConfig,
    HybridSearchEngine,
    HybridSearchQuery,
    HybridSearchResult,
)

__all__ = [
    "HybridSearchConfig",
    "HybridSearchEngine",
    "HybridSearchQuery",
    "HybridSearchResult",
    "KGEdge",
    "KGQueryFilter",
    "KGSearchResult",
    "MarkdownDoc",
    "MemoryEntry",
    "SearchResult",
    "TierABackend",
    "TierBBackend",
]
