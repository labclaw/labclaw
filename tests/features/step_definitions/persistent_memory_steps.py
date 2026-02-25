"""BDD step definitions for Persistent Memory (C3: REMEMBER).

Feature: tests/features/layer4_memory/persistent_memory.feature
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from pytest_bdd import given, then, when

from labclaw.discovery.hypothesis import HypothesisGenerator, HypothesisInput
from labclaw.discovery.mining import PatternRecord
from labclaw.memory.dedup import PatternDeduplicator
from labclaw.memory.session_memory import SessionMemoryManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_known_patterns(n: int) -> list[dict[str, Any]]:
    return [
        {"column_a": f"a{i}", "column_b": f"b{i}", "pattern_type": "correlation"} for i in range(n)
    ]


def _make_finding(i: int) -> dict[str, Any]:
    return {
        "finding_id": f"f-{i}",
        "description": f"Test finding {i}",
        "column_a": f"col_a_{i}",
        "column_b": f"col_b_{i}",
        "pattern_type": "correlation",
    }


# ---------------------------------------------------------------------------
# Session Memory Manager fixtures
# ---------------------------------------------------------------------------


@given("a session memory manager with SQLite backend", target_fixture="session_mgr_ctx")
def session_mgr_with_sqlite(tmp_path: Path) -> dict[str, Any]:
    """Provide a dict holding memory_root and db_path for shared use."""
    return {
        "memory_root": tmp_path / "memory",
        "db_path": tmp_path / "tier_b.db",
        "stored_count": 0,
        "mgr2": None,
    }


@given("a fresh session memory manager", target_fixture="session_mgr_ctx")
def fresh_session_mgr(tmp_path: Path) -> dict[str, Any]:
    return {
        "memory_root": tmp_path / "memory",
        "db_path": None,
        "stored_count": 0,
        "mgr": None,
        "pattern": None,
        "is_known_result": None,
    }


# ---------------------------------------------------------------------------
# When steps
# ---------------------------------------------------------------------------


@when("I store 5 findings and create a new manager instance")
def store_5_findings_and_restart(session_mgr_ctx: dict[str, Any]) -> None:
    async def _run() -> None:
        mgr1 = SessionMemoryManager(session_mgr_ctx["memory_root"], session_mgr_ctx["db_path"])
        await mgr1.init()
        for i in range(5):
            await mgr1.store_finding(_make_finding(i))
        session_mgr_ctx["stored_count"] = len(mgr1._findings)
        if mgr1._tier_b is not None:
            await mgr1._tier_b.close()

        mgr2 = SessionMemoryManager(session_mgr_ctx["memory_root"], session_mgr_ctx["db_path"])
        await mgr2.init()
        session_mgr_ctx["mgr2"] = mgr2

    asyncio.run(_run())


@when("I check whether a new pattern is known")
def check_new_pattern_not_known(session_mgr_ctx: dict[str, Any]) -> None:
    async def _run() -> None:
        mgr = SessionMemoryManager(session_mgr_ctx["memory_root"])
        await mgr.init()
        session_mgr_ctx["mgr"] = mgr
        p = {"column_a": "x", "column_b": "y", "pattern_type": "correlation"}
        session_mgr_ctx["pattern"] = p
        session_mgr_ctx["is_known_result"] = mgr.is_known_pattern(p)

    asyncio.run(_run())


@when("I store a pattern and check if it is known")
def store_and_check_known(session_mgr_ctx: dict[str, Any]) -> None:
    async def _run() -> None:
        mgr = SessionMemoryManager(session_mgr_ctx["memory_root"])
        await mgr.init()
        session_mgr_ctx["mgr"] = mgr
        p = {"column_a": "speed", "column_b": "distance", "pattern_type": "correlation"}
        session_mgr_ctx["pattern"] = p
        await mgr.store_finding(p)
        session_mgr_ctx["is_known_result"] = mgr.is_known_pattern(p)

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Then steps — session manager
# ---------------------------------------------------------------------------


@then("at least 4 findings are retrievable")
def at_least_4_retrievable(session_mgr_ctx: dict[str, Any]) -> None:
    mgr2: SessionMemoryManager = session_mgr_ctx["mgr2"]
    assert mgr2 is not None

    async def _retrieve() -> list[dict[str, Any]]:
        return await mgr2.retrieve_findings()

    retrieved = asyncio.run(_retrieve())
    stored = session_mgr_ctx["stored_count"]
    assert len(retrieved) >= 4, f"Expected ≥4 findings, retrieved {len(retrieved)}/{stored}"
    if mgr2._tier_b is not None:
        asyncio.run(mgr2._tier_b.close())


@then("the retrieval rate is at least 0.9")
def retrieval_rate_at_least_90(session_mgr_ctx: dict[str, Any]) -> None:
    mgr2: SessionMemoryManager = session_mgr_ctx["mgr2"]
    assert mgr2 is not None
    rate = mgr2.get_retrieval_rate()
    assert rate >= 0.9, f"Expected retrieval rate ≥0.9, got {rate}"
    if mgr2._tier_b is not None:
        asyncio.run(mgr2._tier_b.close())


@then("it is not known")
def pattern_is_not_known(session_mgr_ctx: dict[str, Any]) -> None:
    assert session_mgr_ctx["is_known_result"] is False


@then("it is flagged as known")
def pattern_is_known(session_mgr_ctx: dict[str, Any]) -> None:
    assert session_mgr_ctx["is_known_result"] is True


# ---------------------------------------------------------------------------
# PatternDeduplicator fixtures and steps
# ---------------------------------------------------------------------------


@given("a pattern deduplicator with 3 known patterns", target_fixture="dedup_ctx")
def dedup_with_3_known() -> dict[str, Any]:
    known = _make_known_patterns(3)
    return {
        "dedup": PatternDeduplicator(known),
        "result": None,
        "checked_pattern": None,
        "patterns_to_dedup": [],
    }


@given("a list of 5 patterns where 2 are duplicates")
def add_5_patterns_2_dup(dedup_ctx: dict[str, Any]) -> None:
    """Add a 5-pattern list where patterns 0 and 1 match the known set."""
    dedup_ctx["patterns_to_dedup"] = [
        # duplicates of known patterns 0 and 1
        {"column_a": "a0", "column_b": "b0", "pattern_type": "correlation"},
        {"column_a": "a1", "column_b": "b1", "pattern_type": "correlation"},
        # 3 unique new patterns
        {"column_a": "x", "column_b": "y", "pattern_type": "cluster"},
        {"column_a": "p", "column_b": "q", "pattern_type": "anomaly"},
        {"column_a": "m", "column_b": "n", "pattern_type": "temporal"},
    ]


@when("I check a pattern that matches a known one")
def check_known_pattern(dedup_ctx: dict[str, Any]) -> None:
    p = {"column_a": "a0", "column_b": "b0", "pattern_type": "correlation"}
    dedup_ctx["checked_pattern"] = p
    dedup_ctx["result"] = dedup_ctx["dedup"].is_duplicate(p)


@when("I check a completely new pattern")
def check_new_pattern(dedup_ctx: dict[str, Any]) -> None:
    p = {"column_a": "new_x", "column_b": "new_y", "pattern_type": "cluster"}
    dedup_ctx["checked_pattern"] = p
    dedup_ctx["result"] = dedup_ctx["dedup"].is_duplicate(p)


@when("I deduplicate the list")
def run_deduplication(dedup_ctx: dict[str, Any]) -> None:
    dedup_ctx["result"] = dedup_ctx["dedup"].deduplicate(dedup_ctx["patterns_to_dedup"])


@then("it is flagged as duplicate")
def pattern_is_duplicate(dedup_ctx: dict[str, Any]) -> None:
    assert dedup_ctx["result"] is True


@then("it is not flagged as duplicate")
def pattern_not_duplicate(dedup_ctx: dict[str, Any]) -> None:
    assert dedup_ctx["result"] is False


@then("3 unique patterns remain")
def three_unique_patterns_remain(dedup_ctx: dict[str, Any]) -> None:
    result = dedup_ctx["result"]
    assert isinstance(result, list)
    assert len(result) == 3, f"Expected 3 unique patterns, got {len(result)}: {result}"


# ---------------------------------------------------------------------------
# Memory-assisted hypothesis steps
# ---------------------------------------------------------------------------


@given("past findings about speed-distance correlation", target_fixture="hypothesis_ctx")
def past_findings_speed_distance() -> dict[str, Any]:
    return {
        "context_findings": [
            {
                "finding_id": "f-speed-dist",
                "description": "speed is correlated with distance (r=0.92)",
                "column_a": "speed",
                "column_b": "distance",
                "pattern_type": "correlation",
            }
        ],
        "hypotheses": [],
    }


@when("I generate hypotheses with context")
def generate_hypotheses_with_context(hypothesis_ctx: dict[str, Any]) -> None:
    pattern = PatternRecord(
        pattern_type="correlation",
        description="speed vs distance",
        confidence=0.8,
        evidence={"col_a": "speed", "col_b": "distance", "r": 0.92, "p_value": 0.001},
    )
    hi = HypothesisInput(
        patterns=[pattern],
        context_findings=hypothesis_ctx["context_findings"],
    )
    gen = HypothesisGenerator()
    hypothesis_ctx["hypotheses"] = gen.generate(hi)


@then("the hypotheses reference the past findings")
def hypotheses_reference_past_findings(hypothesis_ctx: dict[str, Any]) -> None:
    hyps = hypothesis_ctx["hypotheses"]
    assert hyps, "Expected at least one hypothesis"
    combined = " ".join(h.statement for h in hyps).lower()
    assert "building on past findings" in combined, (
        f"Expected past findings reference in: {combined!r}"
    )
