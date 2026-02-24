"""PersonaManager — digital staff training, benchmarking, promotion/demotion.

Spec: docs/specs/L5-persona.md
Design doc: section 7 (Digital Staff Training & Promotion)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from labclaw.core.events import event_registry
from labclaw.core.schemas import MemberRole
from labclaw.persona.schemas import (
    BenchmarkResult,
    CorrectionEntry,
    MemberProfile,
    PromotionGate,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Register events at module import time
# ---------------------------------------------------------------------------

_EVENTS = [
    "persona.member.created",
    "persona.benchmark.recorded",
    "persona.correction.recorded",
    "persona.member.promoted",
    "persona.member.demoted",
]

for _evt in _EVENTS:
    if not event_registry.is_registered(_evt):
        event_registry.register(_evt)

# ---------------------------------------------------------------------------
# Promotion ladder
# ---------------------------------------------------------------------------

PROMOTION_LADDER: list[PromotionGate] = [
    PromotionGate(
        from_role=MemberRole.DIGITAL_INTERN,
        to_role=MemberRole.DIGITAL_ANALYST,
        min_benchmarks=10,
        min_avg_score=0.7,
        requires_approval=False,
    ),
    PromotionGate(
        from_role=MemberRole.DIGITAL_ANALYST,
        to_role=MemberRole.DIGITAL_SPECIALIST,
        min_benchmarks=25,
        min_avg_score=0.85,
        requires_approval=True,
    ),
]

# Ordered digital roles for demotion logic
_DIGITAL_ROLES = [
    MemberRole.DIGITAL_INTERN,
    MemberRole.DIGITAL_ANALYST,
    MemberRole.DIGITAL_SPECIALIST,
]


class PersonaManager:
    """Manages human and digital lab members: creation, benchmarks, promotions."""

    def __init__(self) -> None:
        self._members: dict[str, MemberProfile] = {}
        self._benchmarks: dict[str, list[BenchmarkResult]] = {}
        self._corrections: dict[str, list[CorrectionEntry]] = {}

    def create_member(
        self, name: str, role: MemberRole, is_digital: bool
    ) -> MemberProfile:
        """Create a new lab member (human or digital)."""
        profile = MemberProfile(name=name, role=role, is_digital=is_digital)
        self._members[profile.member_id] = profile
        self._benchmarks[profile.member_id] = []
        self._corrections[profile.member_id] = []

        event_registry.emit(
            "persona.member.created",
            payload={
                "member_id": profile.member_id,
                "name": profile.name,
                "role": profile.role.value,
            },
        )
        logger.info("Created member %s (%s, %s)", name, role.value, profile.member_id)
        return profile

    def get_member(self, member_id: str) -> MemberProfile:
        """Retrieve a member by ID. Raises KeyError if not found."""
        if member_id not in self._members:
            raise KeyError(f"Member {member_id!r} not found")
        return self._members[member_id]

    def record_benchmark(
        self,
        member_id: str,
        task_type: str,
        score: float,
        details: dict | None = None,
    ) -> BenchmarkResult:
        """Record a benchmark result for a member."""
        if member_id not in self._members:
            raise KeyError(f"Member {member_id!r} not found")

        result = BenchmarkResult(
            member_id=member_id,
            task_type=task_type,
            score=score,
            details=details or {},
        )
        self._benchmarks[member_id].append(result)

        event_registry.emit(
            "persona.benchmark.recorded",
            payload={
                "member_id": member_id,
                "task_type": task_type,
                "score": score,
            },
        )
        logger.debug("Recorded benchmark for %s: %s=%.2f", member_id, task_type, score)
        return result

    def record_correction(
        self,
        member_id: str,
        category: str,
        detail: str,
        corrected_by: str,
    ) -> CorrectionEntry:
        """Log a correction entry for a member."""
        if member_id not in self._members:
            raise KeyError(f"Member {member_id!r} not found")

        entry = CorrectionEntry(
            member_id=member_id,
            category=category,
            detail=detail,
            corrected_by=corrected_by,
        )
        self._corrections[member_id].append(entry)

        event_registry.emit(
            "persona.correction.recorded",
            payload={
                "member_id": member_id,
                "category": category,
                "corrected_by": corrected_by,
            },
        )
        logger.debug("Recorded correction for %s: %s", member_id, category)
        return entry

    def get_benchmarks(self, member_id: str) -> list[BenchmarkResult]:
        """Get all benchmarks for a member."""
        if member_id not in self._members:
            raise KeyError(f"Member {member_id!r} not found")
        return list(self._benchmarks[member_id])

    def get_corrections(self, member_id: str) -> list[CorrectionEntry]:
        """Get all corrections for a member."""
        if member_id not in self._members:
            raise KeyError(f"Member {member_id!r} not found")
        return list(self._corrections[member_id])

    def check_promotion(self, member_id: str) -> PromotionGate | None:
        """Check if a member is eligible for promotion.

        Returns the matching PromotionGate if eligible, None otherwise.
        """
        member = self.get_member(member_id)
        benchmarks = self._benchmarks.get(member_id, [])

        for gate in PROMOTION_LADDER:
            if gate.from_role != member.role:
                continue
            if len(benchmarks) < gate.min_benchmarks:
                return None
            avg_score = sum(b.score for b in benchmarks) / len(benchmarks)
            if avg_score >= gate.min_avg_score:
                return gate
            return None

        return None

    def promote(self, member_id: str) -> MemberProfile:
        """Promote a digital member to the next role.

        Raises ValueError if the member cannot be promoted.
        """
        member = self.get_member(member_id)

        if not member.is_digital:
            raise ValueError(f"Cannot promote non-digital member {member_id!r}")

        gate = self.check_promotion(member_id)
        if gate is None:
            raise ValueError(
                f"Member {member_id!r} does not meet promotion requirements"
            )

        from_role = member.role
        member.role = gate.to_role
        member.promoted_at = datetime.now(UTC)

        event_registry.emit(
            "persona.member.promoted",
            payload={
                "member_id": member_id,
                "from_role": from_role.value,
                "to_role": gate.to_role.value,
            },
        )
        logger.info("Promoted %s: %s -> %s", member_id, from_role.value, gate.to_role.value)
        return member

    def demote(self, member_id: str) -> MemberProfile:
        """Demote a digital member one step down the ladder.

        Raises ValueError for human members or members already at digital_intern.
        """
        member = self.get_member(member_id)

        if not member.is_digital:
            raise ValueError(f"Cannot demote non-digital member {member_id!r}")

        try:
            idx = _DIGITAL_ROLES.index(member.role)
        except ValueError:
            raise ValueError(
                f"Member role {member.role!r} is not on the digital ladder"
            ) from None

        if idx == 0:
            raise ValueError(
                f"Member {member_id!r} is already at the lowest digital role"
            )

        from_role = member.role
        member.role = _DIGITAL_ROLES[idx - 1]

        event_registry.emit(
            "persona.member.demoted",
            payload={
                "member_id": member_id,
                "from_role": from_role.value,
                "to_role": member.role.value,
            },
        )
        logger.info("Demoted %s: %s -> %s", member_id, from_role.value, member.role.value)
        return member
