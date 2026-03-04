from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from labclaw.api.app import app
from labclaw.api.deps import (
    get_session_chronicle,
    get_tier_a_backend,
    reset_all,
    set_memory_root,
)
from labclaw.core.events import event_registry


def _ensure_memory_events() -> None:
    for name in ("memory.tier_a.created", "memory.tier_a.updated", "memory.search.executed"):
        if not event_registry.is_registered(name):
            event_registry.register(name)


def test_memory_api_rejects_invalid_entity_id_on_append(tmp_path: Path) -> None:
    reset_all()
    try:
        _ensure_memory_events()
        set_memory_root(tmp_path / "memory")
        client = TestClient(app)

        resp = client.post("/api/memory/bad*id/memory", json={"category": "x", "detail": "y"})
        assert resp.status_code == 400
        assert "entity_id" in resp.json()["detail"]
    finally:
        reset_all()


def test_memory_api_rejects_invalid_entity_id_on_read(tmp_path: Path) -> None:
    reset_all()
    try:
        _ensure_memory_events()
        set_memory_root(tmp_path / "memory")
        client = TestClient(app)

        resp = client.get("/api/memory/bad*id/soul")
        assert resp.status_code == 400
        assert "entity_id" in resp.json()["detail"]
    finally:
        reset_all()


def test_memory_api_rejects_invalid_entity_id_on_memory_read(tmp_path: Path) -> None:
    reset_all()
    try:
        _ensure_memory_events()
        set_memory_root(tmp_path / "memory")
        client = TestClient(app)

        resp = client.get("/api/memory/bad*id/memory")
        assert resp.status_code == 400
        assert "entity_id" in resp.json()["detail"]
    finally:
        reset_all()


def test_memory_api_append_valid_entity_id_still_works(tmp_path: Path) -> None:
    reset_all()
    try:
        _ensure_memory_events()
        set_memory_root(tmp_path / "memory")
        client = TestClient(app)

        resp = client.post("/api/memory/lab_001/memory", json={"category": "x", "detail": "y"})
        assert resp.status_code == 201
        assert resp.json()["entity_id"] == "lab_001"
    finally:
        reset_all()


def test_set_memory_root_clears_chronicle_and_backend_cache(tmp_path: Path) -> None:
    reset_all()
    try:
        first_root = tmp_path / "memory-a"
        second_root = tmp_path / "memory-b"

        set_memory_root(first_root)
        first_backend = get_tier_a_backend()
        first_chronicle = get_session_chronicle()

        set_memory_root(second_root)
        second_backend = get_tier_a_backend()
        second_chronicle = get_session_chronicle()

        assert first_backend is not second_backend
        assert first_chronicle is not second_chronicle
        assert second_backend.root == second_root
        assert second_chronicle._memory is second_backend
    finally:
        reset_all()


def test_memory_api_rejects_invalid_search_limit(tmp_path: Path) -> None:
    reset_all()
    try:
        _ensure_memory_events()
        set_memory_root(tmp_path / "memory")
        client = TestClient(app)

        resp = client.get("/api/memory/search/query?q=test&limit=0")
        assert resp.status_code == 422
        assert "greater than or equal to 1" in resp.text
    finally:
        reset_all()


# ---------------------------------------------------------------------------
# Findings endpoint (lines 113-131)
# ---------------------------------------------------------------------------


