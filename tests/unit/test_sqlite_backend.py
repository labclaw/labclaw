"""Tests for SQLite-backed Tier B knowledge graph."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio

from labclaw.core.events import event_registry
from labclaw.core.graph import GraphNode, PersonNode
from labclaw.memory.knowledge_graph import KGQueryFilter
from labclaw.memory.sqlite_backend import SQLiteTierBBackend


@pytest_asyncio.fixture
async def backend(tmp_path: Path):
    db_path = tmp_path / "test_kg.db"
    b = SQLiteTierBBackend(db_path)
    await b.init_db()
    yield b
    await b.close()


def _make_person(name: str, **kwargs) -> PersonNode:
    return PersonNode(name=name, **kwargs)


# ---------------------------------------------------------------------------
# init_db / close
# ---------------------------------------------------------------------------


class TestInitAndClose:
    @pytest.mark.asyncio
    async def test_init_creates_tables(self, tmp_path: Path) -> None:
        db_path = tmp_path / "sub" / "test.db"
        b = SQLiteTierBBackend(db_path)
        await b.init_db()
        assert db_path.exists()
        await b.close()

    @pytest.mark.asyncio
    async def test_close_works(self, backend: SQLiteTierBBackend) -> None:
        await backend.close()
        assert backend._db is None

    @pytest.mark.asyncio
    async def test_not_initialized_raises(self, tmp_path: Path) -> None:
        b = SQLiteTierBBackend(tmp_path / "nope.db")
        with pytest.raises(RuntimeError, match="not initialized"):
            await b.add_node(_make_person("Alice"))


# ---------------------------------------------------------------------------
# Node CRUD
# ---------------------------------------------------------------------------


class TestNodeCRUD:
    @pytest.mark.asyncio
    async def test_add_and_get_roundtrip(self, backend: SQLiteTierBBackend) -> None:
        node = _make_person("Alice", tags=["pi"], metadata={"lab": "neuro"})
        result = await backend.add_node(node)
        assert result.node_id == node.node_id

        fetched = await backend.get_node(node.node_id)
        assert fetched.node_id == node.node_id
        assert fetched.node_type == "person"

    @pytest.mark.asyncio
    async def test_add_duplicate_raises(self, backend: SQLiteTierBBackend) -> None:
        node = _make_person("Alice")
        await backend.add_node(node)
        with pytest.raises(ValueError, match="already exists"):
            await backend.add_node(node)

    @pytest.mark.asyncio
    async def test_get_missing_raises(self, backend: SQLiteTierBBackend) -> None:
        with pytest.raises(KeyError, match="not found"):
            await backend.get_node("nonexistent-id")

    @pytest.mark.asyncio
    async def test_update_node(self, backend: SQLiteTierBBackend) -> None:
        node = _make_person("Alice")
        await backend.add_node(node)
        updated = await backend.update_node(node.node_id, name="Bob")
        assert updated.name == "Bob"  # type: ignore[attr-defined]
        assert updated.updated_at > node.updated_at

    @pytest.mark.asyncio
    async def test_update_missing_raises(self, backend: SQLiteTierBBackend) -> None:
        with pytest.raises(KeyError):
            await backend.update_node("nope", name="X")

    @pytest.mark.asyncio
    async def test_remove_node(self, backend: SQLiteTierBBackend) -> None:
        node = _make_person("Alice")
        await backend.add_node(node)
        await backend.remove_node(node.node_id)
        with pytest.raises(KeyError):
            await backend.get_node(node.node_id)

    @pytest.mark.asyncio
    async def test_remove_node_removes_connected_edges(self, backend: SQLiteTierBBackend) -> None:
        n1 = _make_person("Alice")
        n2 = _make_person("Bob")
        await backend.add_node(n1)
        await backend.add_node(n2)
        edge = await backend.add_edge(n1.node_id, n2.node_id, "knows")
        await backend.remove_node(n1.node_id)
        with pytest.raises(KeyError):
            await backend.get_edge(edge.edge_id)

    @pytest.mark.asyncio
    async def test_remove_missing_raises(self, backend: SQLiteTierBBackend) -> None:
        with pytest.raises(KeyError):
            await backend.remove_node("nope")

    @pytest.mark.asyncio
    async def test_node_count(self, backend: SQLiteTierBBackend) -> None:
        assert await backend.node_count() == 0
        await backend.add_node(_make_person("A"))
        await backend.add_node(_make_person("B"))
        assert await backend.node_count() == 2


# ---------------------------------------------------------------------------
# Edge CRUD
# ---------------------------------------------------------------------------


class TestEdgeCRUD:
    @pytest.mark.asyncio
    async def test_add_and_get_roundtrip(self, backend: SQLiteTierBBackend) -> None:
        n1 = _make_person("Alice")
        n2 = _make_person("Bob")
        await backend.add_node(n1)
        await backend.add_node(n2)

        edge = await backend.add_edge(n1.node_id, n2.node_id, "collaborates", {"weight": 5})
        assert edge.source_id == n1.node_id
        assert edge.relation == "collaborates"

        fetched = await backend.get_edge(edge.edge_id)
        assert fetched.edge_id == edge.edge_id
        assert fetched.properties == {"weight": 5}

    @pytest.mark.asyncio
    async def test_add_edge_missing_node_raises(self, backend: SQLiteTierBBackend) -> None:
        n1 = _make_person("Alice")
        await backend.add_node(n1)
        with pytest.raises(KeyError):
            await backend.add_edge(n1.node_id, "nonexistent", "knows")

    @pytest.mark.asyncio
    async def test_get_edge_missing_raises(self, backend: SQLiteTierBBackend) -> None:
        with pytest.raises(KeyError, match="not found"):
            await backend.get_edge("nonexistent-edge")

    @pytest.mark.asyncio
    async def test_remove_edge(self, backend: SQLiteTierBBackend) -> None:
        n1 = _make_person("Alice")
        n2 = _make_person("Bob")
        await backend.add_node(n1)
        await backend.add_node(n2)
        edge = await backend.add_edge(n1.node_id, n2.node_id, "knows")
        await backend.remove_edge(edge.edge_id)
        with pytest.raises(KeyError):
            await backend.get_edge(edge.edge_id)

    @pytest.mark.asyncio
    async def test_remove_edge_missing_raises(self, backend: SQLiteTierBBackend) -> None:
        with pytest.raises(KeyError):
            await backend.remove_edge("nope")

    @pytest.mark.asyncio
    async def test_edge_count(self, backend: SQLiteTierBBackend) -> None:
        n1 = _make_person("Alice")
        n2 = _make_person("Bob")
        await backend.add_node(n1)
        await backend.add_node(n2)
        assert await backend.edge_count() == 0
        await backend.add_edge(n1.node_id, n2.node_id, "knows")
        assert await backend.edge_count() == 1


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------


class TestQueryNodes:
    @pytest.mark.asyncio
    async def test_query_by_type(self, backend: SQLiteTierBBackend) -> None:
        await backend.add_node(_make_person("Alice"))
        node2 = GraphNode(node_type="experiment")
        await backend.add_node(node2)

        results = await backend.query_nodes(KGQueryFilter(node_type="person"))
        assert len(results) == 1
        assert results[0].node_type == "person"

    @pytest.mark.asyncio
    async def test_query_by_tags(self, backend: SQLiteTierBBackend) -> None:
        await backend.add_node(_make_person("Alice", tags=["pi", "neuro"]))
        await backend.add_node(_make_person("Bob", tags=["student"]))

        results = await backend.query_nodes(KGQueryFilter(tags=["pi"]))
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_query_by_metadata(self, backend: SQLiteTierBBackend) -> None:
        await backend.add_node(_make_person("Alice", metadata={"lab": "neuro"}))
        await backend.add_node(_make_person("Bob", metadata={"lab": "chem"}))

        results = await backend.query_nodes(KGQueryFilter(metadata_filter={"lab": "neuro"}))
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_query_by_time_range(self, backend: SQLiteTierBBackend) -> None:
        now = datetime.now(UTC)
        n1 = _make_person("Old")
        n1.created_at = now - timedelta(days=10)
        n1.updated_at = n1.created_at
        await backend.add_node(n1)

        n2 = _make_person("New")
        n2.created_at = now
        n2.updated_at = n2.created_at
        await backend.add_node(n2)

        results = await backend.query_nodes(KGQueryFilter(created_after=now - timedelta(days=1)))
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_query_all(self, backend: SQLiteTierBBackend) -> None:
        await backend.add_node(_make_person("Alice"))
        await backend.add_node(_make_person("Bob"))
        results = await backend.query_nodes(KGQueryFilter())
        assert len(results) == 2


# ---------------------------------------------------------------------------
# Neighbors
# ---------------------------------------------------------------------------


class TestGetNeighbors:
    @pytest.mark.asyncio
    async def test_outgoing(self, backend: SQLiteTierBBackend) -> None:
        n1 = _make_person("Alice")
        n2 = _make_person("Bob")
        await backend.add_node(n1)
        await backend.add_node(n2)
        await backend.add_edge(n1.node_id, n2.node_id, "knows")

        neighbors = await backend.get_neighbors(n1.node_id, direction="outgoing")
        assert len(neighbors) == 1
        assert neighbors[0][0].node_id == n2.node_id

    @pytest.mark.asyncio
    async def test_incoming(self, backend: SQLiteTierBBackend) -> None:
        n1 = _make_person("Alice")
        n2 = _make_person("Bob")
        await backend.add_node(n1)
        await backend.add_node(n2)
        await backend.add_edge(n1.node_id, n2.node_id, "knows")

        neighbors = await backend.get_neighbors(n2.node_id, direction="incoming")
        assert len(neighbors) == 1
        assert neighbors[0][0].node_id == n1.node_id

    @pytest.mark.asyncio
    async def test_both(self, backend: SQLiteTierBBackend) -> None:
        n1 = _make_person("Alice")
        n2 = _make_person("Bob")
        n3 = _make_person("Carol")
        await backend.add_node(n1)
        await backend.add_node(n2)
        await backend.add_node(n3)
        await backend.add_edge(n1.node_id, n2.node_id, "knows")
        await backend.add_edge(n3.node_id, n2.node_id, "knows")

        neighbors = await backend.get_neighbors(n2.node_id, direction="both")
        assert len(neighbors) == 2

    @pytest.mark.asyncio
    async def test_filter_by_relation(self, backend: SQLiteTierBBackend) -> None:
        n1 = _make_person("Alice")
        n2 = _make_person("Bob")
        await backend.add_node(n1)
        await backend.add_node(n2)
        await backend.add_edge(n1.node_id, n2.node_id, "knows")
        await backend.add_edge(n1.node_id, n2.node_id, "supervises")

        neighbors = await backend.get_neighbors(
            n1.node_id, relation="supervises", direction="outgoing"
        )
        assert len(neighbors) == 1
        assert neighbors[0][1].relation == "supervises"


# ---------------------------------------------------------------------------
# Search (FTS5)
# ---------------------------------------------------------------------------


class TestSearch:
    @pytest.mark.asyncio
    async def test_fts_search(self, backend: SQLiteTierBBackend) -> None:
        await backend.add_node(_make_person("Alice Neuroscientist", tags=["pi"]))
        await backend.add_node(_make_person("Bob Engineer"))

        results = await backend.search("Alice")
        assert len(results) >= 1
        assert results[0].node.node_id is not None

    @pytest.mark.asyncio
    async def test_empty_query(self, backend: SQLiteTierBBackend) -> None:
        results = await backend.search("")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_emits_event(self, backend: SQLiteTierBBackend) -> None:
        await backend.add_node(_make_person("Alice"))
        events: list = []
        event_registry.subscribe("memory.tier_b.search_executed", events.append)
        await backend.search("Alice")
        assert any(e.payload["query"] == "Alice" for e in events)

    @pytest.mark.asyncio
    async def test_search_with_limit(self, backend: SQLiteTierBBackend) -> None:
        for i in range(5):
            await backend.add_node(_make_person(f"Person{i}"))
        results = await backend.search("Person", limit=2)
        assert len(results) <= 2


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


class TestEvents:
    @pytest.mark.asyncio
    async def test_node_added_event(self, backend: SQLiteTierBBackend) -> None:
        events: list = []
        event_registry.subscribe("memory.tier_b.node_added", events.append)
        node = _make_person("Alice")
        await backend.add_node(node)
        assert any(e.payload["node_id"] == node.node_id for e in events)

    @pytest.mark.asyncio
    async def test_node_updated_event(self, backend: SQLiteTierBBackend) -> None:
        events: list = []
        event_registry.subscribe("memory.tier_b.node_updated", events.append)
        node = _make_person("Alice")
        await backend.add_node(node)
        await backend.update_node(node.node_id, name="Bob")
        assert any(
            e.payload["node_id"] == node.node_id and "name" in e.payload["updated_fields"]
            for e in events
        )

    @pytest.mark.asyncio
    async def test_node_removed_event(self, backend: SQLiteTierBBackend) -> None:
        events: list = []
        event_registry.subscribe("memory.tier_b.node_removed", events.append)
        node = _make_person("Alice")
        await backend.add_node(node)
        await backend.remove_node(node.node_id)
        assert any(e.payload["node_id"] == node.node_id for e in events)

    @pytest.mark.asyncio
    async def test_edge_added_event(self, backend: SQLiteTierBBackend) -> None:
        events: list = []
        event_registry.subscribe("memory.tier_b.edge_added", events.append)
        n1 = _make_person("Alice")
        n2 = _make_person("Bob")
        await backend.add_node(n1)
        await backend.add_node(n2)
        edge = await backend.add_edge(n1.node_id, n2.node_id, "knows")
        assert any(e.payload["edge_id"] == edge.edge_id for e in events)

    @pytest.mark.asyncio
    async def test_edge_removed_event(self, backend: SQLiteTierBBackend) -> None:
        events: list = []
        event_registry.subscribe("memory.tier_b.edge_removed", events.append)
        n1 = _make_person("Alice")
        n2 = _make_person("Bob")
        await backend.add_node(n1)
        await backend.add_node(n2)
        edge = await backend.add_edge(n1.node_id, n2.node_id, "knows")
        await backend.remove_edge(edge.edge_id)
        assert any(e.payload["edge_id"] == edge.edge_id for e in events)
