"""BDD step definitions for L3 Optimization (EXPERIMENT).

Spec: docs/specs/L3-optimization.md
Uses conftest fixtures: event_capture
"""

from __future__ import annotations

import random

from pytest_bdd import given, parsers, then, when

from labclaw.core.events import event_registry
from labclaw.optimization.approval import ApprovalGate, ApprovalRequest
from labclaw.optimization.optimizer import (
    BayesianOptimizer,
    ExperimentProposal,
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
# Background
# ---------------------------------------------------------------------------


@given(
    "a parameter space with dimensions:",
    target_fixture="param_space",
)
def parameter_space_from_table(datatable: list) -> ParameterSpace:
    """Build a ParameterSpace from a BDD datatable."""
    headers = [str(c) for c in datatable[0]]
    rows = [{headers[i]: str(cell) for i, cell in enumerate(row)} for row in datatable[1:]]

    dims = [
        ParameterDimension(
            name=row["name"],
            low=float(row["low"]),
            high=float(row["high"]),
        )
        for row in rows
    ]
    return ParameterSpace(name="test_space", dimensions=dims)


@given(
    "the optimizer is initialized with this space",
    target_fixture="optimizer",
)
def optimizer_initialized(param_space: ParameterSpace, event_capture: object) -> BayesianOptimizer:
    """Create a BayesianOptimizer and subscribe event capture."""
    for evt_name in [
        "optimization.proposal.created",
        "optimization.result.recorded",
        "optimization.safety.checked",
        "optimization.approval.requested",
        "optimization.approval.decided",
    ]:
        event_registry.subscribe(evt_name, event_capture)  # type: ignore[arg-type]
    return BayesianOptimizer(param_space)


# ---------------------------------------------------------------------------
# Suggest proposals
# ---------------------------------------------------------------------------


@when(
    parsers.parse("I request {n:d} experiment proposals"),
    target_fixture="proposals",
)
def request_proposals(optimizer: BayesianOptimizer, n: int) -> list[ExperimentProposal]:
    return optimizer.suggest(n)


@then(parsers.parse("{n:d} proposals are returned"))
def check_proposal_count(proposals: list[ExperimentProposal], n: int) -> None:
    assert len(proposals) == n, f"Expected {n} proposals, got {len(proposals)}"


@then("each proposal has parameters within bounds")
def check_proposals_within_bounds(
    proposals: list[ExperimentProposal],
    param_space: ParameterSpace,
) -> None:
    bounds = {dim.name: (dim.low, dim.high) for dim in param_space.dimensions}
    for proposal in proposals:
        for name, value in proposal.parameters.items():
            low, high = bounds[name]
            assert low <= value <= high, (
                f"Proposal {proposal.proposal_id}: {name}={value} "
                f"outside [{low}, {high}]"
            )


# ---------------------------------------------------------------------------
# Record results and track best
# ---------------------------------------------------------------------------


@given(
    "I have suggested and recorded 5 experiments with objective values",
    target_fixture="recorded_results",
)
def suggest_and_record_5(optimizer: BayesianOptimizer) -> list[OptimizationResult]:
    rng = random.Random(42)
    results = []
    for i in range(5):
        proposals = optimizer.suggest(1)
        result = OptimizationResult(
            iteration=proposals[0].iteration,
            parameters=proposals[0].parameters,
            objective_value=rng.uniform(0.0, 100.0),
        )
        optimizer.tell(result)
        results.append(result)
    return results


@when("I query the best result", target_fixture="best_result")
def query_best(optimizer: BayesianOptimizer) -> OptimizationResult:
    result = optimizer.get_best()
    assert result is not None, "No best result found"
    return result


@then("the best result has the highest objective value")
def check_best_is_highest(
    best_result: OptimizationResult,
    recorded_results: list[OptimizationResult],
) -> None:
    max_value = max(r.objective_value for r in recorded_results)
    assert best_result.objective_value == max_value, (
        f"Best={best_result.objective_value}, expected max={max_value}"
    )


# ---------------------------------------------------------------------------
# Scientific safety
# ---------------------------------------------------------------------------


@given(
    "safety constraints:",
    target_fixture="constraints",
)
def safety_constraints_from_table(datatable: list) -> list[SafetyConstraint]:
    headers = [str(c) for c in datatable[0]]
    rows = [{headers[i]: str(cell) for i, cell in enumerate(row)} for row in datatable[1:]]

    return [
        SafetyConstraint(
            parameter=row["parameter"],
            min_value=float(row["min_value"]) if row.get("min_value") else None,
            max_value=float(row["max_value"]) if row.get("max_value") else None,
        )
        for row in rows
    ]


@when(
    parsers.parse("I validate a proposal with temperature {temp:g} and duration {dur:g}"),
    target_fixture="safety_result",
)
def validate_proposal_two_params(
    temp: float,
    dur: float,
    constraints: list[SafetyConstraint],
) -> ScientificSafetyCheck:
    proposal = ExperimentProposal(
        parameters={"temperature": temp, "duration": dur},
        iteration=1,
    )
    validator = ScientificSafetyValidator()
    return validator.validate(proposal, constraints)


@when(
    parsers.parse("I validate a proposal with temperature {temp:g}"),
    target_fixture="safety_result",
)
def validate_proposal_one_param(
    temp: float,
    constraints: list[SafetyConstraint],
) -> ScientificSafetyCheck:
    proposal = ExperimentProposal(
        parameters={"temperature": temp},
        iteration=1,
    )
    validator = ScientificSafetyValidator()
    return validator.validate(proposal, constraints)


@then("the scientific safety check passes")
def check_safety_passes(safety_result: ScientificSafetyCheck) -> None:
    assert safety_result.passed, (
        f"Safety check failed: {[c.message for c in safety_result.checks if not c.passed]}"
    )


@then("the scientific safety check fails")
def check_safety_fails(safety_result: ScientificSafetyCheck) -> None:
    assert not safety_result.passed, "Safety check passed when it should have failed"


@then(parsers.parse('the safety level is "{level}"'))
def check_safety_level(safety_result: ScientificSafetyCheck, level: str) -> None:
    assert safety_result.level.value == level, (
        f"Expected level {level!r}, got {safety_result.level.value!r}"
    )


# ---------------------------------------------------------------------------
# Approval workflow
# ---------------------------------------------------------------------------


@given(
    "a proposal that passed scientific safety",
    target_fixture="passed_proposal_and_check",
)
def proposal_passed_safety(
    optimizer: BayesianOptimizer,
) -> tuple[ExperimentProposal, ScientificSafetyCheck]:
    proposals = optimizer.suggest(1)
    proposal = proposals[0]
    validator = ScientificSafetyValidator()
    check = validator.validate(proposal, [])
    return proposal, check


@when("I request approval", target_fixture="approval_request")
def request_approval(
    passed_proposal_and_check: tuple[ExperimentProposal, ScientificSafetyCheck],
) -> ApprovalRequest:
    proposal, check = passed_proposal_and_check
    gate = ApprovalGate()
    request = gate.request_approval(proposal, check)
    # Store gate in request for later steps (attach as attribute)
    request._gate = gate  # type: ignore[attr-defined]
    return request


@then(parsers.parse('an approval request is created with status "{status}"'))
def check_approval_status_created(approval_request: ApprovalRequest, status: str) -> None:
    assert approval_request.status == status, (
        f"Expected status {status!r}, got {approval_request.status!r}"
    )


@when("the PI approves the request", target_fixture="approval_request")
def pi_approves(approval_request: ApprovalRequest) -> ApprovalRequest:
    gate: ApprovalGate = approval_request._gate  # type: ignore[attr-defined]
    approved = gate.approve(approval_request.request_id, approver="pi_zhang")
    approved._gate = gate  # type: ignore[attr-defined]
    return approved


@then(parsers.parse('the approval status is "{status}"'))
def check_approval_status(approval_request: ApprovalRequest, status: str) -> None:
    assert approval_request.status == status, (
        f"Expected status {status!r}, got {approval_request.status!r}"
    )


@when(
    parsers.parse('the PI rejects the request with reason "{reason}"'),
    target_fixture="approval_request",
)
def pi_rejects(approval_request: ApprovalRequest, reason: str) -> ApprovalRequest:
    gate: ApprovalGate = approval_request._gate  # type: ignore[attr-defined]
    rejected = gate.reject(approval_request.request_id, approver="pi_zhang", reason=reason)
    rejected._gate = gate  # type: ignore[attr-defined]
    return rejected
