from __future__ import annotations

from unittest.mock import MagicMock

from labclaw.core.schemas import SafetyLevel
from labclaw.optimization.approval import ApprovalRequest
from labclaw.optimization.optimizer import ExperimentProposal
from labclaw.optimization.proposal import ExperimentPipeline
from labclaw.optimization.safety import SafetyConstraint, ScientificSafetyCheck

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_proposal() -> ExperimentProposal:
    return ExperimentProposal(parameters={"lr": 0.01}, iteration=1)


def _make_safety_check(proposal_id: str, passed: bool = True) -> ScientificSafetyCheck:
    return ScientificSafetyCheck(
        proposal_id=proposal_id,
        passed=passed,
        level=SafetyLevel.SAFE if passed else SafetyLevel.BLOCKED,
        checks=[],
    )


def _make_approval_request(
    proposal: ExperimentProposal,
    safety_check: ScientificSafetyCheck,
) -> ApprovalRequest:
    return ApprovalRequest(
        proposal=proposal,
        scientific_safety=safety_check,
        status="pending",
    )


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------


def test_init_stores_components() -> None:
    optimizer = MagicMock()
    safety = MagicMock()
    approval = MagicMock()

    pipeline = ExperimentPipeline(optimizer, safety, approval)

    assert pipeline._optimizer is optimizer
    assert pipeline._safety_validator is safety
    assert pipeline._approval_gate is approval


# ---------------------------------------------------------------------------
# propose_and_validate
# ---------------------------------------------------------------------------


def test_propose_and_validate_calls_chain_in_order() -> None:
    proposal = _make_proposal()
    safety_check = _make_safety_check(proposal.proposal_id, passed=True)
    approval_request = _make_approval_request(proposal, safety_check)

    optimizer = MagicMock()
    optimizer.suggest.return_value = [proposal]

    safety = MagicMock()
    safety.validate.return_value = safety_check

    approval = MagicMock()
    approval.request_approval.return_value = approval_request

    constraints = [SafetyConstraint(parameter="lr", min_value=0.0, max_value=1.0)]
    pipeline = ExperimentPipeline(optimizer, safety, approval)
    result = pipeline.propose_and_validate(constraints)

    optimizer.suggest.assert_called_once_with(n=1)
    safety.validate.assert_called_once_with(proposal, constraints)
    approval.request_approval.assert_called_once_with(proposal, safety_check)
    assert result is approval_request
