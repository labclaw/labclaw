"""Unit tests for SessionMemoryManager (C3: REMEMBER)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from labclaw.memory.session_memory import SessionMemoryManager, _SQLiteFindingsStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _finding(n: int) -> dict[str, Any]:
    return {
        "finding_id": f"f-{n}",
        "description": f"finding {n}",
        "column_a": f"a{n}",
        "column_b": f"b{n}",
        "pattern_type": "correlation",
    }


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------


class TestSessionMemoryManagerInit:
    @pytest.mark.asyncio
    async def test_init_no_tier_b(self, tmp_path: Path) -> None:
        """init() without db_path leaves _tier_b as None."""
        mgr = SessionMemoryManager(tmp_path / "mem")
        await mgr.init()
        assert mgr._tier_b is None
        assert mgr._findings == []

    @pytest.mark.asyncio
    async def test_init_with_tier_b(self, tmp_path: Path) -> None:
        """init() with db_path creates and initializes _tier_b."""
        db = tmp_path / "kg.db"
        mgr = SessionMemoryManager(tmp_path / "mem", db)
        await mgr.init()
        assert mgr._tier_b is not None
        await mgr._tier_b.close()

    @pytest.mark.asyncio
    async def test_init_loads_existing_findings(self, tmp_path: Path) -> None:
        """init() loads findings that were stored in a previous session."""
        memory_root = tmp_path / "mem"
        db = tmp_path / "kg.db"

        mgr1 = SessionMemoryManager(memory_root, db)
        await mgr1.init()
        await mgr1.store_finding(_finding(1))
        await mgr1.store_finding(_finding(2))
        await mgr1._tier_b.close()

        # New manager — should reload from disk
        mgr2 = SessionMemoryManager(memory_root, db)
        await mgr2.init()
        assert len(mgr2._findings) == 2
        await mgr2._tier_b.close()

    @pytest.mark.asyncio
    async def test_init_empty_memory_root(self, tmp_path: Path) -> None:
        """init() on an empty memory root returns zero findings."""
        mgr = SessionMemoryManager(tmp_path / "nonexistent_mem")
        await mgr.init()
        assert mgr._findings == []


# ---------------------------------------------------------------------------
# store_finding
# ---------------------------------------------------------------------------


class TestStoreFinding:
    @pytest.mark.asyncio
    async def test_store_appends_to_findings(self, tmp_path: Path) -> None:
        mgr = SessionMemoryManager(tmp_path / "mem")
        await mgr.init()
        fid = await mgr.store_finding(_finding(1))
        assert fid == "f-1"
        assert len(mgr._findings) == 1

    @pytest.mark.asyncio
    async def test_store_generates_finding_id_if_absent(self, tmp_path: Path) -> None:
        mgr = SessionMemoryManager(tmp_path / "mem")
        await mgr.init()
        fid = await mgr.store_finding({"description": "no id"})
        assert isinstance(fid, str) and len(fid) > 0

    @pytest.mark.asyncio
    async def test_store_writes_tier_a_file(self, tmp_path: Path) -> None:
        memory_root = tmp_path / "mem"
        mgr = SessionMemoryManager(memory_root)
        await mgr.init()
        await mgr.store_finding(_finding(5))
        mem_path = memory_root / "findings" / "MEMORY.md"
        assert mem_path.exists()
        assert "finding 5" in mem_path.read_text()

    @pytest.mark.asyncio
    async def test_store_writes_tier_b(self, tmp_path: Path) -> None:
        db = tmp_path / "kg.db"
        mgr = SessionMemoryManager(tmp_path / "mem", db)
        await mgr.init()
        await mgr.store_finding(_finding(3))
        findings = await mgr._tier_b.list_findings()
        assert len(findings) == 1
        await mgr._tier_b.close()

    @pytest.mark.asyncio
    async def test_store_sets_stored_at(self, tmp_path: Path) -> None:
        mgr = SessionMemoryManager(tmp_path / "mem")
        await mgr.init()
        await mgr.store_finding({"description": "test"})
        assert mgr._findings[0].get("stored_at") is not None

    @pytest.mark.asyncio
    async def test_store_uses_provided_finding_id(self, tmp_path: Path) -> None:
        mgr = SessionMemoryManager(tmp_path / "mem")
        await mgr.init()
        fid = await mgr.store_finding({"finding_id": "custom-id", "description": "x"})
        assert fid == "custom-id"
        assert mgr._findings[0]["finding_id"] == "custom-id"


# ---------------------------------------------------------------------------
# retrieve_findings
# ---------------------------------------------------------------------------


class TestRetrieveFindings:
    @pytest.mark.asyncio
    async def test_retrieve_all(self, tmp_path: Path) -> None:
        mgr = SessionMemoryManager(tmp_path / "mem")
        await mgr.init()
        for i in range(3):
            await mgr.store_finding(_finding(i))
        results = await mgr.retrieve_findings()
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_retrieve_with_query(self, tmp_path: Path) -> None:
        mgr = SessionMemoryManager(tmp_path / "mem")
        await mgr.init()
        await mgr.store_finding({"description": "speed matters"})
        await mgr.store_finding({"description": "mass measurement"})
        results = await mgr.retrieve_findings(query="speed")
        assert len(results) == 1
        assert "speed" in results[0]["description"]

    @pytest.mark.asyncio
    async def test_retrieve_uses_tier_b_when_available(self, tmp_path: Path) -> None:
        db = tmp_path / "kg.db"
        mgr = SessionMemoryManager(tmp_path / "mem", db)
        await mgr.init()
        await mgr.store_finding(_finding(7))
        results = await mgr.retrieve_findings()
        assert len(results) == 1
        await mgr._tier_b.close()

    @pytest.mark.asyncio
    async def test_retrieve_empty(self, tmp_path: Path) -> None:
        mgr = SessionMemoryManager(tmp_path / "mem")
        await mgr.init()
        results = await mgr.retrieve_findings()
        assert results == []

    @pytest.mark.asyncio
    async def test_retrieve_tier_b_with_query(self, tmp_path: Path) -> None:
        db = tmp_path / "kg.db"
        mgr = SessionMemoryManager(tmp_path / "mem", db)
        await mgr.init()
        await mgr.store_finding({"description": "alpha result", "finding_id": "a1"})
        await mgr.store_finding({"description": "beta result", "finding_id": "b2"})
        results = await mgr.retrieve_findings(query="alpha")
        assert len(results) == 1
        await mgr._tier_b.close()


# ---------------------------------------------------------------------------
# get_retrieval_rate
# ---------------------------------------------------------------------------


class TestGetRetrievalRate:
    @pytest.mark.asyncio
    async def test_rate_is_one_when_empty(self, tmp_path: Path) -> None:
        mgr = SessionMemoryManager(tmp_path / "mem")
        await mgr.init()
        assert mgr.get_retrieval_rate() == 1.0

    @pytest.mark.asyncio
    async def test_rate_is_one_after_storing(self, tmp_path: Path) -> None:
        mgr = SessionMemoryManager(tmp_path / "mem")
        await mgr.init()
        await mgr.store_finding(_finding(1))
        assert mgr.get_retrieval_rate() == 1.0


# ---------------------------------------------------------------------------
# is_known_pattern
# ---------------------------------------------------------------------------


class TestIsKnownPattern:
    @pytest.mark.asyncio
    async def test_not_known_when_empty(self, tmp_path: Path) -> None:
        mgr = SessionMemoryManager(tmp_path / "mem")
        await mgr.init()
        p = {"column_a": "x", "column_b": "y", "pattern_type": "correlation"}
        assert mgr.is_known_pattern(p) is False

    @pytest.mark.asyncio
    async def test_known_after_store(self, tmp_path: Path) -> None:
        mgr = SessionMemoryManager(tmp_path / "mem")
        await mgr.init()
        p = {"column_a": "x", "column_b": "y", "pattern_type": "correlation"}
        await mgr.store_finding(p)
        assert mgr.is_known_pattern(p) is True

    @pytest.mark.asyncio
    async def test_different_pattern_not_known(self, tmp_path: Path) -> None:
        mgr = SessionMemoryManager(tmp_path / "mem")
        await mgr.init()
        await mgr.store_finding(
            {"column_a": "x", "column_b": "y", "pattern_type": "correlation"}
        )
        other = {"column_a": "a", "column_b": "b", "pattern_type": "anomaly"}
        assert mgr.is_known_pattern(other) is False

    @pytest.mark.asyncio
    async def test_known_by_finding_id_fallback(self, tmp_path: Path) -> None:
        """When column fields are absent, match by finding_id."""
        mgr = SessionMemoryManager(tmp_path / "mem")
        await mgr.init()
        await mgr.store_finding({"finding_id": "special-123", "description": "test"})
        assert mgr.is_known_pattern({"finding_id": "special-123"}) is True

    @pytest.mark.asyncio
    async def test_not_known_missing_fields(self, tmp_path: Path) -> None:
        """Pattern without column fields and non-matching id is not known."""
        mgr = SessionMemoryManager(tmp_path / "mem")
        await mgr.init()
        await mgr.store_finding({"finding_id": "abc", "description": "test"})
        # No column fields, different id — should not match
        assert mgr.is_known_pattern({"description": "test"}) is False


# ---------------------------------------------------------------------------
# _load_existing_findings (edge cases)
# ---------------------------------------------------------------------------


class TestLoadExistingFindings:
    def test_malformed_json_skipped(self, tmp_path: Path) -> None:
        """Corrupt JSON blocks are skipped with a warning."""
        memory_root = tmp_path / "mem"
        findings_dir = memory_root / "findings"
        findings_dir.mkdir(parents=True)
        mem_path = findings_dir / "MEMORY.md"
        mem_path.write_text(
            "## entry\n\n```json\n{bad json\n```\n\n"
            "## entry2\n\n```json\n{\"finding_id\": \"ok\"}\n```\n"
        )
        mgr = SessionMemoryManager(memory_root)
        result = mgr._load_existing_findings()
        assert len(result) == 1
        assert result[0]["finding_id"] == "ok"

    def test_non_dict_json_skipped(self, tmp_path: Path) -> None:
        """JSON blocks that are not dicts are skipped."""
        memory_root = tmp_path / "mem"
        findings_dir = memory_root / "findings"
        findings_dir.mkdir(parents=True)
        mem_path = findings_dir / "MEMORY.md"
        mem_path.write_text("```json\n[1, 2, 3]\n```\n")
        mgr = SessionMemoryManager(memory_root)
        result = mgr._load_existing_findings()
        assert result == []


# ---------------------------------------------------------------------------
# _SQLiteFindingsStore
# ---------------------------------------------------------------------------


class TestSQLiteFindingsStore:
    @pytest.mark.asyncio
    async def test_init_creates_db(self, tmp_path: Path) -> None:
        store = _SQLiteFindingsStore(tmp_path / "sub" / "findings.db")
        await store.init_db()
        assert (tmp_path / "sub" / "findings.db").exists()
        await store.close()

    @pytest.mark.asyncio
    async def test_upsert_and_list(self, tmp_path: Path) -> None:
        store = _SQLiteFindingsStore(tmp_path / "f.db")
        await store.init_db()
        await store.upsert_finding({"finding_id": "x1", "description": "test"})
        rows = await store.list_findings()
        assert len(rows) == 1
        assert rows[0]["finding_id"] == "x1"
        await store.close()

    @pytest.mark.asyncio
    async def test_upsert_idempotent(self, tmp_path: Path) -> None:
        store = _SQLiteFindingsStore(tmp_path / "f.db")
        await store.init_db()
        f = {"finding_id": "dup", "v": 1}
        await store.upsert_finding(f)
        f2 = {"finding_id": "dup", "v": 2}
        await store.upsert_finding(f2)
        rows = await store.list_findings()
        assert len(rows) == 1
        assert rows[0]["v"] == 2
        await store.close()

    @pytest.mark.asyncio
    async def test_list_with_query(self, tmp_path: Path) -> None:
        store = _SQLiteFindingsStore(tmp_path / "f.db")
        await store.init_db()
        await store.upsert_finding({"finding_id": "a", "desc": "alpha"})
        await store.upsert_finding({"finding_id": "b", "desc": "beta"})
        rows = await store.list_findings(query="alpha")
        assert len(rows) == 1
        await store.close()

    @pytest.mark.asyncio
    async def test_not_initialized_raises(self, tmp_path: Path) -> None:
        store = _SQLiteFindingsStore(tmp_path / "f.db")
        with pytest.raises(RuntimeError, match="not initialized"):
            store._conn()

    @pytest.mark.asyncio
    async def test_close_idempotent(self, tmp_path: Path) -> None:
        store = _SQLiteFindingsStore(tmp_path / "f.db")
        await store.init_db()
        await store.close()
        await store.close()  # second close is safe
        assert store._db is None
