"""Tests for TierBBackend in labclaw.memory.knowledge_graph.

Covers: node CRUD, edge CRUD, query, neighbors, get_edges_between, search,
and utility methods. Targets all uncovered lines identified in the coverage
report.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from labclaw.core.graph import GraphNode
from labclaw.memory.knowledge_graph import KGQueryFilter, TierBBackend

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _node(node_id: str, node_type: str = "experiment", **kw: object) -> GraphNode:
    """Build a minimal GraphNode with a fixed ID."""
    return GraphNode(node_id=node_id, node_type=node_type, **kw)  # type: ignore[arg-type]


def _fresh() -> TierBBackend:
    return TierBBackend()


# ---------------------------------------------------------------------------
# Node CRUD
# ---------------------------------------------------------------------------


def test_add_and_get_node() -> None:
    """add_node returns the node; get_node retrieves it by ID."""
    backend = _fresh()
    node = _node("n1", "experiment")
    returned = backend.add_node(node)
    assert returned.node_id == "n1"
    fetched = backend.get_node("n1")
    assert fetched.node_id == "n1"
    assert fetched.node_type == "experiment"


def test_add_duplicate_raises() -> None:
    """Adding a node with an already-present ID raises ValueError."""
    backend = _fresh()
    node = _node("dup")
    backend.add_node(node)
    with pytest.raises(ValueError, match="already exists"):
        backend.add_node(_node("dup"))


def test_add_node_capacity_warning(caplog: pytest.LogCaptureFixture) -> None:
    """At 80% capacity a warning is logged but the add still succeeds."""
    backend = TierBBackend(max_nodes=5)
    # Adding the 4th node brings (4+1)/5 = 100% → triggers warning at len+1 >= 4 (80% of 5)
    # Actually threshold: len(nodes)+1 >= int(5*0.8) = 4
    # So adding node #4 triggers the warning (before adding, len=3, 3+1=4 >= 4)
    for i in range(3):
        backend.add_node(_node(f"n{i}"))
    with caplog.at_level("WARNING", logger="labclaw.memory.knowledge_graph"):
        backend.add_node(_node("n3"))
    assert backend.node_count == 4
    assert any("capacity" in r.message for r in caplog.records)


def test_add_node_evicts_oldest_at_max() -> None:
    """When max_nodes is reached the oldest node is evicted before adding the new one."""
    backend = TierBBackend(max_nodes=3)
    t0 = datetime(2024, 1, 1, tzinfo=UTC)
    for i in range(3):
        n = GraphNode(
            node_id=f"n{i}",
            node_type="experiment",
            created_at=t0 + timedelta(hours=i),
        )
        backend.add_node(n)
    # n0 is oldest; adding n3 should evict n0
    backend.add_node(_node("n3"))
    assert backend.node_count == 3
    with pytest.raises(KeyError):
        backend.get_node("n0")
    backend.get_node("n3")  # new node is present


def test_get_node_not_found() -> None:
    """get_node raises KeyError for an unknown node_id."""
    backend = _fresh()
    with pytest.raises(KeyError, match="not found"):
        backend.get_node("missing")


def test_update_node() -> None:
    """update_node changes a field and returns the updated node."""
    backend = _fresh()
    backend.add_node(_node("n1", metadata={"status": "new"}))
    updated = backend.update_node("n1", metadata={"status": "done"})
    assert updated.metadata["status"] == "done"
    assert backend.get_node("n1").metadata["status"] == "done"


def test_update_node_type_change_updates_index() -> None:
    """When node_type changes, the type index is updated correctly."""
    backend = _fresh()
    backend.add_node(_node("n1", "alpha"))
    backend.update_node("n1", node_type="beta")
    # Query by old type should return nothing
    alpha_nodes = backend.query_nodes(KGQueryFilter(node_type="alpha"))
    beta_nodes = backend.query_nodes(KGQueryFilter(node_type="beta"))
    assert not any(n.node_id == "n1" for n in alpha_nodes)
    assert any(n.node_id == "n1" for n in beta_nodes)


def test_update_node_not_found() -> None:
    """update_node raises KeyError for an unknown node_id."""
    backend = _fresh()
    with pytest.raises(KeyError):
        backend.update_node("ghost", metadata={})


def test_remove_node() -> None:
    """remove_node deletes the node and any attached edges."""
    backend = _fresh()
    backend.add_node(_node("a"))
    backend.add_node(_node("b"))
    backend.add_edge("a", "b", "related")
    backend.remove_node("a")
    assert backend.node_count == 1
    with pytest.raises(KeyError):
        backend.get_node("a")
    # Edge must also be gone
    assert backend.edge_count == 0


def test_remove_node_not_found() -> None:
    """remove_node raises KeyError when node does not exist."""
    backend = _fresh()
    with pytest.raises(KeyError):
        backend.remove_node("ghost")


# ---------------------------------------------------------------------------
# Edge CRUD
# ---------------------------------------------------------------------------


def test_add_edge() -> None:
    """add_edge creates an edge with the correct relation and source/target."""
    backend = _fresh()
    backend.add_node(_node("a"))
    backend.add_node(_node("b"))
    edge = backend.add_edge("a", "b", "links_to")
    assert edge.source_id == "a"
    assert edge.target_id == "b"
    assert edge.relation == "links_to"
    assert backend.edge_count == 1


def test_add_edge_missing_source() -> None:
    """add_edge raises KeyError when the source node does not exist."""
    backend = _fresh()
    backend.add_node(_node("b"))
    with pytest.raises(KeyError):
        backend.add_edge("missing_src", "b", "x")


def test_get_edge() -> None:
    """get_edge retrieves a previously added edge by its ID."""
    backend = _fresh()
    backend.add_node(_node("a"))
    backend.add_node(_node("b"))
    edge = backend.add_edge("a", "b", "foo")
    fetched = backend.get_edge(edge.edge_id)
    assert fetched.edge_id == edge.edge_id
    assert fetched.relation == "foo"


def test_get_edge_not_found() -> None:
    """get_edge raises KeyError for an unknown edge_id."""
    backend = _fresh()
    with pytest.raises(KeyError, match="not found"):
        backend.get_edge("nonexistent-edge-id")


def test_remove_edge() -> None:
    """remove_edge deletes the edge; edge_count decreases."""
    backend = _fresh()
    backend.add_node(_node("a"))
    backend.add_node(_node("b"))
    edge = backend.add_edge("a", "b", "bar")
    assert backend.edge_count == 1
    backend.remove_edge(edge.edge_id)
    assert backend.edge_count == 0


def test_remove_edge_not_found() -> None:
    """remove_edge raises KeyError when edge_id does not exist."""
    backend = _fresh()
    with pytest.raises(KeyError):
        backend.remove_edge("ghost-edge")


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------


def test_query_by_type() -> None:
    """query_nodes with node_type filter returns only matching nodes."""
    backend = _fresh()
    backend.add_node(_node("a", "experiment"))
    backend.add_node(_node("b", "session"))
    backend.add_node(_node("c", "experiment"))
    results = backend.query_nodes(KGQueryFilter(node_type="experiment"))
    ids = {n.node_id for n in results}
    assert ids == {"a", "c"}


def test_query_by_tags() -> None:
    """query_nodes with tags filter returns nodes containing all specified tags."""
    backend = _fresh()
    backend.add_node(GraphNode(node_id="tagged", node_type="t", tags=["foo", "bar"]))
    backend.add_node(GraphNode(node_id="partial", node_type="t", tags=["foo"]))
    backend.add_node(GraphNode(node_id="none", node_type="t", tags=[]))
    results = backend.query_nodes(KGQueryFilter(tags=["foo", "bar"]))
    assert len(results) == 1
    assert results[0].node_id == "tagged"


def test_query_by_time_range() -> None:
    """created_after / created_before filter nodes by creation timestamp."""
    backend = _fresh()
    base = datetime(2024, 6, 1, 12, 0, 0, tzinfo=UTC)
    early = GraphNode(node_id="early", node_type="t", created_at=base - timedelta(days=10))
    mid = GraphNode(node_id="mid", node_type="t", created_at=base)
    late = GraphNode(node_id="late", node_type="t", created_at=base + timedelta(days=10))
    for n in (early, mid, late):
        backend.add_node(n)

    results = backend.query_nodes(
        KGQueryFilter(
            created_after=base - timedelta(days=1),
            created_before=base + timedelta(days=1),
        )
    )
    ids = {n.node_id for n in results}
    assert ids == {"mid"}


def test_query_by_metadata() -> None:
    """metadata_filter requires all key-value pairs to match."""
    backend = _fresh()
    backend.add_node(GraphNode(node_id="match", node_type="t", metadata={"env": "prod", "v": 2}))
    backend.add_node(GraphNode(node_id="partial", node_type="t", metadata={"env": "prod"}))
    backend.add_node(GraphNode(node_id="other", node_type="t", metadata={"env": "dev"}))
    results = backend.query_nodes(KGQueryFilter(metadata_filter={"env": "prod", "v": 2}))
    assert len(results) == 1
    assert results[0].node_id == "match"


# ---------------------------------------------------------------------------
# Neighbors
# ---------------------------------------------------------------------------


def test_get_neighbors_outgoing() -> None:
    """direction='outgoing' returns only nodes reachable along outgoing edges."""
    backend = _fresh()
    backend.add_node(_node("a"))
    backend.add_node(_node("b"))
    backend.add_edge("a", "b", "next")
    neighbors = backend.get_neighbors("a", direction="outgoing")
    assert len(neighbors) == 1
    neighbor_node, edge = neighbors[0]
    assert neighbor_node.node_id == "b"
    assert edge.relation == "next"


def test_get_neighbors_incoming() -> None:
    """direction='incoming' returns nodes that have edges pointing to the queried node."""
    backend = _fresh()
    backend.add_node(_node("a"))
    backend.add_node(_node("b"))
    backend.add_edge("a", "b", "next")
    neighbors = backend.get_neighbors("b", direction="incoming")
    assert len(neighbors) == 1
    neighbor_node, _ = neighbors[0]
    assert neighbor_node.node_id == "a"


def test_get_neighbors_both() -> None:
    """direction='both' returns neighbors connected by any edge."""
    backend = _fresh()
    backend.add_node(_node("a"))
    backend.add_node(_node("b"))
    backend.add_node(_node("c"))
    backend.add_edge("a", "b", "out")  # a→b
    backend.add_edge("c", "a", "in")   # c→a
    neighbors = backend.get_neighbors("a", direction="both")
    ids = {n.node_id for n, _ in neighbors}
    assert "b" in ids  # outgoing
    assert "c" in ids  # incoming


def test_get_neighbors_with_relation_filter() -> None:
    """Relation filter restricts neighbors to edges with the given relation."""
    backend = _fresh()
    backend.add_node(_node("a"))
    backend.add_node(_node("b"))
    backend.add_node(_node("c"))
    backend.add_edge("a", "b", "foo")
    backend.add_edge("a", "c", "bar")
    foo_neighbors = backend.get_neighbors("a", relation="foo", direction="outgoing")
    assert len(foo_neighbors) == 1
    assert foo_neighbors[0][0].node_id == "b"


# ---------------------------------------------------------------------------
# get_edges_between
# ---------------------------------------------------------------------------


def test_get_edges_between() -> None:
    """get_edges_between returns edges between two nodes, filtered by relation."""
    backend = _fresh()
    backend.add_node(_node("a"))
    backend.add_node(_node("b"))
    e1 = backend.add_edge("a", "b", "rel1")
    e2 = backend.add_edge("a", "b", "rel2")
    # No relation filter → both edges
    all_edges = backend.get_edges_between("a", "b")
    assert {e.edge_id for e in all_edges} == {e1.edge_id, e2.edge_id}
    # Filtered by relation
    rel1_edges = backend.get_edges_between("a", "b", relation="rel1")
    assert len(rel1_edges) == 1
    assert rel1_edges[0].relation == "rel1"


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


def test_search_matches_node_fields() -> None:
    """search finds nodes whose fields contain the query string."""
    backend = _fresh()
    backend.add_node(_node("exp1", "experiment"))
    backend.add_node(_node("sess1", "session"))
    results = backend.search("experiment")
    ids = {r.node.node_id for r in results}
    assert "exp1" in ids
    assert "sess1" not in ids


def test_search_respects_limit() -> None:
    """search with limit=2 returns at most 2 results even when more match."""
    backend = _fresh()
    for i in range(5):
        backend.add_node(_node(f"node{i}", "experiment"))
    results = backend.search("experiment", limit=2)
    assert len(results) == 2


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def test_clear() -> None:
    """clear() removes all nodes and edges."""
    backend = _fresh()
    backend.add_node(_node("a"))
    backend.add_node(_node("b"))
    backend.add_edge("a", "b", "link")
    backend.clear()
    assert backend.node_count == 0
    assert backend.edge_count == 0


def test_all_nodes() -> None:
    """all_nodes() returns every node in the graph."""
    backend = _fresh()
    backend.add_node(_node("x"))
    backend.add_node(_node("y"))
    ids = {n.node_id for n in backend.all_nodes()}
    assert ids == {"x", "y"}


def test_all_edges() -> None:
    """all_edges() returns every edge in the graph."""
    backend = _fresh()
    backend.add_node(_node("a"))
    backend.add_node(_node("b"))
    e = backend.add_edge("a", "b", "z")
    edges = backend.all_edges()
    assert len(edges) == 1
    assert edges[0].edge_id == e.edge_id


def test_node_count_and_edge_count() -> None:
    """node_count and edge_count properties reflect current graph size."""
    backend = _fresh()
    assert backend.node_count == 0
    assert backend.edge_count == 0
    backend.add_node(_node("a"))
    backend.add_node(_node("b"))
    assert backend.node_count == 2
    edge = backend.add_edge("a", "b", "r")
    assert backend.edge_count == 1
    backend.remove_edge(edge.edge_id)
    assert backend.edge_count == 0