class TestFindingsEndpoint:
    @pytest.mark.asyncio
    async def test_list_findings_returns_results(self, tmp_path: Path) -> None:
        """GET /api/memory/findings returns findings from SessionMemoryManager."""
        reset_all()
        try:
            mock_mgr = AsyncMock()
            mock_mgr.init = AsyncMock()
            mock_mgr.retrieve_findings = AsyncMock(
                return_value=[{"id": "f1", "text": "finding one"}]
            )
            mock_mgr.close = AsyncMock()

            with (
                patch("labclaw.api.deps._default_memory_root", return_value=tmp_path),
                patch(
                    "labclaw.memory.session_memory.SessionMemoryManager",
                    return_value=mock_mgr,
                ),
            ):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as c:
                    resp = await c.get("/api/memory/findings?q=test&limit=10")

            assert resp.status_code == 200
            body = resp.json()
            assert len(body) == 1
            assert body[0]["id"] == "f1"
            mock_mgr.init.assert_awaited_once()
            mock_mgr.retrieve_findings.assert_awaited_once_with(query="test")
            mock_mgr.close.assert_awaited_once()
        finally:
            reset_all()

    @pytest.mark.asyncio
    async def test_list_findings_empty_query(self, tmp_path: Path) -> None:
        """GET /api/memory/findings with no query returns all findings."""
        reset_all()
        try:
            mock_mgr = AsyncMock()
            mock_mgr.init = AsyncMock()
            mock_mgr.retrieve_findings = AsyncMock(return_value=[])
            mock_mgr.close = AsyncMock()

            with (
                patch("labclaw.api.deps._default_memory_root", return_value=tmp_path),
                patch(
                    "labclaw.memory.session_memory.SessionMemoryManager",
                    return_value=mock_mgr,
                ),
            ):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as c:
                    resp = await c.get("/api/memory/findings")

            assert resp.status_code == 200
            assert resp.json() == []
            mock_mgr.retrieve_findings.assert_awaited_once_with(query="")
        finally:
            reset_all()

    @pytest.mark.asyncio
    async def test_list_findings_respects_limit(self, tmp_path: Path) -> None:
        """GET /api/memory/findings truncates results to limit."""
        reset_all()
        try:
            many_findings = [{"id": f"f{i}"} for i in range(10)]
            mock_mgr = AsyncMock()
            mock_mgr.init = AsyncMock()
            mock_mgr.retrieve_findings = AsyncMock(return_value=many_findings)
            mock_mgr.close = AsyncMock()

            with (
                patch("labclaw.api.deps._default_memory_root", return_value=tmp_path),
                patch(
                    "labclaw.memory.session_memory.SessionMemoryManager",
                    return_value=mock_mgr,
                ),
            ):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as c:
                    resp = await c.get("/api/memory/findings?limit=3")

            assert resp.status_code == 200
            assert len(resp.json()) == 3
        finally:
            reset_all()


# ---------------------------------------------------------------------------
# KG nodes endpoint (lines 139-155)
# ---------------------------------------------------------------------------


class TestKGNodesEndpoint:
    @pytest.mark.asyncio
    async def test_list_kg_nodes_no_filter(self) -> None:
        """GET /api/memory/kg/nodes returns nodes from TierBBackend."""
        reset_all()
        try:
            from labclaw.core.graph import GraphNode

            node = GraphNode(node_id="n1", node_type="experiment")
            mock_kg = MagicMock()
            mock_kg.query_nodes.return_value = [node]

            with patch(
                "labclaw.memory.knowledge_graph.TierBBackend",
                return_value=mock_kg,
            ):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as c:
                    resp = await c.get("/api/memory/kg/nodes")

            assert resp.status_code == 200
            body = resp.json()
            assert len(body) == 1
            assert body[0]["node_id"] == "n1"
        finally:
            reset_all()

    @pytest.mark.asyncio
    async def test_list_kg_nodes_with_type_filter(self) -> None:
        """GET /api/memory/kg/nodes?node_type=X filters by type."""
        reset_all()
        try:
            from labclaw.core.graph import GraphNode

            mock_kg = MagicMock()
            mock_kg.query_nodes.return_value = [GraphNode(node_id="n2", node_type="finding")]

            with patch(
                "labclaw.memory.knowledge_graph.TierBBackend",
                return_value=mock_kg,
            ):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as c:
                    resp = await c.get("/api/memory/kg/nodes?node_type=finding")

            assert resp.status_code == 200
            # Verify KGQueryFilter was constructed with node_type
            call_args = mock_kg.query_nodes.call_args
            filt = call_args[0][0]
            assert filt.node_type == "finding"
        finally:
            reset_all()

    @pytest.mark.asyncio
    async def test_list_kg_nodes_with_label_filter(self) -> None:
        """GET /api/memory/kg/nodes?label=X filters by tag."""
        reset_all()
        try:
            from labclaw.core.graph import GraphNode

            mock_kg = MagicMock()
            mock_kg.query_nodes.return_value = [GraphNode(node_id="n3", node_type="hypothesis")]

            with patch(
                "labclaw.memory.knowledge_graph.TierBBackend",
                return_value=mock_kg,
            ):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as c:
                    resp = await c.get("/api/memory/kg/nodes?label=neuro")

            assert resp.status_code == 200
            call_args = mock_kg.query_nodes.call_args
            filt = call_args[0][0]
            assert filt.tags == ["neuro"]
        finally:
            reset_all()

    @pytest.mark.asyncio
    async def test_list_kg_nodes_respects_limit(self) -> None:
        """GET /api/memory/kg/nodes?limit=2 truncates results."""
        reset_all()
        try:
            from labclaw.core.graph import GraphNode

            nodes = [GraphNode(node_id=f"n{i}", node_type="x") for i in range(5)]
            mock_kg = MagicMock()
            mock_kg.query_nodes.return_value = nodes

            with patch(
                "labclaw.memory.knowledge_graph.TierBBackend",
                return_value=mock_kg,
            ):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as c:
                    resp = await c.get("/api/memory/kg/nodes?limit=2")

            assert resp.status_code == 200
            assert len(resp.json()) == 2
        finally:
            reset_all()


