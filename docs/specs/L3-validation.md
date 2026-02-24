# L3 Validation Spec

**Layer:** Validation (L3 — Engine)
**Design doc reference:** Section 5.5 (Validator)

## Purpose

The validation layer implements the CONCLUDE step of the scientific method loop.
Every finding produced by the Discovery/Optimization layers must survive rigorous
statistical validation before it can be reported. The layer provides:

- Effect sizes, confidence intervals, multiple comparison correction
- Hold-out tests, permutation tests, generalization checks
- Full provenance chain: finding -> analysis -> recording -> session -> subject
- Automated statistical report generation
- Feedback loop: conclusions feed back to Discovery Loop
- Evolution trigger: validation results feed into self-evolution fitness

This layer is stateless — it depends only on Phase 0 foundations (core schemas,
events, graph nodes).

---

## Pydantic Schemas

### StatTestResult

```python
class StatTestResult(BaseModel):
    """Result of a single statistical test."""
    test_name: str                                  # e.g. "t_test", "mann_whitney"
    statistic: float                                # Test statistic value
    p_value: float                                  # Raw p-value from run_test; corrected after apply_correction
    effect_size: float | None = None                # Cohen's d or equivalent
    confidence_interval: tuple[float, float] | None = None
    sample_sizes: dict[str, int]                    # {"group_a": N, "group_b": M}
    significant: bool                               # p < alpha after correction
    correction_method: str | None = None            # "bonferroni", "holm", or None
    warnings: list[str] = []                        # e.g. sample size warnings
```

### ProvenanceStep

```python
class ProvenanceStep(BaseModel):
    """A single step in a provenance chain."""
    node_id: str                                    # Graph node reference
    node_type: str                                  # "subject", "session", etc.
    description: str                                # Human-readable description
    timestamp: datetime                             # When this step was created
```

### ProvenanceChain

```python
class ProvenanceChain(BaseModel):
    """Full traceability from a finding back to raw data."""
    chain_id: str                                   # UUID
    finding_id: str                                 # FindingNode reference
    steps: list[ProvenanceStep]                     # Ordered: subject -> ... -> finding
    created_at: datetime                            # UTC
```

### ValidationReport

```python
class ValidationReport(BaseModel):
    """Complete validation report for a finding."""
    report_id: str                                  # UUID
    finding_id: str                                 # FindingNode reference
    tests: list[StatTestResult]                     # All statistical tests run
    provenance: ProvenanceChain                     # Full provenance chain
    conclusion: HypothesisStatus                    # confirmed / rejected / inconclusive
    confidence: float                               # 0-1 overall confidence
    summary: str                                    # Human-readable summary
    created_at: datetime                            # UTC
```

### ValidationConfig

```python
class ValidationConfig(BaseModel):
    """Configuration for validation thresholds."""
    alpha: float = 0.05                             # Significance threshold
    correction_method: str = "bonferroni"           # Multiple comparison method
    min_effect_size: float = 0.2                    # Minimum Cohen's d
    min_sample_size: int = 5                        # Minimum per-group N
```

---

## Public Interfaces

### StatisticalValidator

Statistical testing engine. Supports parametric and non-parametric tests with
multiple comparison correction.

```python
class StatisticalValidator:
    def run_test(
        self,
        test_name: str,
        group_a: list[float],
        group_b: list[float],
        config: ValidationConfig | None = None,
    ) -> StatTestResult:
        """Run a named statistical test on two groups.

        Supported tests: "t_test", "mann_whitney", "permutation".
        Computes effect size (Cohen's d) for t-tests.
        Warns if sample size < config.min_sample_size.
        """

    def apply_correction(
        self,
        results: list[StatTestResult],
        method: str = "bonferroni",
    ) -> list[StatTestResult]:
        """Apply multiple comparison correction to a list of test results.

        Supported methods: "bonferroni", "holm".
        Returns a new StatTestResult list with corrected p-values/significance,
        preserving the original input order.
        """

    def validate_finding(
        self,
        finding_id: str,
        tests: list[StatTestResult],
        provenance: ProvenanceChain,
        config: ValidationConfig | None = None,
    ) -> ValidationReport:
        """Generate a full ValidationReport for a finding.

        Applies correction, determines conclusion (HypothesisStatus),
        computes confidence score, and emits validation.report.generated event.
        """
```

### ProvenanceTracker

Builds and verifies provenance chains from graph nodes.

```python
class ProvenanceTracker:
    def build_chain(
        self,
        finding_id: str,
        steps: list[ProvenanceStep],
    ) -> ProvenanceChain:
        """Build a provenance chain for a finding.

        Emits validation.provenance.built event.
        """

    def verify_chain(self, chain: ProvenanceChain) -> bool:
        """Verify that a provenance chain is valid.

        Checks: non-empty steps, all steps have node_id and node_type,
        chain has a valid finding_id.
        """
```

---

## Events

| Event Name | Payload | Emitted By |
|---|---|---|
| `validation.test.completed` | `{test_name, p_value, significant}` | StatisticalValidator.run_test() |
| `validation.report.generated` | `{report_id, finding_id, conclusion}` | StatisticalValidator.validate_finding() |
| `validation.provenance.built` | `{chain_id, finding_id, step_count}` | ProvenanceTracker.build_chain() |

---

## Boundary Contracts

- All IDs are UUIDs (auto-generated by default)
- All timestamps are timezone-aware UTC
- Pydantic models validate at boundary (test submission, report generation)
- Events follow `{layer}.{module}.{action}` naming convention
- HypothesisStatus uses `core.schemas.HypothesisStatus` enum
- scipy is optional — imported with `try/except ImportError` and graceful fallback
- numpy int64/float64 are cast to native Python types before serialization
- Holm correction uses step-down adjustment with monotonic corrected p-values:
  sort by p ascending, compute `min(p * (n - rank), 1.0)`, then apply a running max.
- Corrected Holm results are mapped back to original test order before returning.
- `significant` is evaluated from corrected `p_value` and `alpha` (`p_value < alpha`).

## Error Conditions

| Condition | Exception | Raised By |
|---|---|---|
| Unknown test name | `ValueError` | StatisticalValidator.run_test() |
| Empty group data | `ValueError` | StatisticalValidator.run_test() |
| Unknown correction method | `ValueError` | StatisticalValidator.apply_correction() |
| Empty provenance steps | `ValueError` | ProvenanceTracker.build_chain() |
| Invalid chain (no steps / missing IDs) | Returns `False` | ProvenanceTracker.verify_chain() |

## Storage

- MVP: stateless — results returned directly, no persistence
- Reports are Pydantic models, serializable to JSON for storage
- Future: SQLite persistence for audit trail

## Acceptance Criteria

- [ ] StatTestResult correctly stores test outcomes with effect sizes
- [ ] StatisticalValidator.run_test supports t_test, mann_whitney, permutation
- [ ] Cohen's d is computed for t-tests
- [ ] Bonferroni and Holm correction methods work correctly
- [ ] ProvenanceTracker builds and verifies chains
- [ ] ValidationReport combines stats + provenance with conclusion
- [ ] Sample size warnings are generated when N < min_sample_size
- [ ] Events are emitted: validation.test.completed, validation.report.generated, validation.provenance.built
- [ ] All schemas importable from `jarvis_mesh.validation`
- [ ] All BDD scenarios pass
