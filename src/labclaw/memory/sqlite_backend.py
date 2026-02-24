"""SQLite-backed Tier B knowledge graph.

Drop-in replacement for the in-memory TierBBackend.
Uses aiosqlite for async SQLite access.
"""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiosqlite

from labclaw.core.events import event_registry
from labclaw.core.graph import NODE_TYPES, GraphNode
from labclaw.memory.knowledge_graph import KGEdge, KGQueryFilter, KGSearchResult

logger = logging.getLogger(__name__)


class SQLiteTierBBackend:
    """SQLite-backed temporal knowledge graph.

    Same API as TierBBackend but with persistent storage.
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def init_db(self) -> None:
        """Initialize database and create tables."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(str(self._db_path))
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS nodes (
                node_id TEXT PRIMARY KEY,
                node_type TEXT NOT NULL,
                data_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(node_type);
            CREATE INDEX IF NOT EXISTS idx_nodes_created ON nodes(created_at);

            CREATE TABLE IF NOT EXISTS edges (
                edge_id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                relation TEXT NOT NULL,
                properties_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY (source_id) REFERENCES nodes(node_id),
                FOREIGN KEY (target_id) REFERENCES nodes(node_id)
            );
            CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
            CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id);
            CREATE INDEX IF NOT EXISTS idx_edges_relation ON edges(relation);

            -- FTS5 for text search; node_id is UNINDEXED for equality lookup
            CREATE VIRTUAL TABLE IF NOT EXISTS nodes_fts USING fts5(
                node_id UNINDEXED,
                content,
                tokenize='porter'
            );
        """)
        await self._db.commit()

    async def close(self) -> None:
        """Close the database connection."""
        if self._db:
            await self._db.close()
            self._db = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _db_or_raise(self) -> aiosqlite.Connection:
        if self._db is None:
            raise RuntimeError("SQLiteTierBBackend not initialized — call init_db() first")
        return self._db

    def _node_to_fts_content(self, node: GraphNode) -> str:
        """Flatten all node fields to a space-joined string for FTS indexing."""
        data = node.model_dump(mode="json")
        parts: list[str] = []
        for v in data.values():
            if isinstance(v, str) and v:
                parts.append(v)
            elif isinstance(v, list):
                parts.extend(str(item) for item in v if item)
            elif isinstance(v, dict):
                parts.extend(str(val) for val in v.values() if val)
        return " ".join(parts)

    def _row_to_node(self, row: aiosqlite.Row) -> GraphNode:
        node_type: str = row["node_type"]
        node_class = NODE_TYPES.get(node_type, GraphNode)
        return node_class.model_validate_json(row["data_json"])

    def _row_to_edge(self, row: aiosqlite.Row) -> KGEdge:
        return KGEdge(
            edge_id=row["edge_id"],
            source_id=row["source_id"],
            target_id=row["target_id"],
            relation=row["relation"],
            properties=json.loads(row["properties_json"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    async def _fts_rowid(self, node_id: str) -> int | None:
        """Return the FTS5 rowid for the given node_id, or None."""
        db = self._db_or_raise()
        async with db.execute("SELECT rowid FROM nodes_fts WHERE node_id = ?", (node_id,)) as cur:
            row = await cur.fetchone()
        return row[0] if row else None

    async def _fts_upsert(self, node: GraphNode) -> None:
        """Insert or replace the FTS entry for a node."""
        db = self._db_or_raise()
        fts_rowid = await self._fts_rowid(node.node_id)
        if fts_rowid is not None:
            await db.execute("DELETE FROM nodes_fts WHERE rowid = ?", (fts_rowid,))
        content = self._node_to_fts_content(node)
        await db.execute(
            "INSERT INTO nodes_fts(node_id, content) VALUES (?, ?)", (node.node_id, content)
        )

    async def _fts_delete(self, node_id: str) -> None:
        """Remove the FTS entry for a node."""
        db = self._db_or_raise()
        fts_rowid = await self._fts_rowid(node_id)
        if fts_rowid is not None:
            await db.execute("DELETE FROM nodes_fts WHERE rowid = ?", (fts_rowid,))

    # ------------------------------------------------------------------
    # Node CRUD
    # ------------------------------------------------------------------

    async def add_node(self, node: GraphNode) -> GraphNode:
        """Add a node. Raises ValueError if node_id already exists."""
        db = self._db_or_raise()
        async with db.execute("SELECT 1 FROM nodes WHERE node_id = ?", (node.node_id,)) as cur:
            if await cur.fetchone():
                raise ValueError(f"Node {node.node_id!r} already exists")

        await db.execute(
            "INSERT INTO nodes "
            "(node_id, node_type, data_json, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                node.node_id,
                node.node_type,
                node.model_dump_json(),
                node.created_at.isoformat(),
                node.updated_at.isoformat(),
            ),
        )
        await self._fts_upsert(node)
        await db.commit()

        event_registry.emit(
            "memory.tier_b.node_added",
            payload={"node_id": node.node_id, "node_type": node.node_type},
        )
        return node

    async def get_node(self, node_id: str) -> GraphNode:
        """Get node by ID. Raises KeyError if not found."""
        db = self._db_or_raise()
        async with db.execute("SELECT * FROM nodes WHERE node_id = ?", (node_id,)) as cur:
            row = await cur.fetchone()
        if row is None:
            raise KeyError(f"Node {node_id!r} not found in knowledge graph")
        return self._row_to_node(row)

    async def update_node(self, node_id: str, **fields: Any) -> GraphNode:
        """Update fields on an existing node. Raises KeyError if not found."""
        db = self._db_or_raise()
        existing = await self.get_node(node_id)
        update_data = existing.model_dump()
        update_data.update(fields)
        update_data["updated_at"] = datetime.now(UTC)
        updated = type(existing).model_validate(update_data)

        await db.execute(
            "UPDATE nodes SET node_type = ?, data_json = ?, updated_at = ? WHERE node_id = ?",
            (updated.node_type, updated.model_dump_json(), updated.updated_at.isoformat(), node_id),
        )
        await self._fts_upsert(updated)
        await db.commit()

        event_registry.emit(
            "memory.tier_b.node_updated",
            payload={
                "node_id": node_id,
                "node_type": updated.node_type,
                "updated_fields": list(fields.keys()),
            },
        )
        return updated

    async def remove_node(self, node_id: str) -> None:
        """Remove a node and all connected edges. Raises KeyError if not found."""
        db = self._db_or_raise()
        node = await self.get_node(node_id)

        await db.execute(
            "DELETE FROM edges WHERE source_id = ? OR target_id = ?",
            (node_id, node_id),
        )
        await self._fts_delete(node_id)
        await db.execute("DELETE FROM nodes WHERE node_id = ?", (node_id,))
        await db.commit()

        event_registry.emit(
            "memory.tier_b.node_removed",
            payload={"node_id": node_id, "node_type": node.node_type},
        )

    # ------------------------------------------------------------------
    # Edge CRUD
    # ------------------------------------------------------------------

    async def add_edge(
        self,
        source_id: str,
        target_id: str,
        relation: str,
        properties: dict[str, Any] | None = None,
    ) -> KGEdge:
        """Add a directed edge between two nodes. Raises KeyError if either node missing."""
        db = self._db_or_raise()
        await self.get_node(source_id)
        await self.get_node(target_id)

        edge = KGEdge(
            source_id=source_id,
            target_id=target_id,
            relation=relation,
            properties=properties or {},
        )
        await db.execute(
            "INSERT INTO edges "
            "(edge_id, source_id, target_id, relation, "
            "properties_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                edge.edge_id,
                edge.source_id,
                edge.target_id,
                edge.relation,
                json.dumps(edge.properties),
                edge.created_at.isoformat(),
            ),
        )
        await db.commit()

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

    async def get_edge(self, edge_id: str) -> KGEdge:
        """Retrieve an edge by ID. Raises KeyError if not found."""
        db = self._db_or_raise()
        async with db.execute("SELECT * FROM edges WHERE edge_id = ?", (edge_id,)) as cur:
            row = await cur.fetchone()
        if row is None:
            raise KeyError(f"Edge {edge_id!r} not found")
        return self._row_to_edge(row)

    async def remove_edge(self, edge_id: str) -> None:
        """Remove an edge by ID. Raises KeyError if not found."""
        db = self._db_or_raise()
        edge = await self.get_edge(edge_id)
        await db.execute("DELETE FROM edges WHERE edge_id = ?", (edge_id,))
        await db.commit()

        event_registry.emit(
            "memory.tier_b.edge_removed",
            payload={
                "edge_id": edge_id,
                "source_id": edge.source_id,
                "target_id": edge.target_id,
                "relation": edge.relation,
            },
        )

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    async def query_nodes(self, filter: KGQueryFilter) -> list[GraphNode]:
        """Query nodes by type, time range, tags, and metadata."""
        db = self._db_or_raise()
        sql = "SELECT * FROM nodes WHERE 1=1"
        params: list[Any] = []

        if filter.node_type is not None:
            sql += " AND node_type = ?"
            params.append(filter.node_type)
        if filter.created_after is not None:
            sql += " AND created_at > ?"
            params.append(filter.created_after.isoformat())
        if filter.created_before is not None:
            sql += " AND created_at < ?"
            params.append(filter.created_before.isoformat())

        async with db.execute(sql, params) as cur:
            rows = await cur.fetchall()

        results: list[GraphNode] = []
        for row in rows:
            node = self._row_to_node(row)
            if filter.tags and not all(t in node.tags for t in filter.tags):
                continue
            if filter.metadata_filter and not all(
                node.metadata.get(k) == v for k, v in filter.metadata_filter.items()
            ):
                continue
            results.append(node)

        return results

    async def get_neighbors(
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
        """
        db = self._db_or_raise()
        await self.get_node(node_id)
        results: list[tuple[GraphNode, KGEdge]] = []

        if direction in ("outgoing", "both"):
            sql = "SELECT * FROM edges WHERE source_id = ?"
            params: list[Any] = [node_id]
            if relation:
                sql += " AND relation = ?"
                params.append(relation)
            async with db.execute(sql, params) as cur:
                rows = await cur.fetchall()
            for row in rows:
                edge = self._row_to_edge(row)
                try:
                    neighbor = await self.get_node(edge.target_id)
                    results.append((neighbor, edge))
                except KeyError:
                    pass

        if direction in ("incoming", "both"):
            sql = "SELECT * FROM edges WHERE target_id = ?"
            params = [node_id]
            if relation:
                sql += " AND relation = ?"
                params.append(relation)
            async with db.execute(sql, params) as cur:
                rows = await cur.fetchall()
            for row in rows:
                edge = self._row_to_edge(row)
                try:
                    neighbor = await self.get_node(edge.source_id)
                    results.append((neighbor, edge))
                except KeyError:
                    pass

        return results

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    async def search(self, query: str, limit: int = 10) -> list[KGSearchResult]:
        """Full-text search across all nodes using FTS5."""
        db = self._db_or_raise()
        query = query.strip()
        if not query:
            return []

        sql = (
            "SELECT node_id, (-bm25(nodes_fts)) AS score "
            "FROM nodes_fts WHERE nodes_fts MATCH ? "
            "ORDER BY score DESC LIMIT ?"
        )
        try:
            async with db.execute(sql, (query, limit)) as cur:
                fts_rows = await cur.fetchall()
        except Exception:
            logger.warning("FTS5 search failed for query %r", query, exc_info=True)
            fts_rows = []

        results: list[KGSearchResult] = []
        for fts_row in fts_rows:
            try:
                node = await self.get_node(fts_row["node_id"])
            except KeyError:
                continue
            results.append(KGSearchResult(
                node=node,
                score=max(0.0, float(fts_row["score"])),
                matched_field="content",
            ))

        event_registry.emit(
            "memory.tier_b.search_executed",
            payload={"query": query, "result_count": len(results)},
        )
        return results

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    async def node_count(self) -> int:
        """Return total number of nodes."""
        db = self._db_or_raise()
        async with db.execute("SELECT COUNT(*) FROM nodes") as cur:
            row = await cur.fetchone()
        return int(row[0]) if row else 0

    async def edge_count(self) -> int:
        """Return total number of edges."""
        db = self._db_or_raise()
        async with db.execute("SELECT COUNT(*) FROM edges") as cur:
            row = await cur.fetchone()
        return int(row[0]) if row else 0
