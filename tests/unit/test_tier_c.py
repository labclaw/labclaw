"""Tests for Tier C: Agent shared blocks (key-value working memory)."""

from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio

from labclaw.core.events import event_registry
from labclaw.memory.shared_blocks import TierCBackend

# ---------------------------------------------------------------------------
# In-memory mode fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def mem_backend():
    b = TierCBackend(db_path=None)
    await b.init_db()
    yield b


@pytest_asyncio.fixture
async def sqlite_backend(tmp_path: Path):
    db_path = tmp_path / "tier_c.db"
    b = TierCBackend(db_path=db_path)
    await b.init_db()
    yield b
    await b.close()


# ---------------------------------------------------------------------------
# In-memory mode
# ---------------------------------------------------------------------------


class TestInMemoryMode:
    @pytest.mark.asyncio
    async def test_set_and_get(self, mem_backend: TierCBackend) -> None:
        await mem_backend.set_block("key1", {"data": "hello"})
        result = await mem_backend.get_block("key1")
        assert result is not None
        assert result["data"] == "hello"

    @pytest.mark.asyncio
    async def test_get_missing(self, mem_backend: TierCBackend) -> None:
        result = await mem_backend.get_block("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_overwrite(self, mem_backend: TierCBackend) -> None:
        await mem_backend.set_block("key1", {"v": 1})
        await mem_backend.set_block("key1", {"v": 2})
        result = await mem_backend.get_block("key1")
        assert result is not None
        assert result["v"] == 2

    @pytest.mark.asyncio
    async def test_delete(self, mem_backend: TierCBackend) -> None:
        await mem_backend.set_block("key1", {"v": 1})
        assert await mem_backend.delete_block("key1") is True
        assert await mem_backend.get_block("key1") is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, mem_backend: TierCBackend) -> None:
        assert await mem_backend.delete_block("nope") is False

    @pytest.mark.asyncio
    async def test_list_blocks(self, mem_backend: TierCBackend) -> None:
        await mem_backend.set_block("a", {"v": 1})
        await mem_backend.set_block("b", {"v": 2})
        keys = await mem_backend.list_blocks()
        assert set(keys) == {"a", "b"}

    @pytest.mark.asyncio
    async def test_list_blocks_by_agent(self, mem_backend: TierCBackend) -> None:
        await mem_backend.set_block("a", {"v": 1}, agent_id="agent-1")
        await mem_backend.set_block("b", {"v": 2}, agent_id="agent-2")
        await mem_backend.set_block("c", {"v": 3}, agent_id="agent-1")

        keys = await mem_backend.list_blocks(agent_id="agent-1")
        assert set(keys) == {"a", "c"}

    @pytest.mark.asyncio
    async def test_get_all_blocks(self, mem_backend: TierCBackend) -> None:
        await mem_backend.set_block("a", {"v": 1})
        await mem_backend.set_block("b", {"v": 2})
        all_blocks = await mem_backend.get_all_blocks()
        assert set(all_blocks.keys()) == {"a", "b"}

    @pytest.mark.asyncio
    async def test_get_all_blocks_by_agent(self, mem_backend: TierCBackend) -> None:
        await mem_backend.set_block("a", {"v": 1}, agent_id="agent-1")
        await mem_backend.set_block("b", {"v": 2}, agent_id="agent-2")
        result = await mem_backend.get_all_blocks(agent_id="agent-1")
        assert set(result.keys()) == {"a"}


# ---------------------------------------------------------------------------
# SQLite mode
# ---------------------------------------------------------------------------


