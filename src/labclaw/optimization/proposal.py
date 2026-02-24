"""Experiment pipeline — coordinator for propose-validate-approve workflow.

Spec: docs/specs/L3-optimization.md
Design doc: section 5.4 (Conductor)

Orchestrates the full experiment proposal lifecycle:
  1. Optimizer suggests parameters
  2. Scientific safety validates against constraints
  3. Approval gate submits for human review
"""

from __future__ import annotations

import logging

from labclaw.optimization.approval import ApprovalGate, ApprovalRequest
from labclaw.optimization.optimizer import BayesianOptimizer
from labclaw.optimization.safety import SafetyConstraint, ScientificSafetyValidator

logger = logging.getLogger(__name__)


class ExperimentPipeline:
    """Coordinator for the propose-validate-approve experiment workflow."""

    def __init__(
        self,
        optimizer: BayesianOptimizer,
        safety_validator: ScientificSafetyValidator,
        approval_gate: ApprovalGate,
    ) -> None:
        self._optimizer = optimizer
        self._safety_validator = safety_validator
        self._approval_gate = approval_gate

    def propose_and_validate(
        self,
        constraints: list[SafetyConstraint],
    ) -> ApprovalRequest:
        """Suggest one experiment, validate safety, and request approval.

        Returns the ApprovalRequest (status: 'pending').
        """
        proposals = self._optimizer.suggest(n=1)
        proposal = proposals[0]

        safety_check = self._safety_validator.validate(proposal, constraints)

        return self._approval_gate.request_approval(proposal, safety_check)
