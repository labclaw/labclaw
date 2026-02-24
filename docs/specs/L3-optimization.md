# L3 Optimization Spec

**Layer:** Optimization (L3 — Engine)
**Design doc reference:** Section 5.4 (Conductor), Section 9.3 (Two-Layer Safety)

## Purpose

The optimization layer implements the EXPERIMENT step of the scientific method loop.
Instead of fixed experimental designs, it adapts parameters based on accumulating
evidence via Bayesian optimization. The layer provides:

- Bayesian optimization of experimental parameters within defined bounds
- Two-layer safety: scientific safety (parameter range, animal welfare) + hardware safety (device state)
- Human-in-the-loop approval gate before experiment execution
- Full audit trail of proposals, safety checks, and approval decisions
- Feedback loop: optimization results feed back into the optimizer

This layer depends on Phase 0 foundations (core schemas, events) and L1 hardware
(SafetyCheckResult for hardware safety).

---

## Pydantic Schemas

### ParameterDimension

```python
class ParameterDimension(BaseModel):
    """A single dimension in the parameter search space."""
    name: str                                       # e.g. "temperature", "duration"
    low: float                                      # Lower bound (inclusive)
    high: float                                     # Upper bound (inclusive)
    prior: str = "uniform"                          # Prior distribution
```

### ParameterSpace

```python
class ParameterSpace(BaseModel):
    """Definition of the experimental parameter search space."""
    name: str                                       # Human-readable name
    dimensions: list[ParameterDimension]            # Parameter dimensions
```

### ExperimentProposal

```python
class ExperimentProposal(BaseModel):
    """A proposed set of experimental parameters."""
    proposal_id: str                                # UUID
    parameters: dict[str, float]                    # Proposed parameter values
    expected_improvement: float                     # Expected improvement score
    iteration: int                                  # Optimization iteration number
    timestamp: datetime                             # UTC
```

### SafetyCheckDetail

```python
class SafetyCheckDetail(BaseModel):
    """Result of a single safety constraint check."""
    name: str                                       # Constraint name
    passed: bool                                    # Whether the check passed
    message: str                                    # Human-readable result
```

### ScientificSafetyCheck

```python
class ScientificSafetyCheck(BaseModel):
    """Result of scientific safety validation for a proposal."""
    proposal_id: str                                # Reference to ExperimentProposal
    passed: bool                                    # Overall pass/fail
    level: SafetyLevel                              # SAFE, CAUTION, REQUIRES_APPROVAL, BLOCKED
    checks: list[SafetyCheckDetail]                 # Individual constraint results
    checked_at: datetime                            # UTC
```

### ApprovalRequest

```python
class ApprovalRequest(BaseModel):
    """Human approval request for experiment execution."""
    request_id: str                                 # UUID
    proposal: ExperimentProposal                    # The proposed experiment
    scientific_safety: ScientificSafetyCheck        # Scientific safety result
    hardware_safety: SafetyCheckResult | None       # Hardware safety result (optional)
    status: str                                     # "pending" | "approved" | "rejected"
    requested_at: datetime                          # UTC
    decided_at: datetime | None = None              # When decision was made
    decided_by: str | None = None                   # Who decided
    rejection_reason: str | None = None             # Reason if rejected
```

### SafetyConstraint

```python
class SafetyConstraint(BaseModel):
    """A scientific safety constraint on a parameter."""
    parameter: str                                  # Parameter name
    min_value: float | None = None                  # Minimum allowed value
    max_value: float | None = None                  # Maximum allowed value
    description: str = ""                           # Human-readable explanation
```

### OptimizationResult

```python
class OptimizationResult(BaseModel):
    """Result of an executed experiment."""
    iteration: int                                  # Iteration number
    parameters: dict[str, float]                    # Parameters used
    objective_value: float                          # Measured objective
    timestamp: datetime                             # UTC
```

---

## Public Interfaces

### BayesianOptimizer

Bayesian optimization engine for experimental parameters. MVP uses random sampling
within parameter bounds; future versions will use GP-based optimization.

```python
class BayesianOptimizer:
    def __init__(self, space: ParameterSpace) -> None:
        """Initialize with a parameter search space."""

    def suggest(self, n: int = 1) -> list[ExperimentProposal]:
        """Suggest n experimental parameter sets.

        MVP: random sampling within parameter bounds.
        Returns list of ExperimentProposal with unique IDs.
        Emits optimization.proposal.created event for each proposal.
        """

    def tell(self, result: OptimizationResult) -> None:
        """Record an optimization result.

        Stores the result for history tracking and future optimization.
        Emits optimization.result.recorded event.
        """

    def get_best(self) -> OptimizationResult | None:
        """Return the result with the highest objective value, or None."""

    def get_history(self) -> list[OptimizationResult]:
        """Return all recorded results in order."""
```

