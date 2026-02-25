"""Integration tests for C3: REMEMBER — cross-session memory persistence.

These tests verify that:
- Findings stored in session 1 are retrievable after a "restart" (new manager).
- Known patterns are correctly flagged as duplicates.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from labclaw.memory.dedup import PatternDeduplicator
from labclaw.memory.session_memory import SessionMemoryManager


def _make_finding(n: int) -> dict[str, Any]:
    return {
        "finding_id": f"finding-{n}",
        "description": f"Test finding number {n}",
        "column_a": f"col_a_{n}",
        "column_b": f"col_b_{n}",
        "pattern_type": "correlation",
        "p_value": 0.01 * n,
    }


# ---------------------------------------------------------------------------
# C3-1: Findings survive manager restart
# ---------------------------------------------------------------------------


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_findings_survive_restart(tmp_path: Path) -> None:
    """C3: Store findings, 'restart' (new manager instance), retrieve ≥90%."""
    db_path = tmp_path / "tier_b.db"
    memory_root = tmp_path / "memory"

    # Session 1 — store 10 findings
    mgr1 = SessionMemoryManager(memory_root, db_path)
    await mgr1.init()

    n_findings = 10
    for i in range(n_findings):
        await mgr1.store_finding(_make_finding(i))

    stored_count = len(mgr1._findings)
    assert stored_count == n_findings

    # "Restart" — new manager instance reading from same paths
    mgr2 = SessionMemoryManager(memory_root, db_path)
    await mgr2.init()
    retrieved = await mgr2.retrieve_findings()

    rate = len(retrieved) / stored_count
    assert rate >= 0.9, f"Expected ≥90% retrieval, got {rate:.1%} ({len(retrieved)}/{stored_count})"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_findings_survive_restart_tier_a_only(tmp_path: Path) -> None:
    """C3: Tier A only (no SQLite) — findings still survive restart."""
    memory_root = tmp_path / "memory"

    mgr1 = SessionMemoryManager(memory_root, db_path=None)
    await mgr1.init()

    for i in range(5):
        await mgr1.store_finding(_make_finding(i))

    stored_count = len(mgr1._findings)

    mgr2 = SessionMemoryManager(memory_root, db_path=None)
    await mgr2.init()
    # Tier A only: findings loaded from MEMORY.md on disk
    assert len(mgr2._findings) == stored_count


# ---------------------------------------------------------------------------
# C3-2: Dedup skips known patterns
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_dedup_skips_known_patterns() -> None:
    """C3: Known patterns are not re-discovered."""
    known = [
        {"column_a": "speed", "column_b": "distance", "pattern_type": "correlation"},
        {"column_a": "time", "column_b": "energy", "pattern_type": "temporal"},
    ]
    dedup = PatternDeduplicator(known)

    # Already-known pattern
    duplicate = {"column_a": "speed", "column_b": "distance", "pattern_type": "correlation"}
    assert dedup.is_duplicate(duplicate) is True

    # New pattern
    new_pattern = {"column_a": "force", "column_b": "mass", "pattern_type": "correlation"}
    assert dedup.is_duplicate(new_pattern) is False


@pytest.mark.e2e
def test_dedup_filters_list() -> None:
    """C3: deduplicate() removes known patterns from a list."""
    known = [
        {"column_a": "a", "column_b": "b", "pattern_type": "correlation"},
    ]
    dedup = PatternDeduplicator(known)

    patterns = [
        {"column_a": "a", "column_b": "b", "pattern_type": "correlation"},  # dup
        {"column_a": "c", "column_b": "d", "pattern_type": "cluster"},  # new
        {"column_a": "e", "column_b": "f", "pattern_type": "anomaly"},  # new
    ]
    result = dedup.deduplicate(patterns)
    assert len(result) == 2
    assert all(p["column_a"] != "a" for p in result)


# ---------------------------------------------------------------------------
# C3-3: is_known_pattern on SessionMemoryManager
# ---------------------------------------------------------------------------


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_session_manager_is_known_pattern(tmp_path: Path) -> None:
    """SessionMemoryManager.is_known_pattern returns True for stored findings."""
    mgr = SessionMemoryManager(tmp_path / "memory")
    await mgr.init()

    finding = {
        "column_a": "speed",
        "column_b": "distance",
        "pattern_type": "correlation",
    }
    assert mgr.is_known_pattern(finding) is False

    await mgr.store_finding(finding)
    assert mgr.is_known_pattern(finding) is True
