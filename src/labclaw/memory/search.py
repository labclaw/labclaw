"""Hybrid search across all memory tiers.

Spec: docs/specs/L4-memory.md (HybridSearchQuery)
Design doc: Section 6 (Memory Architecture)

Combines:
  - BM25-like keyword search across Tier A (markdown files)
  - Entity search across Tier B (knowledge graph)
  - Temporal decay weighting (recent results scored higher)
  - Combined ranking with configurable tier weights
"""

from __future__ import annotations

import logging
import math
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from labclaw.core.events import event_registry
from labclaw.memory.knowledge_graph import TierBBackend
from labclaw.memory.markdown import SearchResult, TierABackend

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Register events
# ---------------------------------------------------------------------------

_SEARCH_EVENTS = [
    "memory.hybrid_search.executed",
]

for _evt in _SEARCH_EVENTS:
    if not event_registry.is_registered(_evt):
        event_registry.register(_evt)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class HybridSearchQuery(BaseModel):
    """Query for hybrid (text + graph) memory search."""

    text: str
    limit: int = 10
    tiers: list[str] = Field(default_factory=lambda: ["a", "b"])
    entity_filter: str | None = None


class HybridSearchResult(BaseModel):
    """A single result from hybrid search with provenance."""

    entity_id: str
    snippet: str
    score: float
    source_tier: str  # "a" or "b"
    source_detail: str  # "soul", "memory", "node:<type>", etc.
    matched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class HybridSearchConfig(BaseModel):
    """Configuration for hybrid search behavior."""

    tier_a_weight: float = 1.0
    tier_b_weight: float = 1.0
    temporal_decay_half_life_days: float = 30.0
    enable_temporal_decay: bool = False


# ---------------------------------------------------------------------------
# HybridSearchEngine
# ---------------------------------------------------------------------------


class HybridSearchEngine:
    """Combines search across Tier A (markdown) and Tier B (knowledge graph).

    Spec: docs/specs/L4-memory.md
    """

    def __init__(
        self,
        tier_a: TierABackend | None = None,
        tier_b: TierBBackend | None = None,
        config: HybridSearchConfig | None = None,
    ) -> None:
        self._tier_a = tier_a
        self._tier_b = tier_b
        self._config = config or HybridSearchConfig()

    def search(self, query: HybridSearchQuery) -> list[HybridSearchResult]:
        """Run hybrid search across configured tiers.

        Returns results sorted by combined score (descending).
        """
        results: list[HybridSearchResult] = []

        if "a" in query.tiers and self._tier_a is not None:
            results.extend(self._search_tier_a(query))

        if "b" in query.tiers and self._tier_b is not None:
            results.extend(self._search_tier_b(query))

        # Apply temporal decay if enabled
        if self._config.enable_temporal_decay:
            now = datetime.now(UTC)
            half_life = self._config.temporal_decay_half_life_days
            for r in results:
                age_days = (now - r.matched_at).total_seconds() / 86400.0
                decay = math.pow(0.5, age_days / half_life) if half_life > 0 else 1.0
                r.score *= decay

        # Sort by score descending and limit
        results.sort(key=lambda r: r.score, reverse=True)
        results = results[: query.limit]

        event_registry.emit(
            "memory.hybrid_search.executed",
            payload={
                "query": query.text,
                "tiers": query.tiers,
                "result_count": len(results),
            },
        )
        return results

    def _search_tier_a(self, query: HybridSearchQuery) -> list[HybridSearchResult]:
        """Search Tier A (markdown memory)."""
        assert self._tier_a is not None
        weight = self._config.tier_a_weight
        tier_a_results: list[SearchResult] = self._tier_a.search(query.text, limit=query.limit * 2)

        hybrid_results: list[HybridSearchResult] = []
        for r in tier_a_results:
            if query.entity_filter and r.entity_id != query.entity_filter:
                continue
            hybrid_results.append(
                HybridSearchResult(
                    entity_id=r.entity_id,
                    snippet=r.snippet,
                    score=r.score * weight,
                    source_tier="a",
                    source_detail=r.source,
                )
            )
        return hybrid_results

    def _search_tier_b(self, query: HybridSearchQuery) -> list[HybridSearchResult]:
        """Search Tier B (knowledge graph)."""
        assert self._tier_b is not None
        weight = self._config.tier_b_weight
        kg_results = self._tier_b.search(query.text, limit=query.limit * 2)

        hybrid_results: list[HybridSearchResult] = []
        for r in kg_results:
            node_id = r.node.node_id
            node_type = r.node.node_type
            if query.entity_filter and node_id != query.entity_filter:
                continue

            # Build snippet from node data
            data = r.node.model_dump()
            snippet_parts: list[str] = []
            for key in ("name", "summary", "description", "subject_label", "title"):
                if key in data and data[key]:
                    snippet_parts.append(f"{key}: {data[key]}")
            snippet = "; ".join(snippet_parts) if snippet_parts else f"[{node_type}] {node_id}"

            hybrid_results.append(
                HybridSearchResult(
                    entity_id=node_id,
                    snippet=snippet[:200],
                    score=r.score * weight,
                    source_tier="b",
                    source_detail=f"node:{node_type}",
                    matched_at=r.node.created_at,
                )
            )
        return hybrid_results
