"""L5 Persona — digital staff training, benchmarking, and promotion.

Spec: docs/specs/L5-persona.md
Design doc: section 7 (Digital Staff Training & Promotion)
"""

from __future__ import annotations

from labclaw.persona.manager import PersonaManager
from labclaw.persona.schemas import (
    BenchmarkResult,
    CorrectionEntry,
    MemberProfile,
    PromotionGate,
)

__all__ = [
    "BenchmarkResult",
    "CorrectionEntry",
    "MemberProfile",
    "PersonaManager",
    "PromotionGate",
]
