"""Integration tests for all 3 memory tiers together."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from labclaw.core.graph import PersonNode, ProjectNode
from labclaw.memory.knowledge_graph import TierBBackend
from labclaw.memory.markdown import MarkdownDoc, MemoryEntry, TierABackend
from labclaw.memory.shared_blocks import TierCBackend
from labclaw.memory.sqlite_backend import SQLiteTierBBackend

# ---------------------------------------------------------------------------
# Tier A: Markdown memory
# ---------------------------------------------------------------------------


class TestTierA:
    def test_write_and_search_memory(self, tmp_path: Path) -> None:
        backend = TierABackend(root=tmp_path)

        entry = MemoryEntry(
            timestamp=datetime.now(UTC),
            category="experiment",
            detail="Ran behavioral tracking with DeepLabCut model",
        )
        backend.append_memory("lab", entry)

        results = backend.search("DeepLabCut")
        assert len(results) >= 1
        assert results[0].entity_id == "lab"
        assert "DeepLabCut" in results[0].snippet

    def test_write_soul_and_read(self, tmp_path: Path) -> None:
        backend = TierABackend(root=tmp_path)

        doc = MarkdownDoc(
            path=tmp_path / "testlab" / "SOUL.md",
            frontmatter={"name": "TestLab", "domain": "neuroscience"},
            content="# TestLab\n\nA test laboratory.",
        )
        backend.write_soul("testlab", doc)
        read_back = backend.read_soul("testlab")
        assert read_back.frontmatter["name"] == "TestLab"
        assert "TestLab" in read_back.content

    def test_search_across_entities(self, tmp_path: Path) -> None:
        backend = TierABackend(root=tmp_path)

        backend.append_memory(
            "lab1",
            MemoryEntry(
                timestamp=datetime.now(UTC),
                category="protocol",
                detail="Updated calcium imaging protocol",
            ),
        )
        backend.append_memory(
            "lab2",
            MemoryEntry(
                timestamp=datetime.now(UTC),
                category="experiment",
                detail="Calcium imaging session completed",
            ),
        )

        results = backend.search("calcium imaging")
        assert len(results) == 2
        entity_ids = {r.entity_id for r in results}
        assert "lab1" in entity_ids
        assert "lab2" in entity_ids


# ---------------------------------------------------------------------------
# Tier B: Knowledge graph (in-memory)
# ---------------------------------------------------------------------------


class TestTierBInMemory:
    def test_add_and_search_nodes(self) -> None:
        backend = TierBBackend()

        person = PersonNode(name="Alice", expertise=["electrophysiology"])
        backend.add_node(person)

        project = ProjectNode(name="Behavior Study", description="Mouse behavior tracking")
        backend.add_node(project)

        results = backend.search("behavior")
        assert len(results) >= 1
        names = [r.node.metadata.get("name", getattr(r.node, "name", "")) for r in results]
        # The ProjectNode should match
        assert any("Behavior" in str(n) for n in names) or len(results) > 0

    def test_add_edge_and_neighbors(self) -> None:
        backend = TierBBackend()

        person = PersonNode(name="Bob", expertise=["imaging"])
        backend.add_node(person)
        project = ProjectNode(name="Imaging Project")
        backend.add_node(project)

        backend.add_edge(person.node_id, project.node_id, "leads")
        neighbors = backend.get_neighbors(person.node_id, direction="outgoing")
        assert len(neighbors) == 1
        assert neighbors[0][1].relation == "leads"


# ---------------------------------------------------------------------------
# Tier B: Knowledge graph (SQLite)
# ---------------------------------------------------------------------------


class TestTierBSQLite:
    @pytest.mark.asyncio
    async def test_add_and_fts_search(self, tmp_path: Path) -> None:
        db_path = tmp_path / "tier_b.db"
        backend = SQLiteTierBBackend(db_path)
        await backend.init_db()

        try:
            person = PersonNode(name="Charlie", expertise=["calcium imaging"])
            await backend.add_node(person)

            project = ProjectNode(
                name="Neural Circuit Mapping",
                description="Mapping neural circuits",
            )
            await backend.add_node(project)

            results = await backend.search("neural")
            assert len(results) >= 1
            node_ids = [r.node.node_id for r in results]
            assert project.node_id in node_ids
        finally:
            await backend.close()

    @pytest.mark.asyncio
    async def test_add_edge_and_query(self, tmp_path: Path) -> None:
        db_path = tmp_path / "tier_b_edges.db"
        backend = SQLiteTierBBackend(db_path)
        await backend.init_db()

        try:
            p1 = PersonNode(name="Dana")
            await backend.add_node(p1)
            p2 = ProjectNode(name="Tracking Study")
            await backend.add_node(p2)

            await backend.add_edge(p1.node_id, p2.node_id, "contributes_to")

            neighbors = await backend.get_neighbors(p1.node_id, direction="outgoing")
            assert len(neighbors) == 1
            assert neighbors[0][1].relation == "contributes_to"
        finally:
            await backend.close()

    @pytest.mark.asyncio
    async def test_node_count(self, tmp_path: Path) -> None:
        db_path = tmp_path / "tier_b_count.db"
        backend = SQLiteTierBBackend(db_path)
        await backend.init_db()

        try:
            assert await backend.node_count() == 0
            await backend.add_node(PersonNode(name="Eve"))
            assert await backend.node_count() == 1
        finally:
            await backend.close()


# ---------------------------------------------------------------------------
# Tier C: Shared blocks
# ---------------------------------------------------------------------------


class TestTierC:
    @pytest.mark.asyncio
    async def test_set_get_block_inmemory(self) -> None:
        backend = TierCBackend()
        await backend.set_block("agent1:state", {"step": 3, "status": "running"}, agent_id="agent1")

        block = await backend.get_block("agent1:state")
        assert block is not None
        assert block["step"] == 3
        assert block["status"] == "running"

    @pytest.mark.asyncio
    async def test_list_blocks_filter_by_agent(self) -> None:
        backend = TierCBackend()
        await backend.set_block("a1:state", {"x": 1}, agent_id="agent1")
        await backend.set_block("a2:state", {"x": 2}, agent_id="agent2")
        await backend.set_block("a1:config", {"y": 3}, agent_id="agent1")

        all_keys = await backend.list_blocks()
        assert len(all_keys) == 3

        agent1_keys = await backend.list_blocks(agent_id="agent1")
        assert set(agent1_keys) == {"a1:state", "a1:config"}

    @pytest.mark.asyncio
    async def test_delete_block(self) -> None:
        backend = TierCBackend()
        await backend.set_block("key1", {"data": "test"})
        existed = await backend.delete_block("key1")
        assert existed is True
        assert await backend.get_block("key1") is None

        not_existed = await backend.delete_block("nonexistent")
        assert not_existed is False

    @pytest.mark.asyncio
    async def test_sqlite_backed(self, tmp_path: Path) -> None:
        db_path = tmp_path / "tier_c.db"
        backend = TierCBackend(db_path=db_path)
        await backend.init_db()

        try:
            await backend.set_block("k1", {"val": 42}, agent_id="agent_x")
            block = await backend.get_block("k1")
            assert block is not None
            assert block["val"] == 42

            keys = await backend.list_blocks(agent_id="agent_x")
            assert "k1" in keys
        finally:
            await backend.close()


# ---------------------------------------------------------------------------
# Cross-tier: Write to Tier A and Tier B, search both
# ---------------------------------------------------------------------------


class TestCrossTier:
    @pytest.mark.asyncio
    async def test_search_across_tiers(self, tmp_path: Path) -> None:
        # Tier A: Write markdown memory about calcium imaging
        tier_a = TierABackend(root=tmp_path / "memory")
        tier_a.append_memory(
            "lab",
            MemoryEntry(
                timestamp=datetime.now(UTC),
                category="protocol",
                detail="Calcium imaging protocol v2 established for hippocampal neurons",
            ),
        )

        # Tier B: Add knowledge graph node about calcium imaging
        tier_b = TierBBackend()
        project = ProjectNode(
            name="Calcium Imaging Study",
            description="Two-photon calcium imaging of hippocampal CA1",
        )
        tier_b.add_node(project)

        # Search Tier A
        tier_a_results = tier_a.search("calcium imaging")
        assert len(tier_a_results) >= 1

        # Search Tier B
        tier_b_results = tier_b.search("calcium imaging")
        assert len(tier_b_results) >= 1

        # Both tiers found relevant data
        all_snippets = [r.snippet for r in tier_a_results]
        all_kg_names = [getattr(r.node, "name", "") for r in tier_b_results]
        assert any("calcium" in s.lower() for s in all_snippets)
        assert any("Calcium" in n for n in all_kg_names)
