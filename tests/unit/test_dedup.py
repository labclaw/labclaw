"""Unit tests for PatternDeduplicator (C3: REMEMBER)."""

from __future__ import annotations

from typing import Any

from labclaw.memory.dedup import PatternDeduplicator


def _p(col_a: str, col_b: str, ptype: str) -> dict[str, Any]:
    return {"column_a": col_a, "column_b": col_b, "pattern_type": ptype}


# ---------------------------------------------------------------------------
# is_duplicate
# ---------------------------------------------------------------------------


class TestIsDuplicate:
    def test_identical_pattern_is_duplicate(self) -> None:
        known = [_p("x", "y", "correlation")]
        dedup = PatternDeduplicator(known)
        assert dedup.is_duplicate(_p("x", "y", "correlation")) is True

    def test_different_col_a_not_duplicate(self) -> None:
        known = [_p("x", "y", "correlation")]
        dedup = PatternDeduplicator(known)
        assert dedup.is_duplicate(_p("z", "y", "correlation")) is False

    def test_different_col_b_not_duplicate(self) -> None:
        known = [_p("x", "y", "correlation")]
        dedup = PatternDeduplicator(known)
        assert dedup.is_duplicate(_p("x", "z", "correlation")) is False

    def test_different_pattern_type_not_duplicate(self) -> None:
        known = [_p("x", "y", "correlation")]
        dedup = PatternDeduplicator(known)
        assert dedup.is_duplicate(_p("x", "y", "anomaly")) is False

    def test_empty_known_never_duplicate(self) -> None:
        dedup = PatternDeduplicator([])
        assert dedup.is_duplicate(_p("a", "b", "cluster")) is False

    def test_missing_column_a_not_duplicate(self) -> None:
        """Patterns without column_a cannot be flagged as duplicates."""
        known = [_p("x", "y", "correlation")]
        dedup = PatternDeduplicator(known)
        assert dedup.is_duplicate({"column_b": "y", "pattern_type": "correlation"}) is False

    def test_missing_column_b_not_duplicate(self) -> None:
        known = [_p("x", "y", "correlation")]
        dedup = PatternDeduplicator(known)
        assert dedup.is_duplicate({"column_a": "x", "pattern_type": "correlation"}) is False

    def test_missing_pattern_type_not_duplicate(self) -> None:
        known = [_p("x", "y", "correlation")]
        dedup = PatternDeduplicator(known)
        assert dedup.is_duplicate({"column_a": "x", "column_b": "y"}) is False

    def test_matches_any_known(self) -> None:
        known = [_p("a", "b", "correlation"), _p("c", "d", "temporal")]
        dedup = PatternDeduplicator(known)
        assert dedup.is_duplicate(_p("c", "d", "temporal")) is True

    def test_no_match_among_multiple_known(self) -> None:
        known = [_p("a", "b", "correlation"), _p("c", "d", "temporal")]
        dedup = PatternDeduplicator(known)
        assert dedup.is_duplicate(_p("e", "f", "cluster")) is False


# ---------------------------------------------------------------------------
# deduplicate
# ---------------------------------------------------------------------------


class TestDeduplicate:
    def test_removes_known_duplicate(self) -> None:
        known = [_p("a", "b", "correlation")]
        dedup = PatternDeduplicator(known)
        patterns = [_p("a", "b", "correlation"), _p("c", "d", "cluster")]
        result = dedup.deduplicate(patterns)
        assert len(result) == 1
        assert result[0]["column_a"] == "c"

    def test_preserves_all_unique(self) -> None:
        dedup = PatternDeduplicator([])
        patterns = [_p("a", "b", "correlation"), _p("c", "d", "cluster")]
        result = dedup.deduplicate(patterns)
        assert len(result) == 2

    def test_intra_list_dedup(self) -> None:
        """Duplicate within the input list is removed on second occurrence."""
        dedup = PatternDeduplicator([])
        patterns = [
            _p("x", "y", "correlation"),
            _p("x", "y", "correlation"),  # second copy
            _p("a", "b", "anomaly"),
        ]
        result = dedup.deduplicate(patterns)
        assert len(result) == 2

    def test_empty_list(self) -> None:
        dedup = PatternDeduplicator([_p("a", "b", "correlation")])
        result = dedup.deduplicate([])
        assert result == []

    def test_all_duplicates_removed(self) -> None:
        known = [_p("a", "b", "correlation"), _p("c", "d", "cluster")]
        dedup = PatternDeduplicator(known)
        result = dedup.deduplicate([_p("a", "b", "correlation"), _p("c", "d", "cluster")])
        assert result == []

    def test_preserves_order(self) -> None:
        dedup = PatternDeduplicator([])
        patterns = [
            _p("z", "y", "anomaly"),
            _p("a", "b", "correlation"),
            _p("m", "n", "temporal"),
        ]
        result = dedup.deduplicate(patterns)
        assert [r["column_a"] for r in result] == ["z", "a", "m"]

    def test_missing_fields_never_deduped(self) -> None:
        """Patterns without required fields always pass through."""
        known = [_p("a", "b", "correlation")]
        dedup = PatternDeduplicator(known)
        patterns = [{"description": "no columns"}]
        result = dedup.deduplicate(patterns)
        assert len(result) == 1

    def test_known_patterns_not_modified(self) -> None:
        """deduplicate does not mutate the known list."""
        known = [_p("a", "b", "correlation")]
        dedup = PatternDeduplicator(known)
        dedup.deduplicate([_p("c", "d", "cluster")])
        assert dedup._known[0] == _p("a", "b", "correlation")