### ScientificSafetyValidator

Validates proposed parameters against scientific safety constraints (animal welfare,
parameter ranges, protocol compliance).

```python
class ScientificSafetyValidator:
    def validate(
        self,
        proposal: ExperimentProposal,
        constraints: list[SafetyConstraint],
    ) -> ScientificSafetyCheck:
        """Validate a proposal against safety constraints.

        Each parameter is checked against min_value/max_value bounds.
        Any violation -> SafetyLevel.BLOCKED.
        All pass -> SafetyLevel.SAFE.
        Emits optimization.safety.checked event.
        """
```

### ApprovalGate

Human-in-the-loop approval workflow. Proposals that pass scientific safety
are submitted for human review before execution.

```python
class ApprovalGate:
    def request_approval(
        self,
        proposal: ExperimentProposal,
        scientific_check: ScientificSafetyCheck,
    ) -> ApprovalRequest:
        """Create an approval request with status "pending".

        Emits optimization.approval.requested event.
        """

    def approve(self, request_id: str, approver: str) -> ApprovalRequest:
        """Approve a pending request.

        Sets status to "approved", records approver and timestamp.
        Emits optimization.approval.decided event.
        """

    def reject(
        self, request_id: str, approver: str, reason: str
    ) -> ApprovalRequest:
        """Reject a pending request with reason.

        Sets status to "rejected", records approver, reason, and timestamp.
        Emits optimization.approval.decided event.
        """

    def get_pending(self) -> list[ApprovalRequest]:
        """Return all requests with status "pending"."""
```

### ExperimentPipeline

Coordinator that orchestrates the full propose-validate-approve workflow.

```python
class ExperimentPipeline:
    def __init__(
        self,
        optimizer: BayesianOptimizer,
        safety_validator: ScientificSafetyValidator,
        approval_gate: ApprovalGate,
    ) -> None:
        """Initialize with optimizer, safety validator, and approval gate."""

    def propose_and_validate(
        self,
        constraints: list[SafetyConstraint],
    ) -> ApprovalRequest:
        """Suggest one experiment, validate safety, and request approval.

        1. optimizer.suggest(1) -> proposal
        2. safety_validator.validate(proposal, constraints) -> safety check
        3. approval_gate.request_approval(proposal, safety) -> approval request
        Returns the ApprovalRequest (status: "pending").
        """
```

---

## Events

| Event Name | Payload | Emitted By |
|---|---|---|
| `optimization.proposal.created` | `{proposal_id, parameters, iteration}` | BayesianOptimizer.suggest() |
| `optimization.safety.checked` | `{proposal_id, passed, level}` | ScientificSafetyValidator.validate() |
| `optimization.approval.requested` | `{request_id, proposal_id, status}` | ApprovalGate.request_approval() |
| `optimization.approval.decided` | `{request_id, status, decided_by}` | ApprovalGate.approve() / reject() |
| `optimization.result.recorded` | `{iteration, objective_value}` | BayesianOptimizer.tell() |

---

## Boundary Contracts

- All IDs are UUIDs (auto-generated by default)
- All timestamps are timezone-aware UTC
- Pydantic models validate at boundary (proposal creation, safety check, approval)
- Events follow `{layer}.{module}.{action}` naming convention
- SafetyLevel uses `core.schemas.SafetyLevel` enum
- SafetyCheckResult uses `hardware.schemas.SafetyCheckResult` for hardware safety
- No scikit-optimize dependency for MVP — pure random sampling within bounds

## Error Conditions

| Condition | Exception | Raised By |
|---|---|---|
| Empty parameter space | `ValueError` | BayesianOptimizer.__init__() |
| Request n <= 0 suggestions | `ValueError` | BayesianOptimizer.suggest() |
| Unknown request_id | `KeyError` | ApprovalGate.approve() / reject() |
| Request not in pending state | `ValueError` | ApprovalGate.approve() / reject() |

## Storage

- MVP: in-memory — results and approval requests stored in lists/dicts
- All models are Pydantic, serializable to JSON for future persistence
- Future: SQLite persistence for audit trail

## Acceptance Criteria

- [ ] ParameterSpace and ParameterDimension correctly define search space
- [ ] BayesianOptimizer.suggest() returns proposals within parameter bounds
- [ ] BayesianOptimizer.tell() records results and tracks best
- [ ] ScientificSafetyValidator checks parameter bounds, blocks violations
- [ ] ApprovalGate manages pending/approved/rejected workflow
- [ ] ExperimentPipeline coordinates propose-validate-approve flow
- [ ] Events are emitted: optimization.proposal.created, optimization.safety.checked, optimization.approval.requested, optimization.approval.decided, optimization.result.recorded
- [ ] All schemas importable from `jarvis_mesh.optimization`
- [ ] All BDD scenarios pass
