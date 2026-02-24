"""Tests for HybridSearchEngine from labclaw.memory.search."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from labclaw.core.graph import GraphNode
from labclaw.memory.knowledge_graph import KGSearchResult, TierBBackend
from labclaw.memory.markdown import SearchResult
from labclaw.memory.search import (
    HybridSearchConfig,
    HybridSearchEngine,
    HybridSearchQuery,
)


def _make_tier_a_mock(results: list[SearchResult]) -> MagicMock:
    """Return a mock TierABackend whose .search() returns the given results."""
    tier_a = MagicMock()
    tier_a.search.return_value = results
    return tier_a


def _sr(entity_id: str, score: float, source: str = "soul") -> SearchResult:
    return SearchResult(
        entity_id=entity_id, snippet=f"snippet for {entity_id}", score=score, source=source
    )


# ---------------------------------------------------------------------------
# Basic search behaviour
# ---------------------------------------------------------------------------


def test_search_empty_no_tiers() -> None:
    """Engine with no backends configured returns an empty list."""
    engine = HybridSearchEngine()
    query = HybridSearchQuery(text="test query")

    results = engine.search(query)

    assert results == []


def test_search_tier_a_only() -> None:
    """Tier A results are returned as HybridSearchResult with source_tier='a'."""
    tier_a = _make_tier_a_mock([_sr("e1", 0.9)])
    engine = HybridSearchEngine(tier_a=tier_a)
    query = HybridSearchQuery(text="hello", tiers=["a"])

    results = engine.search(query)

    assert len(results) == 1
    r = results[0]
    assert r.entity_id == "e1"
    assert r.source_tier == "a"
    assert r.score == pytest.approx(0.9)


def test_search_with_tier_a_weight() -> None:
    """Config tier_a_weight=2.0 multiplies the raw score by 2."""
    tier_a = _make_tier_a_mock([_sr("e1", 0.9)])
    config = HybridSearchConfig(tier_a_weight=2.0)
    engine = HybridSearchEngine(tier_a=tier_a, config=config)
    query = HybridSearchQuery(text="weighted", tiers=["a"])

    results = engine.search(query)

    assert len(results) == 1
    assert results[0].score == pytest.approx(0.9 * 2.0)


def test_search_entity_filter() -> None:
    """entity_filter restricts results to the matching entity_id only."""
    tier_a = _make_tier_a_mock([_sr("e1", 0.9), _sr("e2", 0.5)])
    engine = HybridSearchEngine(tier_a=tier_a)
    query = HybridSearchQuery(text="filter", tiers=["a"], entity_filter="e1")

    results = engine.search(query)

    assert len(results) == 1
    assert results[0].entity_id == "e1"


def test_search_sorts_by_score_descending() -> None:
    """Results are sorted by score descending regardless of input order."""
    tier_a = _make_tier_a_mock([
        _sr("low", 0.2),
        _sr("high", 0.95),
        _sr("mid", 0.6),
    ])
    engine = HybridSearchEngine(tier_a=tier_a)
    query = HybridSearchQuery(text="sort", tiers=["a"])

    results = engine.search(query)

    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)
    assert results[0].entity_id == "high"


def test_search_respects_limit() -> None:
    """Query with limit=1 returns at most 1 result even when more are available."""
    tier_a = _make_tier_a_mock([_sr("a", 0.9), _sr("b", 0.8), _sr("c", 0.7)])
    engine = HybridSearchEngine(tier_a=tier_a)
    query = HybridSearchQuery(text="limit", tiers=["a"], limit=1)

    results = engine.search(query)

    assert len(results) == 1
    assert results[0].entity_id == "a"


# ---------------------------------------------------------------------------
# Temporal decay
# ---------------------------------------------------------------------------


def test_temporal_decay_reduces_scores() -> None:
    """Temporal decay (half_life=30d) reduces scores; matched_at=now gives ~1.0 decay factor."""
    tier_a = _make_tier_a_mock([_sr("fresh", 1.0)])
    config = HybridSearchConfig(enable_temporal_decay=True, temporal_decay_half_life_days=30.0)
    engine = HybridSearchEngine(tier_a=tier_a, config=config)
    query = HybridSearchQuery(text="decay", tiers=["a"])

    results = engine.search(query)

    # The decay for age≈0 days is very close to 1.0, so score is ≤ 1.0
    assert len(results) == 1
    assert results[0].score <= 1.0
    # And it should be very close to the original score (not zero)
    assert results[0].score > 0.99


# ---------------------------------------------------------------------------
# Schema defaults
# ---------------------------------------------------------------------------


def test_hybrid_search_query_defaults() -> None:
    """HybridSearchQuery(text=...) has limit=10 and tiers=['a','b'] by default."""
    query = HybridSearchQuery(text="test")

    assert query.limit == 10
    assert query.tiers == ["a", "b"]
    assert query.entity_filter is None


def test_hybrid_search_config_defaults() -> None:
    """HybridSearchConfig() has expected default values."""
    config = HybridSearchConfig()

    assert config.tier_a_weight == pytest.approx(1.0)
    assert config.tier_b_weight == pytest.approx(1.0)
    assert config.temporal_decay_half_life_days == pytest.approx(30.0)
    assert config.enable_temporal_decay is False


# ---------------------------------------------------------------------------
# Tier B search
# ---------------------------------------------------------------------------


def _kg_result(node_id: str, node_type: str = "experiment", score: float = 0.8) -> KGSearchResult:
    """Build a KGSearchResult with a plain GraphNode."""
    node = GraphNode(node_id=node_id, node_type=node_type)
    return KGSearchResult(node=node, score=score, matched_field="node_type")


def _make_tier_b_mock(results: list[KGSearchResult]) -> MagicMock:
    """Return a mock TierBBackend whose .search() returns the given results."""
    tier_b = MagicMock(spec=TierBBackend)
    tier_b.search.return_value = results
    return tier_b


def test_search_tier_b_only() -> None:
    """Tier B results appear with source_tier='b' and source_detail='node:<type>'."""
    tier_b = _make_tier_b_mock([_kg_result("n1", "experiment", score=0.8)])
    engine = HybridSearchEngine(tier_b=tier_b)
    query = HybridSearchQuery(text="experiment", tiers=["b"])

    results = engine.search(query)

    assert len(results) == 1
    r = results[0]
    assert r.entity_id == "n1"
    assert r.source_tier == "b"
    assert r.source_detail == "node:experiment"
    assert r.score == pytest.approx(0.8)


def test_search_tier_b_entity_filter() -> None:
    """entity_filter restricts tier B results to the matching node_id."""
    tier_b = _make_tier_b_mock([
        _kg_result("n1", score=0.9),
        _kg_result("n2", score=0.7),
    ])
    engine = HybridSearchEngine(tier_b=tier_b)
    query = HybridSearchQuery(text="exp", tiers=["b"], entity_filter="n1")

    results = engine.search(query)

    assert len(results) == 1
    assert results[0].entity_id == "n1"

    # entity_filter that matches nothing → empty
    query_no_match = HybridSearchQuery(text="exp", tiers=["b"], entity_filter="other")
    assert engine.search(query_no_match) == []


def test_search_tier_b_builds_snippet_from_name() -> None:
    """For a plain GraphNode (no name/summary/description), snippet is '[type] node_id'."""
    node = GraphNode(node_id="plain-node", node_type="session")
    kg_res = KGSearchResult(node=node, score=0.5, matched_field="node_type")
    tier_b = _make_tier_b_mock([kg_res])
    engine = HybridSearchEngine(tier_b=tier_b)
    query = HybridSearchQuery(text="session", tiers=["b"])

    results = engine.search(query)

    assert len(results) == 1
    assert results[0].snippet == "[session] plain-node"


def test_search_both_tiers() -> None:
    """When both tiers are active, results from A and B are combined and sorted."""
    tier_a = MagicMock()
    tier_a.search.return_value = [
        SearchResult(entity_id="a1", snippet="tier A result", score=0.6, source="soul"),
    ]
    tier_b = _make_tier_b_mock([_kg_result("b1", score=0.9)])

    engine = HybridSearchEngine(tier_a=tier_a, tier_b=tier_b)
    query = HybridSearchQuery(text="query", tiers=["a", "b"])

    results = engine.search(query)

    assert len(results) == 2
    # Highest score first
    assert results[0].entity_id == "b1"
    assert results[1].entity_id == "a1"
    tiers = {r.source_tier for r in results}
    assert tiers == {"a", "b"}
