"""Tier B: Temporal knowledge graph — structured entities and relationships.

Spec: docs/specs/L4-memory.md (Tier B)
Design doc: Section 6 (Memory Architecture)

Lightweight in-memory implementation of a temporal knowledge graph.
Supports entity CRUD, typed edges (relations), neighbor traversal,
and text search. Uses GraphNode types from core/graph.py.

Designed as a drop-in replacement interface for future Graphiti backend.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from labclaw.core.events import event_registry
from labclaw.core.graph import GraphNode

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Register events
# ---------------------------------------------------------------------------

_KG_EVENTS = [
    "memory.tier_b.node_added",
    "memory.tier_b.node_updated",
    "memory.tier_b.node_removed",
    "memory.tier_b.edge_added",
    "memory.tier_b.edge_removed",
    "memory.tier_b.search_executed",
]

for _evt in _KG_EVENTS:
    if not event_registry.is_registered(_evt):
        event_registry.register(_evt)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class KGEdge(BaseModel):
    """A directed edge between two graph nodes."""

    edge_id: str = Field(default_factory=_uuid)
    source_id: str
    target_id: str
    relation: str  # e.g. "belongs_to", "produced_by", "used_in"
    properties: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_now)


class KGSearchResult(BaseModel):
    """A search result from the knowledge graph."""

    node: GraphNode
    score: float
    matched_field: str  # which field matched


class KGQueryFilter(BaseModel):
    """Filter for querying nodes."""

    node_type: str | None = None
    tags: list[str] = Field(default_factory=list)
    created_after: datetime | None = None
    created_before: datetime | None = None
    metadata_filter: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# TierBBackend
# ---------------------------------------------------------------------------


class TierBBackend:
    """In-memory temporal knowledge graph.

    Stores GraphNode entities and typed edges between them.
    Supports CRUD, neighbor traversal, and text search.

    This is a lightweight implementation for development.
    Production use should swap in the Graphiti-backed version.
    """

    def __init__(self, max_nodes: int = 50_000) -> None:
        self._max_nodes = max_nodes
        self._nodes: dict[str, GraphNode] = {}
        self._edges: dict[str, KGEdge] = {}
        # Index: source_id -> list of edge_ids
        self._outgoing: dict[str, list[str]] = {}
        # Index: target_id -> list of edge_ids
        self._incoming: dict[str, list[str]] = {}
        # Index: node_type -> set of node_ids
        self._type_index: dict[str, set[str]] = {}

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        return len(self._edges)

    # ----- Node CRUD -----

    def add_node(self, node: GraphNode) -> GraphNode:
        """Add a node to the graph. Returns the node (with generated ID if needed).

        Raises ValueError if node_id already exists.
        """
        if node.node_id in self._nodes:
            raise ValueError(f"Node {node.node_id!r} already exists")

        if len(self._nodes) + 1 >= int(self._max_nodes * 0.8):
            logger.warning(
                "Knowledge graph at %d%% capacity (%d/%d nodes)",
                int(100 * len(self._nodes) / self._max_nodes),
                len(self._nodes),
                self._max_nodes,
            )

        if len(self._nodes) >= self._max_nodes:
            oldest_id = min(self._nodes, key=lambda nid: self._nodes[nid].created_at)
            self.remove_node(oldest_id)

        self._nodes[node.node_id] = node
        self._type_index.setdefault(node.node_type, set()).add(node.node_id)

        event_registry.emit(
            "memory.tier_b.node_added",
            payload={
                "node_id": node.node_id,
                "node_type": node.node_type,
            },
        )
        return node

    def get_node(self, node_id: str) -> GraphNode:
        """Retrieve a node by ID. Raises KeyError if not found."""
        try:
            return self._nodes[node_id]
        except KeyError:
            raise KeyError(f"Node {node_id!r} not found in knowledge graph") from None

    def update_node(self, node_id: str, **fields: Any) -> GraphNode:
        """Update fields on an existing node. Returns updated node.

        Raises KeyError if node not found.
        """
        existing = self.get_node(node_id)
        update_data = existing.model_dump()
        update_data.update(fields)
        update_data["updated_at"] = _now()

        old_type = existing.node_type
        updated = type(existing).model_validate(update_data)
        self._nodes[node_id] = updated

        # Update type index if type changed
        if updated.node_type != old_type:
            self._type_index.get(old_type, set()).discard(node_id)
            self._type_index.setdefault(updated.node_type, set()).add(node_id)

        event_registry.emit(
            "memory.tier_b.node_updated",
            payload={
                "node_id": node_id,
                "node_type": updated.node_type,
                "updated_fields": list(fields.keys()),
            },
        )
        return updated

    def remove_node(self, node_id: str) -> None:
        """Remove a node and all its edges. Raises KeyError if not found."""
        node = self.get_node(node_id)

        # Remove all edges connected to this node
        edge_ids_to_remove = set()
        edge_ids_to_remove.update(self._outgoing.get(node_id, []))
        edge_ids_to_remove.update(self._incoming.get(node_id, []))

        for eid in edge_ids_to_remove:
            self._remove_edge_internal(eid)

        # Remove from type index
        self._type_index.get(node.node_type, set()).discard(node_id)

        # Remove node
        del self._nodes[node_id]

        event_registry.emit(
            "memory.tier_b.node_removed",
            payload={"node_id": node_id, "node_type": node.node_type},
        )

    # ----- Edge CRUD -----

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        relation: str,
        properties: dict[str, Any] | None = None,
    ) -> KGEdge:
        """Add a directed edge between two nodes.

        Raises KeyError if either node doesn't exist.
        """
        self.get_node(source_id)  # Validate source exists
        self.get_node(target_id)  # Validate target exists

        edge = KGEdge(
            source_id=source_id,
            target_id=target_id,
            relation=relation,
            properties=properties or {},
        )
        self._edges[edge.edge_id] = edge
        self._outgoing.setdefault(source_id, []).append(edge.edge_id)
        self._incoming.setdefault(target_id, []).append(edge.edge_id)

        event_registry.emit(
            "memory.tier_b.edge_added",
            payload={
                "edge_id": edge.edge_id,
                "source_id": source_id,
                "target_id": target_id,
                "relation": relation,
            },
        )
        return edge

    def get_edge(self, edge_id: str) -> KGEdge:
        """Retrieve an edge by ID. Raises KeyError if not found."""
        try:
            return self._edges[edge_id]
        except KeyError:
            raise KeyError(f"Edge {edge_id!r} not found") from None

    def remove_edge(self, edge_id: str) -> None:
        """Remove an edge by ID. Raises KeyError if not found."""
        edge = self.get_edge(edge_id)
        self._remove_edge_internal(edge_id)

        event_registry.emit(
            "memory.tier_b.edge_removed",
            payload={
                "edge_id": edge_id,
                "source_id": edge.source_id,
                "target_id": edge.target_id,
                "relation": edge.relation,
            },
        )

    def _remove_edge_internal(self, edge_id: str) -> None:
        """Remove an edge from all indices (no event emitted)."""
        edge = self._edges.pop(edge_id, None)
        if edge is None:
            return
        out_list = self._outgoing.get(edge.source_id, [])
        if edge_id in out_list:
            out_list.remove(edge_id)
        in_list = self._incoming.get(edge.target_id, [])
        if edge_id in in_list:
            in_list.remove(edge_id)

    # ----- Query -----

    def query_nodes(self, filter: KGQueryFilter) -> list[GraphNode]:
        """Query nodes by type, tags, time range, or metadata."""
        candidates: set[str] | None = None

        # Narrow by type
        if filter.node_type is not None:
            candidates = set(self._type_index.get(filter.node_type, set()))

        results: list[GraphNode] = []
        node_ids = candidates if candidates is not None else set(self._nodes.keys())

        for nid in node_ids:
            node = self._nodes.get(nid)
            if node is None:
                continue

            # Tag filter: all specified tags must be present
            if filter.tags and not all(t in node.tags for t in filter.tags):
                continue

            # Time range
            if filter.created_after and node.created_at < filter.created_after:
                continue
            if filter.created_before and node.created_at > filter.created_before:
                continue

            # Metadata filter: all key-value pairs must match
            if filter.metadata_filter:
                match = all(node.metadata.get(k) == v for k, v in filter.metadata_filter.items())
                if not match:
                    continue

            results.append(node)

        return results

    def get_neighbors(
        self,
        node_id: str,
        relation: str | None = None,
        direction: str = "both",
    ) -> list[tuple[GraphNode, KGEdge]]:
        """Get neighboring nodes connected by edges.

        Args:
            node_id: The node to find neighbors of.
            relation: Filter by edge relation type (None = all).
            direction: "outgoing", "incoming", or "both".

        Returns:
            List of (neighbor_node, edge) tuples.
        """
        self.get_node(node_id)  # Validate node exists
        results: list[tuple[GraphNode, KGEdge]] = []

        if direction in ("outgoing", "both"):
            for eid in self._outgoing.get(node_id, []):
                edge = self._edges.get(eid)
                if edge is None:
                    continue
                if relation and edge.relation != relation:
                    continue
                neighbor = self._nodes.get(edge.target_id)
                if neighbor is not None:
                    results.append((neighbor, edge))

        if direction in ("incoming", "both"):
            for eid in self._incoming.get(node_id, []):
                edge = self._edges.get(eid)
                if edge is None:
                    continue
                if relation and edge.relation != relation:
                    continue
                neighbor = self._nodes.get(edge.source_id)
                if neighbor is not None:
                    results.append((neighbor, edge))

        return results

    def get_edges_between(
        self,
        source_id: str,
        target_id: str,
        relation: str | None = None,
    ) -> list[KGEdge]:
        """Get all edges between two specific nodes."""
        edges: list[KGEdge] = []
        for eid in self._outgoing.get(source_id, []):
            edge = self._edges.get(eid)
            if edge is None:
                continue
            if edge.target_id != target_id:
                continue
            if relation and edge.relation != relation:
                continue
            edges.append(edge)
        return edges

    # ----- Search -----

    def search(self, query: str, limit: int = 10) -> list[KGSearchResult]:
        """Text search across all node fields.

        Case-insensitive substring matching on stringified node fields.
        Returns results ranked by match score.
        """
        query_lower = query.lower()
        query_terms = query_lower.split()
        results: list[KGSearchResult] = []

        for node in self._nodes.values():
            best_score = 0.0
            best_field = ""

            # Search across all string-representable fields
            data = node.model_dump()
            for field_name, value in data.items():
                text = str(value).lower()
                score = sum(text.count(term) for term in query_terms)
                if score > best_score:
                    best_score = score
                    best_field = field_name

            if best_score > 0:
                results.append(
                    KGSearchResult(
                        node=node,
                        score=best_score,
                        matched_field=best_field,
                    )
                )

        results.sort(key=lambda r: r.score, reverse=True)
        results = results[:limit]

        event_registry.emit(
            "memory.tier_b.search_executed",
            payload={"query": query, "result_count": len(results)},
        )
        return results

    # ----- Utility -----

    def clear(self) -> None:
        """Remove all nodes and edges. For testing."""
        self._nodes.clear()
        self._edges.clear()
        self._outgoing.clear()
        self._incoming.clear()
        self._type_index.clear()

    def all_nodes(self) -> list[GraphNode]:
        """Return all nodes in the graph."""
        return list(self._nodes.values())

    def all_edges(self) -> list[KGEdge]:
        """Return all edges in the graph."""
        return list(self._edges.values())


# ---------------------------------------------------------------------------
# SQLite-backed backend (production)
# ---------------------------------------------------------------------------

from labclaw.memory.sqlite_backend import SQLiteTierBBackend  # noqa: E402


def create_tier_b_backend(
    db_path: str | None = None,
    *,
    in_memory: bool = False,
) -> TierBBackend | SQLiteTierBBackend:
    """Factory: create the appropriate KG backend.

    By default uses SQLiteTierBBackend for persistence across restarts.
    Set ``in_memory=True`` to use the lightweight in-memory backend (tests).
    """
    if in_memory:
        return TierBBackend()
    return SQLiteTierBBackend(db_path or "data/knowledge_graph.db")


__all__ = [
    "KGEdge",
    "KGQueryFilter",
    "KGSearchResult",
    "SQLiteTierBBackend",
    "TierBBackend",
    "create_tier_b_backend",
]
