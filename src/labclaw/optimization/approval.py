"""Human-in-the-loop approval workflow for experiment execution.

Spec: docs/specs/L3-optimization.md
Design doc: section 5.4 (Conductor), section 9.3 (Two-Layer Safety)

Proposals that pass scientific safety are submitted for human review.
The PI (or designated approver) can approve or reject with reason.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from labclaw.core.events import event_registry
from labclaw.hardware.schemas import SafetyCheckResult
from labclaw.optimization.optimizer import ExperimentProposal
from labclaw.optimization.safety import ScientificSafetyCheck

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------

class ApprovalRequest(BaseModel):
    """Human approval request for experiment execution."""

    request_id: str = Field(default_factory=_uuid)
    proposal: ExperimentProposal
    scientific_safety: ScientificSafetyCheck
    hardware_safety: SafetyCheckResult | None = None
    status: str = "pending"
    requested_at: datetime = Field(default_factory=_now)
    decided_at: datetime | None = None
    decided_by: str | None = None
    rejection_reason: str | None = None


# ---------------------------------------------------------------------------
# Register events
# ---------------------------------------------------------------------------

_APPROVAL_EVENTS = [
    "optimization.approval.requested",
    "optimization.approval.decided",
]

for _evt in _APPROVAL_EVENTS:
    if not event_registry.is_registered(_evt):
        event_registry.register(_evt)


# ---------------------------------------------------------------------------
# ApprovalGate
# ---------------------------------------------------------------------------

class ApprovalGate:
    """Human-in-the-loop approval workflow for experiment execution."""

    def __init__(self) -> None:
        self._requests: dict[str, ApprovalRequest] = {}

    def request_approval(
        self,
        proposal: ExperimentProposal,
        scientific_check: ScientificSafetyCheck,
    ) -> ApprovalRequest:
        """Create an approval request with status 'pending'.

        Raises ValueError if the scientific safety check did not pass.
        """
        if not scientific_check.passed:
            raise ValueError(
                f"Cannot request approval: scientific safety check failed "
                f"for proposal {proposal.proposal_id!r} "
                f"(level={scientific_check.level.value})"
            )

        request = ApprovalRequest(
            proposal=proposal,
            scientific_safety=scientific_check,
        )
        self._requests[request.request_id] = request

        event_registry.emit(
            "optimization.approval.requested",
            payload={
                "request_id": request.request_id,
                "proposal_id": proposal.proposal_id,
                "status": request.status,
            },
        )

        return request

    def approve(self, request_id: str, approver: str) -> ApprovalRequest:
        """Approve a pending request."""
        request = self._get_pending(request_id)
        request = request.model_copy(update={
            "status": "approved",
            "decided_at": _now(),
            "decided_by": approver,
        })
        self._requests[request_id] = request

        event_registry.emit(
            "optimization.approval.decided",
            payload={
                "request_id": request_id,
                "status": "approved",
                "decided_by": approver,
            },
        )

        return request

    def reject(self, request_id: str, approver: str, reason: str) -> ApprovalRequest:
        """Reject a pending request with reason."""
        request = self._get_pending(request_id)
        request = request.model_copy(update={
            "status": "rejected",
            "decided_at": _now(),
            "decided_by": approver,
            "rejection_reason": reason,
        })
        self._requests[request_id] = request

        event_registry.emit(
            "optimization.approval.decided",
            payload={
                "request_id": request_id,
                "status": "rejected",
                "decided_by": approver,
            },
        )

        return request

    def get_pending(self) -> list[ApprovalRequest]:
        """Return all requests with status 'pending'."""
        return [r for r in self._requests.values() if r.status == "pending"]

    def _get_pending(self, request_id: str) -> ApprovalRequest:
        """Look up a request and verify it is pending."""
        if request_id not in self._requests:
            raise KeyError(f"Approval request {request_id!r} not found")
        request = self._requests[request_id]
        if request.status != "pending":
            raise ValueError(
                f"Request {request_id!r} is {request.status!r}, not 'pending'"
            )
        return request
