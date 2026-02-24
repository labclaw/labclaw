"""Edge-case tests for optimization modules.

Covers:
  - optimizer.py   lines 102, 111, 153, 158
  - approval.py    lines 90, 158, 163, 166
  - safety.py      lines 102-108, 113
"""

from __future__ import annotations

import pytest

from labclaw.core.schemas import SafetyLevel
from labclaw.optimization.approval import ApprovalGate
from labclaw.optimization.optimizer import (
    BayesianOptimizer,
    OptimizationResult,
    ParameterDimension,
    ParameterSpace,
)
from labclaw.optimization.safety import (
    SafetyConstraint,
    ScientificSafetyCheck,
    ScientificSafetyValidator,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dim(name: str = "lr", low: float = 0.0, high: float = 1.0) -> ParameterDimension:
    return ParameterDimension(name=name, low=low, high=high)


def _space(name: str = "test", dims: list[ParameterDimension] | None = None) -> ParameterSpace:
    return ParameterSpace(name=name, dimensions=dims if dims is not None else [_dim()])


def _optimizer(dims: list[ParameterDimension] | None = None) -> BayesianOptimizer:
    return BayesianOptimizer(_space(dims=dims))


def _passed_check(proposal_id: str = "pid-001") -> ScientificSafetyCheck:
    return ScientificSafetyCheck(
        proposal_id=proposal_id,
        passed=True,
        level=SafetyLevel.SAFE,
        checks=[],
    )


def _failed_check(proposal_id: str = "pid-001") -> ScientificSafetyCheck:
    return ScientificSafetyCheck(
        proposal_id=proposal_id,
        passed=False,
        level=SafetyLevel.BLOCKED,
        checks=[],
    )


# ---------------------------------------------------------------------------
# BayesianOptimizer — constructor guards
# ---------------------------------------------------------------------------


class TestBayesianOptimizerInit:
    def test_empty_dimensions_raises(self) -> None:
        with pytest.raises(ValueError, match="at least one dimension"):
            BayesianOptimizer(ParameterSpace(name="empty", dimensions=[]))

    def test_valid_space_creates_instance(self) -> None:
        opt = _optimizer()
        assert opt is not None


# ---------------------------------------------------------------------------
# BayesianOptimizer — suggest
# ---------------------------------------------------------------------------


class TestBayesianOptimizerSuggest:
    def test_suggest_zero_raises(self) -> None:
        opt = _optimizer()
        with pytest.raises(ValueError, match="positive"):
            opt.suggest(n=0)

    def test_suggest_negative_raises(self) -> None:
        opt = _optimizer()
        with pytest.raises(ValueError, match="positive"):
            opt.suggest(n=-3)

    def test_suggest_returns_correct_count(self) -> None:
        opt = _optimizer()
        proposals = opt.suggest(n=3)
        assert len(proposals) == 3
        for p in proposals:
            assert "lr" in p.parameters
            assert 0.0 <= p.parameters["lr"] <= 1.0


# ---------------------------------------------------------------------------
# BayesianOptimizer — get_best and get_history
# ---------------------------------------------------------------------------


class TestBayesianOptimizerHistory:
    def test_get_best_empty(self) -> None:
        opt = _optimizer()
        assert opt.get_best() is None

    def test_get_history_empty(self) -> None:
        opt = _optimizer()
        assert opt.get_history() == []

    def test_tell_and_get_best_returns_max_objective(self) -> None:
        opt = _optimizer()
        r1 = OptimizationResult(iteration=1, parameters={"lr": 0.1}, objective_value=0.5)
        r2 = OptimizationResult(iteration=2, parameters={"lr": 0.2}, objective_value=0.9)
        opt.tell(r1)
        opt.tell(r2)
        best = opt.get_best()
        assert best is not None
        assert best.objective_value == pytest.approx(0.9)

    def test_get_history_returns_all_results(self) -> None:
        opt = _optimizer()
        r1 = OptimizationResult(iteration=1, parameters={"lr": 0.1}, objective_value=0.3)
        r2 = OptimizationResult(iteration=2, parameters={"lr": 0.5}, objective_value=0.7)
        opt.tell(r1)
        opt.tell(r2)
        history = opt.get_history()
        assert len(history) == 2
        assert history[0].objective_value == pytest.approx(0.3)
        assert history[1].objective_value == pytest.approx(0.7)


# ---------------------------------------------------------------------------
# ApprovalGate
# ---------------------------------------------------------------------------


class TestApprovalGate:
    def _proposal(self) -> object:
        from labclaw.optimization.optimizer import ExperimentProposal

        return ExperimentProposal(parameters={"lr": 0.01}, iteration=1)

    def test_reject_failed_safety_raises(self) -> None:
        gate = ApprovalGate()
        proposal = self._proposal()
        check = _failed_check(proposal.proposal_id)  # type: ignore[attr-defined]
        with pytest.raises(ValueError, match="safety check failed"):
            gate.request_approval(proposal, check)  # type: ignore[arg-type]

    def test_approve_request(self) -> None:
        gate = ApprovalGate()
        proposal = self._proposal()
        check = _passed_check(proposal.proposal_id)  # type: ignore[attr-defined]
        req = gate.request_approval(proposal, check)  # type: ignore[arg-type]
        approved = gate.approve(req.request_id, approver="pi@lab.com")
        assert approved.status == "approved"
        assert approved.decided_by == "pi@lab.com"

    def test_reject_request(self) -> None:
        gate = ApprovalGate()
        proposal = self._proposal()
        check = _passed_check(proposal.proposal_id)  # type: ignore[attr-defined]
        req = gate.request_approval(proposal, check)  # type: ignore[arg-type]
        rejected = gate.reject(req.request_id, approver="pi@lab.com", reason="too risky")
        assert rejected.status == "rejected"
        assert rejected.rejection_reason == "too risky"

    def test_get_pending_filters_correctly(self) -> None:
        from labclaw.optimization.optimizer import ExperimentProposal

        gate = ApprovalGate()

        p1 = ExperimentProposal(parameters={"lr": 0.01}, iteration=1)
        p2 = ExperimentProposal(parameters={"lr": 0.05}, iteration=2)
        c1 = _passed_check(p1.proposal_id)
        c2 = _passed_check(p2.proposal_id)

        req1 = gate.request_approval(p1, c1)
        req2 = gate.request_approval(p2, c2)

        gate.approve(req1.request_id, approver="pi")

        pending = gate.get_pending()
        assert len(pending) == 1
        assert pending[0].request_id == req2.request_id

    def test_approve_nonexistent_raises_key_error(self) -> None:
        gate = ApprovalGate()
        with pytest.raises(KeyError):
            gate.approve("nonexistent-id", approver="pi")

    def test_approve_already_approved_raises_value_error(self) -> None:
        gate = ApprovalGate()
        proposal = self._proposal()
        check = _passed_check(proposal.proposal_id)  # type: ignore[attr-defined]
        req = gate.request_approval(proposal, check)  # type: ignore[arg-type]
        gate.approve(req.request_id, approver="pi")
        with pytest.raises(ValueError, match="not 'pending'"):
            gate.approve(req.request_id, approver="pi")


# ---------------------------------------------------------------------------
# ScientificSafetyValidator
# ---------------------------------------------------------------------------


class TestScientificSafetyValidator:
    def _proposal_with(self, params: dict) -> object:
        from labclaw.optimization.optimizer import ExperimentProposal

        return ExperimentProposal(parameters=params, iteration=1)

    def test_missing_parameter_fails(self) -> None:
        validator = ScientificSafetyValidator()
        proposal = self._proposal_with({"y": 0.5})  # "x" is absent
        constraint = SafetyConstraint(parameter="x", min_value=0.0, max_value=1.0)
        result = validator.validate(proposal, [constraint])  # type: ignore[arg-type]
        assert result.passed is False
        assert result.level == SafetyLevel.BLOCKED
        assert any("absent" in c.message for c in result.checks)

    def test_below_min_fails(self) -> None:
        validator = ScientificSafetyValidator()
        proposal = self._proposal_with({"lr": -0.1})
        constraint = SafetyConstraint(parameter="lr", min_value=0.0)
        result = validator.validate(proposal, [constraint])  # type: ignore[arg-type]
        assert result.passed is False
        assert result.level == SafetyLevel.BLOCKED
        assert any("below minimum" in c.message for c in result.checks)

    def test_above_max_fails(self) -> None:
        validator = ScientificSafetyValidator()
        proposal = self._proposal_with({"lr": 1.5})
        constraint = SafetyConstraint(parameter="lr", max_value=1.0)
        result = validator.validate(proposal, [constraint])  # type: ignore[arg-type]
        assert result.passed is False
        assert result.level == SafetyLevel.BLOCKED
        assert any("above maximum" in c.message for c in result.checks)

    def test_all_within_bounds_passes(self) -> None:
        validator = ScientificSafetyValidator()
        proposal = self._proposal_with({"lr": 0.01, "batch": 32.0})
        constraints = [
            SafetyConstraint(parameter="lr", min_value=0.0, max_value=0.1),
            SafetyConstraint(parameter="batch", min_value=1.0, max_value=64.0),
        ]
        result = validator.validate(proposal, constraints)  # type: ignore[arg-type]
        assert result.passed is True
        assert result.level == SafetyLevel.SAFE
        assert all(c.passed for c in result.checks)

    def test_no_constraints_passes(self) -> None:
        validator = ScientificSafetyValidator()
        proposal = self._proposal_with({"lr": 0.01})
        result = validator.validate(proposal, [])  # type: ignore[arg-type]
        assert result.passed is True
        assert result.level == SafetyLevel.SAFE