# ---------------------------------------------------------------------------
# KG neighbors endpoint (lines 158-177)
# ---------------------------------------------------------------------------


class TestKGNeighborsEndpoint:
    @pytest.mark.asyncio
    async def test_get_neighbors_success(self) -> None:
        """GET /api/memory/kg/neighbors/{node_id} returns neighbor nodes."""
        reset_all()
        try:
            from labclaw.core.graph import GraphNode

            node = GraphNode(node_id="center", node_type="experiment")
            neighbor = GraphNode(node_id="nb1", node_type="finding")
            mock_kg = MagicMock()
            mock_kg.get_node.return_value = node
            mock_kg.get_neighbors.return_value = [neighbor]

            with patch(
                "labclaw.memory.knowledge_graph.TierBBackend",
                return_value=mock_kg,
            ):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as c:
                    resp = await c.get("/api/memory/kg/neighbors/center")

            assert resp.status_code == 200
            body = resp.json()
            assert len(body) == 1
            assert body[0]["node_id"] == "nb1"
            mock_kg.get_neighbors.assert_called_once_with(
                "center", relation=None, direction="outgoing"
            )
        finally:
            reset_all()

    @pytest.mark.asyncio
    async def test_get_neighbors_with_relation_filter(self) -> None:
        """GET /api/memory/kg/neighbors/{id}?relation=X filters by relation."""
        reset_all()
        try:
            from labclaw.core.graph import GraphNode

            mock_kg = MagicMock()
            mock_kg.get_node.return_value = GraphNode(node_id="c1", node_type="exp")
            mock_kg.get_neighbors.return_value = []

            with patch(
                "labclaw.memory.knowledge_graph.TierBBackend",
                return_value=mock_kg,
            ):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as c:
                    resp = await c.get(
                        "/api/memory/kg/neighbors/c1?relation=caused_by&direction=incoming"
                    )

            assert resp.status_code == 200
            mock_kg.get_neighbors.assert_called_once_with(
                "c1", relation="caused_by", direction="incoming"
            )
        finally:
            reset_all()

    @pytest.mark.asyncio
    async def test_get_neighbors_node_not_found(self) -> None:
        """GET /api/memory/kg/neighbors/{id} with unknown node returns 404."""
        reset_all()
        try:
            mock_kg = MagicMock()
            mock_kg.get_node.return_value = None

            with patch(
                "labclaw.memory.knowledge_graph.TierBBackend",
                return_value=mock_kg,
            ):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as c:
                    resp = await c.get("/api/memory/kg/neighbors/nonexistent")

            assert resp.status_code == 404
            assert "nonexistent" in resp.json()["detail"]
        finally:
            reset_all()

    @pytest.mark.asyncio
    async def test_get_neighbors_respects_limit(self) -> None:
        """GET /api/memory/kg/neighbors/{id}?limit=1 truncates results."""
        reset_all()
        try:
            from labclaw.core.graph import GraphNode

            node = GraphNode(node_id="c2", node_type="exp")
            neighbors = [GraphNode(node_id=f"nb{i}", node_type="x") for i in range(5)]
            mock_kg = MagicMock()
            mock_kg.get_node.return_value = node
            mock_kg.get_neighbors.return_value = neighbors

            with patch(
                "labclaw.memory.knowledge_graph.TierBBackend",
                return_value=mock_kg,
            ):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as c:
                    resp = await c.get("/api/memory/kg/neighbors/c2?limit=1")

            assert resp.status_code == 200
            assert len(resp.json()) == 1
        finally:
            reset_all()
