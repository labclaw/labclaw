"""Pydantic schemas for the L5 Persona subsystem.

Spec: docs/specs/L5-persona.md
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from labclaw.core.schemas import MemberRole


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class MemberProfile(BaseModel):
    """A human or digital lab member."""

    member_id: str = Field(default_factory=_uuid)
    name: str
    role: MemberRole
    is_digital: bool
    expertise: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_now)
    promoted_at: datetime | None = None


class BenchmarkResult(BaseModel):
    """A single benchmark measurement for a member."""

    member_id: str
    task_type: str
    score: float
    completed_at: datetime = Field(default_factory=_now)
    details: dict[str, Any] = Field(default_factory=dict)

    @field_validator("score")
    @classmethod
    def _score_in_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"Score must be between 0.0 and 1.0, got {v}")
        return v


class CorrectionEntry(BaseModel):
    """A logged correction when a mistake is found."""

    member_id: str
    category: str
    detail: str
    corrected_by: str
    timestamp: datetime = Field(default_factory=_now)


class PromotionGate(BaseModel):
    """Criteria required to advance from one role to the next."""

    from_role: MemberRole
    to_role: MemberRole
    min_benchmarks: int
    min_avg_score: float
    requires_approval: bool
