"""Scientific safety constraints for closed-loop experiments.

Spec: docs/specs/L3-optimization.md
Design doc: section 9.3 (Two-Layer Safety)

Validates proposed experimental parameters against scientific constraints
(parameter bounds, animal welfare limits, protocol compliance).
This is Layer 1 of the two-layer safety system; hardware safety is Layer 2.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from labclaw.core.events import event_registry
from labclaw.core.schemas import SafetyLevel
from labclaw.optimization.optimizer import ExperimentProposal

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------


class SafetyConstraint(BaseModel):
    """A scientific safety constraint on a parameter."""

    parameter: str
    min_value: float | None = None
    max_value: float | None = None
    description: str = ""


class SafetyCheckDetail(BaseModel):
    """Result of a single safety constraint check."""

    name: str
    passed: bool
    message: str


class ScientificSafetyCheck(BaseModel):
    """Result of scientific safety validation for a proposal."""

    proposal_id: str
    passed: bool
    level: SafetyLevel
    checks: list[SafetyCheckDetail]
    checked_at: datetime = Field(default_factory=_now)


# ---------------------------------------------------------------------------
# Register events
# ---------------------------------------------------------------------------

_SAFETY_EVENTS = [
    "optimization.safety.checked",
]

for _evt in _SAFETY_EVENTS:
    if not event_registry.is_registered(_evt):
        event_registry.register(_evt)


# ---------------------------------------------------------------------------
# ScientificSafetyValidator
# ---------------------------------------------------------------------------


class ScientificSafetyValidator:
    """Validates experimental proposals against scientific safety constraints."""

    def validate(
        self,
        proposal: ExperimentProposal,
        constraints: list[SafetyConstraint],
    ) -> ScientificSafetyCheck:
        """Validate a proposal against safety constraints.

        Each proposed parameter is checked against min_value/max_value bounds.
        Any violation sets level to BLOCKED. All pass sets level to SAFE.
        """
        checks: list[SafetyCheckDetail] = []
        all_passed = True

        for constraint in constraints:
            param_name = constraint.parameter
            value = proposal.parameters.get(param_name)

            if value is None:
                all_passed = False
                checks.append(
                    SafetyCheckDetail(
                        name=param_name,
                        passed=False,
                        message=f"Parameter {param_name!r} is constrained but absent from proposal",
                    )
                )
                continue

            violations: list[str] = []

            if constraint.min_value is not None and value < constraint.min_value:
                violations.append(f"{param_name}={value} below minimum {constraint.min_value}")

            if constraint.max_value is not None and value > constraint.max_value:
                violations.append(f"{param_name}={value} above maximum {constraint.max_value}")

            if violations:
                all_passed = False
                checks.append(
                    SafetyCheckDetail(
                        name=param_name,
                        passed=False,
                        message="; ".join(violations),
                    )
                )
            else:
                checks.append(
                    SafetyCheckDetail(
                        name=param_name,
                        passed=True,
                        message=f"{param_name}={value} within bounds",
                    )
                )

        level = SafetyLevel.SAFE if all_passed else SafetyLevel.BLOCKED

        result = ScientificSafetyCheck(
            proposal_id=proposal.proposal_id,
            passed=all_passed,
            level=level,
            checks=checks,
        )

        event_registry.emit(
            "optimization.safety.checked",
            payload={
                "proposal_id": result.proposal_id,
                "passed": result.passed,
                "level": result.level.value,
            },
        )

        return result
