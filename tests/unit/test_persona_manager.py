"""Tests for PersonaManager: creation, benchmarks, corrections, promotion, demotion."""

from __future__ import annotations

import pytest

from labclaw.core.schemas import MemberRole
from labclaw.persona.manager import PersonaManager
from labclaw.persona.schemas import BenchmarkResult, CorrectionEntry, MemberProfile

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mgr() -> PersonaManager:
    return PersonaManager()


def _intern(mgr: PersonaManager) -> MemberProfile:
    return mgr.create_member("Bot-1", MemberRole.DIGITAL_INTERN, is_digital=True)


# ---------------------------------------------------------------------------
# create_member
# ---------------------------------------------------------------------------


def test_create_member_returns_profile() -> None:
    mgr = _mgr()
    profile = mgr.create_member("Alice", MemberRole.PI, is_digital=False)
    assert isinstance(profile, MemberProfile)
    assert profile.name == "Alice"
    assert profile.role == MemberRole.PI
    assert not profile.is_digital


def test_create_member_stored_by_id() -> None:
    mgr = _mgr()
    profile = _intern(mgr)
    assert mgr.get_member(profile.member_id) is profile


def test_get_member_missing_raises() -> None:
    mgr = _mgr()
    with pytest.raises(KeyError, match="not found"):
        mgr.get_member("nonexistent-id")


# ---------------------------------------------------------------------------
# record_benchmark
# ---------------------------------------------------------------------------


def test_record_benchmark_returns_result() -> None:
    mgr = _mgr()
    profile = _intern(mgr)
    result = mgr.record_benchmark(profile.member_id, "analysis", 0.8)
    assert isinstance(result, BenchmarkResult)
    assert result.score == 0.8
    assert result.task_type == "analysis"


def test_record_benchmark_accumulates() -> None:
    mgr = _mgr()
    profile = _intern(mgr)
    mgr.record_benchmark(profile.member_id, "analysis", 0.7)
    mgr.record_benchmark(profile.member_id, "analysis", 0.9)
    benchmarks = mgr.get_benchmarks(profile.member_id)
    assert len(benchmarks) == 2


def test_record_benchmark_missing_member_raises() -> None:
    mgr = _mgr()
    with pytest.raises(KeyError):
        mgr.record_benchmark("bad-id", "analysis", 0.5)


def test_get_benchmarks_missing_member_raises() -> None:
    mgr = _mgr()
    with pytest.raises(KeyError):
        mgr.get_benchmarks("bad-id")


# ---------------------------------------------------------------------------
# record_correction
# ---------------------------------------------------------------------------


def test_record_correction_returns_entry() -> None:
    mgr = _mgr()
    profile = _intern(mgr)
    entry = mgr.record_correction(profile.member_id, "data_error", "wrong unit", "supervisor-1")
    assert isinstance(entry, CorrectionEntry)
    assert entry.category == "data_error"
    assert entry.corrected_by == "supervisor-1"


def test_record_correction_accumulates() -> None:
    mgr = _mgr()
    profile = _intern(mgr)
    mgr.record_correction(profile.member_id, "cat_a", "d1", "sup")
    mgr.record_correction(profile.member_id, "cat_b", "d2", "sup")
    corrections = mgr.get_corrections(profile.member_id)
    assert len(corrections) == 2


def test_record_correction_missing_member_raises() -> None:
    mgr = _mgr()
    with pytest.raises(KeyError):
        mgr.record_correction("bad-id", "cat", "detail", "sup")


def test_get_corrections_missing_member_raises() -> None:
    mgr = _mgr()
    with pytest.raises(KeyError):
        mgr.get_corrections("bad-id")


# ---------------------------------------------------------------------------
# check_promotion
# ---------------------------------------------------------------------------


def test_check_promotion_not_enough_benchmarks() -> None:
    mgr = _mgr()
    profile = _intern(mgr)
    # Only 5 benchmarks, gate requires 10
    for _ in range(5):
        mgr.record_benchmark(profile.member_id, "analysis", 0.9)
    assert mgr.check_promotion(profile.member_id) is None


def test_check_promotion_score_too_low() -> None:
    mgr = _mgr()
    profile = _intern(mgr)
    for _ in range(10):
        mgr.record_benchmark(profile.member_id, "analysis", 0.5)  # below 0.7
    assert mgr.check_promotion(profile.member_id) is None


def test_check_promotion_eligible() -> None:
    mgr = _mgr()
    profile = _intern(mgr)
    for _ in range(10):
        mgr.record_benchmark(profile.member_id, "analysis", 0.9)
    gate = mgr.check_promotion(profile.member_id)
    assert gate is not None
    assert gate.to_role == MemberRole.DIGITAL_ANALYST


def test_check_promotion_non_ladder_role() -> None:
    mgr = _mgr()
    # PI is not on the digital ladder
    profile = mgr.create_member("Prof", MemberRole.PI, is_digital=False)
    assert mgr.check_promotion(profile.member_id) is None


# ---------------------------------------------------------------------------
# promote
# ---------------------------------------------------------------------------


def test_promote_advances_role() -> None:
    mgr = _mgr()
    profile = _intern(mgr)
    for _ in range(10):
        mgr.record_benchmark(profile.member_id, "analysis", 0.9)

    updated = mgr.promote(profile.member_id)

    assert updated.role == MemberRole.DIGITAL_ANALYST
    assert updated.promoted_at is not None


def test_promote_non_digital_raises() -> None:
    mgr = _mgr()
    profile = mgr.create_member("Alice", MemberRole.PI, is_digital=False)
    with pytest.raises(ValueError, match="non-digital"):
        mgr.promote(profile.member_id)


def test_promote_without_eligibility_raises() -> None:
    mgr = _mgr()
    profile = _intern(mgr)  # no benchmarks yet
    with pytest.raises(ValueError, match="does not meet"):
        mgr.promote(profile.member_id)


# ---------------------------------------------------------------------------
# demote
# ---------------------------------------------------------------------------


def test_demote_lowers_role() -> None:
    mgr = _mgr()
    profile = mgr.create_member("Bot-2", MemberRole.DIGITAL_ANALYST, is_digital=True)
    updated = mgr.demote(profile.member_id)
    assert updated.role == MemberRole.DIGITAL_INTERN


def test_demote_non_digital_raises() -> None:
    mgr = _mgr()
    profile = mgr.create_member("Alice", MemberRole.PI, is_digital=False)
    with pytest.raises(ValueError, match="non-digital"):
        mgr.demote(profile.member_id)


def test_demote_at_bottom_raises() -> None:
    mgr = _mgr()
    profile = _intern(mgr)  # already DIGITAL_INTERN
    with pytest.raises(ValueError, match="lowest digital role"):
        mgr.demote(profile.member_id)


def test_demote_non_ladder_role_raises() -> None:
    mgr = _mgr()
    # Create a digital member with a role not in the demotion ladder
    profile = mgr.create_member("Bot-3", MemberRole.DIGITAL_SPECIALIST, is_digital=True)
    # Manually move to a role outside _DIGITAL_ROLES
    profile.role = MemberRole.PI  # type: ignore[assignment]
    with pytest.raises(ValueError):
        mgr.demote(profile.member_id)
