"""Tier C: Agent shared blocks — key-value working memory.

SQLite-backed persistent key-value store for agent working memory.
Interface designed for future Letta swap-in.
"""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiosqlite

from labclaw.core.events import event_registry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Register events
# ---------------------------------------------------------------------------

_TIER_C_EVENTS = [
    "memory.tier_c.block_set",
    "memory.tier_c.block_deleted",
]
for _evt in _TIER_C_EVENTS:
    if not event_registry.is_registered(_evt):
        event_registry.register(_evt)


# ---------------------------------------------------------------------------
# TierCBackend
# ---------------------------------------------------------------------------


class TierCBackend:
    """Key-value store for agent working memory.

    Each block is a JSON-serializable dict with metadata.
    Backed by SQLite when a db_path is provided; otherwise falls back to
    an in-memory dict.
    """

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None
        self._memory: dict[str, dict[str, Any]] = {}

    async def init_db(self) -> None:
        """Initialize SQLite storage. No-op in in-memory mode."""
        if self._db_path is None:
            return
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(str(self._db_path))
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS shared_blocks (
                key TEXT PRIMARY KEY,
                value_json TEXT NOT NULL,
                agent_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)
        await self._db.commit()

    async def close(self) -> None:
        """Close the database connection."""
        if self._db:
            await self._db.close()
            self._db = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_block(self, key: str) -> dict[str, Any] | None:
        """Return the block for the given key, or None if not found."""
        if self._db is None:
            entry = self._memory.get(key)
            if entry is None:
                return None
            import copy
            return copy.deepcopy(dict(entry))

        async with self._db.execute(
            "SELECT value_json, agent_id, created_at, updated_at FROM shared_blocks WHERE key = ?",
            (key,),
        ) as cur:
            row = await cur.fetchone()

        if row is None:
            return None
        value: dict[str, Any] = json.loads(row["value_json"])
        value.setdefault("_meta", {}).update({
            "agent_id": row["agent_id"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        })
        return value

    async def set_block(self, key: str, value: dict[str, Any], agent_id: str | None = None) -> None:
        """Create or update a block."""
        now = datetime.now(UTC).isoformat()

        if self._db is None:
            entry = dict(value)
            entry.setdefault("_meta", {}).update({"agent_id": agent_id, "updated_at": now})
            if key not in self._memory:
                entry["_meta"]["created_at"] = now
            self._memory[key] = entry
        else:
            value_json = json.dumps(value)
            await self._db.execute(
                """
                INSERT INTO shared_blocks (key, value_json, agent_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value_json = excluded.value_json,
                    agent_id   = excluded.agent_id,
                    updated_at = excluded.updated_at
                """,
                (key, value_json, agent_id, now, now),
            )
            await self._db.commit()

        event_registry.emit(
            "memory.tier_c.block_set",
            payload={"key": key, "agent_id": agent_id},
        )

    async def delete_block(self, key: str) -> bool:
        """Delete a block. Returns True if it existed, False otherwise."""
        if self._db is None:
            existed = key in self._memory
            self._memory.pop(key, None)
        else:
            async with self._db.execute("SELECT 1 FROM shared_blocks WHERE key = ?", (key,)) as cur:
                existed = (await cur.fetchone()) is not None
            if existed:
                await self._db.execute("DELETE FROM shared_blocks WHERE key = ?", (key,))
                await self._db.commit()

        if existed:
            event_registry.emit(
                "memory.tier_c.block_deleted",
                payload={"key": key},
            )
        return existed

    async def list_blocks(self, agent_id: str | None = None) -> list[str]:
        """List all block keys, optionally filtered by agent_id."""
        if self._db is None:
            if agent_id is None:
                return list(self._memory.keys())
            return [
                k for k, v in self._memory.items()
                if v.get("_meta", {}).get("agent_id") == agent_id
            ]

        if agent_id is None:
            async with self._db.execute("SELECT key FROM shared_blocks ORDER BY key") as cur:
                rows = await cur.fetchall()
        else:
            async with self._db.execute(
                "SELECT key FROM shared_blocks WHERE agent_id = ? ORDER BY key",
                (agent_id,),
            ) as cur:
                rows = await cur.fetchall()

        return [row["key"] for row in rows]

    async def get_all_blocks(self, agent_id: str | None = None) -> dict[str, dict[str, Any]]:
        """Return all blocks as {key: value}, optionally filtered by agent_id."""
        keys = await self.list_blocks(agent_id=agent_id)
        result: dict[str, dict[str, Any]] = {}
        for key in keys:
            block = await self.get_block(key)
            if block is not None:
                result[key] = block
        return result