class TestSQLiteMode:
    @pytest.mark.asyncio
    async def test_set_and_get(self, sqlite_backend: TierCBackend) -> None:
        await sqlite_backend.set_block("key1", {"data": "hello"}, agent_id="a1")
        result = await sqlite_backend.get_block("key1")
        assert result is not None
        assert result["data"] == "hello"
        assert result["_meta"]["agent_id"] == "a1"

    @pytest.mark.asyncio
    async def test_get_missing(self, sqlite_backend: TierCBackend) -> None:
        result = await sqlite_backend.get_block("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_overwrite(self, sqlite_backend: TierCBackend) -> None:
        await sqlite_backend.set_block("key1", {"v": 1})
        await sqlite_backend.set_block("key1", {"v": 2})
        result = await sqlite_backend.get_block("key1")
        assert result is not None
        assert result["v"] == 2

    @pytest.mark.asyncio
    async def test_delete(self, sqlite_backend: TierCBackend) -> None:
        await sqlite_backend.set_block("key1", {"v": 1})
        assert await sqlite_backend.delete_block("key1") is True
        assert await sqlite_backend.get_block("key1") is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, sqlite_backend: TierCBackend) -> None:
        assert await sqlite_backend.delete_block("nope") is False

    @pytest.mark.asyncio
    async def test_list_blocks(self, sqlite_backend: TierCBackend) -> None:
        await sqlite_backend.set_block("a", {"v": 1})
        await sqlite_backend.set_block("b", {"v": 2})
        keys = await sqlite_backend.list_blocks()
        assert set(keys) == {"a", "b"}

    @pytest.mark.asyncio
    async def test_list_blocks_by_agent(self, sqlite_backend: TierCBackend) -> None:
        await sqlite_backend.set_block("a", {"v": 1}, agent_id="agent-1")
        await sqlite_backend.set_block("b", {"v": 2}, agent_id="agent-2")
        await sqlite_backend.set_block("c", {"v": 3}, agent_id="agent-1")

        keys = await sqlite_backend.list_blocks(agent_id="agent-1")
        assert set(keys) == {"a", "c"}

    @pytest.mark.asyncio
    async def test_get_all_blocks(self, sqlite_backend: TierCBackend) -> None:
        await sqlite_backend.set_block("a", {"v": 1})
        await sqlite_backend.set_block("b", {"v": 2})
        all_blocks = await sqlite_backend.get_all_blocks()
        assert set(all_blocks.keys()) == {"a", "b"}

    @pytest.mark.asyncio
    async def test_get_all_blocks_by_agent(self, sqlite_backend: TierCBackend) -> None:
        await sqlite_backend.set_block("a", {"v": 1}, agent_id="agent-1")
        await sqlite_backend.set_block("b", {"v": 2}, agent_id="agent-2")
        result = await sqlite_backend.get_all_blocks(agent_id="agent-1")
        assert set(result.keys()) == {"a"}

    @pytest.mark.asyncio
    async def test_close(self, tmp_path: Path) -> None:
        db_path = tmp_path / "close_test.db"
        b = TierCBackend(db_path=db_path)
        await b.init_db()
        await b.close()
        assert b._db is None


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


class TestTierCEvents:
    @pytest.mark.asyncio
    async def test_block_set_event(self, mem_backend: TierCBackend) -> None:
        events: list = []
        event_registry.subscribe("memory.tier_c.block_set", events.append)
        await mem_backend.set_block("k", {"v": 1}, agent_id="a1")
        assert any(
            e.payload["key"] == "k" and e.payload["agent_id"] == "a1"
            for e in events
        )

    @pytest.mark.asyncio
    async def test_block_deleted_event(self, mem_backend: TierCBackend) -> None:
        events: list = []
        event_registry.subscribe("memory.tier_c.block_deleted", events.append)
        await mem_backend.set_block("k", {"v": 1})
        await mem_backend.delete_block("k")
        assert any(e.payload["key"] == "k" for e in events)

    @pytest.mark.asyncio
    async def test_no_event_on_delete_nonexistent(self, mem_backend: TierCBackend) -> None:
        events: list = []
        event_registry.subscribe("memory.tier_c.block_deleted", events.append)
        initial_count = len(events)
        await mem_backend.delete_block("nope")
        # No new event should have been emitted for a nonexistent key
        assert len(events) == initial_count

    @pytest.mark.asyncio
    async def test_sqlite_block_set_event(self, sqlite_backend: TierCBackend) -> None:
        events: list = []
        event_registry.subscribe("memory.tier_c.block_set", events.append)
        await sqlite_backend.set_block("k", {"v": 1}, agent_id="a1")
        assert any(
            e.payload["key"] == "k" and e.payload["agent_id"] == "a1"
            for e in events
        )

    @pytest.mark.asyncio
    async def test_sqlite_block_deleted_event(self, sqlite_backend: TierCBackend) -> None:
        events: list = []
        event_registry.subscribe("memory.tier_c.block_deleted", events.append)
        await sqlite_backend.set_block("k", {"v": 1})
        await sqlite_backend.delete_block("k")
        assert any(e.payload["key"] == "k" for e in events)
