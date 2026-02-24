"""Memory — the lab's super brain.

Spec: docs/specs/L4-memory.md
Design doc: Section 6 (Memory Architecture)

Three-tier architecture:
  Tier A: Human-readable markdown (OpenClaw pattern) — implemented
  Tier B: Temporal knowledge graph — in-memory (TierBBackend) and SQLite (SQLiteTierBBackend)
  Tier C: Agent shared blocks (key-value working memory) — implemented
"""

from __future__ import annotations

from labclaw.memory.knowledge_graph import (
    KGEdge,
    KGQueryFilter,
    KGSearchResult,
    SQLiteTierBBackend,
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
from labclaw.memory.shared_blocks import TierCBackend

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
    "SQLiteTierBBackend",
    "SearchResult",
    "TierABackend",
    "TierBBackend",
    "TierCBackend",
]
