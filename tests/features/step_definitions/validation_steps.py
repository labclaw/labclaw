"""BDD step definitions for L3 Validation (CONCLUDE).

Spec: docs/specs/L3-validation.md
Uses conftest fixtures: event_capture
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pytest_bdd import given, parsers, then, when

from labclaw.core.events import event_registry
from labclaw.validation.provenance import ProvenanceTracker
from labclaw.validation.statistics import (
    ProvenanceChain,
    ProvenanceStep,
    StatisticalValidator,
    StatTestResult,
    ValidationConfig,
    ValidationReport,
)

# ---------------------------------------------------------------------------
# Background
# ---------------------------------------------------------------------------


@given("the statistical validator is initialized", target_fixture="validator")
def stat_validator_initialized(event_capture: object) -> StatisticalValidator:
    """Provide a StatisticalValidator and subscribe event capture."""
    for evt_name in [
        "validation.test.completed",
        "validation.report.generated",
        "validation.provenance.built",
    ]:
        event_registry.subscribe(evt_name, event_capture)  # type: ignore[arg-type]
    return StatisticalValidator()


@given("the provenance tracker is initialized", target_fixture="tracker")
def provenance_tracker_initialized() -> ProvenanceTracker:
    return ProvenanceTracker()


# ---------------------------------------------------------------------------
# Group data
# ---------------------------------------------------------------------------


@given(
    parsers.parse("group A has values [{values}]"),
    target_fixture="group_a",
)
def group_a_values(values: str) -> list[float]:
    return [float(v.strip()) for v in values.split(",")]


@given(
    parsers.parse("group B has values [{values}]"),
    target_fixture="group_b",
)
def group_b_values(values: str) -> list[float]:
    return [float(v.strip()) for v in values.split(",")]


# ---------------------------------------------------------------------------
# Run test
# ---------------------------------------------------------------------------


@when(
    parsers.parse('I run a "{test_name}" on both groups'),
    target_fixture="test_result",
)
def run_test(
    validator: StatisticalValidator,
    test_name: str,
    group_a: list[float],
    group_b: list[float],
) -> StatTestResult:
    return validator.run_test(test_name, group_a, group_b)


@when(
    parsers.parse('I run a "{test_name}" on both groups with min_sample_size {min_size:d}'),
    target_fixture="test_result",
)
def run_test_with_min_sample(
    validator: StatisticalValidator,
    test_name: str,
    group_a: list[float],
    group_b: list[float],
    min_size: int,
) -> StatTestResult:
    config = ValidationConfig(min_sample_size=min_size)
    return validator.run_test(test_name, group_a, group_b, config=config)


# ---------------------------------------------------------------------------
# Test result assertions
# ---------------------------------------------------------------------------


@then("the test result has a p-value less than 0.05")
def check_p_value(test_result: StatTestResult) -> None:
    assert test_result.p_value < 0.05, f"p-value {test_result.p_value} >= 0.05"


@then("the test is significant")
def check_significant(test_result: StatTestResult) -> None:
    assert test_result.significant, "Test result is not significant"


@then("the effect size is calculated")
def check_effect_size(test_result: StatTestResult) -> None:
    assert test_result.effect_size is not None, "Effect size is None"
    assert test_result.effect_size != 0.0, "Effect size is zero"


@then("the result includes a sample size warning")
def check_sample_size_warning(test_result: StatTestResult) -> None:
    assert test_result.warnings, "No warnings found"
    assert any("sample size" in w.lower() or "Sample size" in w for w in test_result.warnings), (
        f"No sample size warning in: {test_result.warnings}"
    )


# ---------------------------------------------------------------------------
# Correction
# ---------------------------------------------------------------------------


@given(
    parsers.parse("I have {count:d} test results with p-values [{pvals}]"),
    target_fixture="raw_results",
)
def create_raw_results(count: int, pvals: str) -> list[StatTestResult]:
    p_values = [float(v.strip()) for v in pvals.split(",")]
    assert len(p_values) == count
    results = []
    for i, p in enumerate(p_values):
        results.append(
            StatTestResult(
                test_name=f"test_{i}",
                statistic=2.0,
                p_value=p,
                sample_sizes={"group_a": 10, "group_b": 10},
                significant=p < 0.05,
            )
        )
    return results


@when(
    parsers.parse('I apply "{method}" correction'),
    target_fixture="corrected_results",
)
def apply_correction(
    validator: StatisticalValidator,
    raw_results: list[StatTestResult],
    method: str,
) -> list[StatTestResult]:
    return validator.apply_correction(raw_results, method)


@then(parsers.parse("the corrected p-values are [{expected}]"))
def check_corrected_pvalues(corrected_results: list[StatTestResult], expected: str) -> None:
    expected_vals = [float(v.strip()) for v in expected.split(",")]
    actual_vals = [r.p_value for r in corrected_results]
    for actual, exp in zip(actual_vals, expected_vals):
        assert abs(actual - exp) < 1e-9, f"Expected p-values {expected_vals}, got {actual_vals}"


@then(parsers.parse("only {count:d} result remains significant at alpha 0.05"))
def check_significant_count(corrected_results: list[StatTestResult], count: int) -> None:
    sig = sum(1 for r in corrected_results if r.significant)
    assert sig == count, f"Expected {count} significant, got {sig}"


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------


@when(
    parsers.parse('I build a provenance chain for finding "{finding_id}" with steps:'),
    target_fixture="built_chain",
)
def build_chain(tracker: ProvenanceTracker, finding_id: str, datatable: list) -> ProvenanceChain:
    # pytest-bdd passes datatable as list[list[str]]; first row is header
    headers = [str(c) for c in datatable[0]]
    rows = [{headers[i]: str(cell) for i, cell in enumerate(row)} for row in datatable[1:]]

    steps = []
    for row in rows:
        steps.append(
            ProvenanceStep(
                node_id=str(uuid.uuid4()),
                node_type=row["node_type"],
                description=row["description"],
                timestamp=datetime.now(UTC),
            )
        )
    return tracker.build_chain(finding_id, steps)


@then(parsers.parse("the chain has {count:d} steps"))
def check_chain_step_count(built_chain: ProvenanceChain, count: int) -> None:
    assert len(built_chain.steps) == count, f"Expected {count} steps, got {len(built_chain.steps)}"


@then("the chain is verified as valid")
def check_chain_valid(tracker: ProvenanceTracker, built_chain: ProvenanceChain) -> None:
    assert tracker.verify_chain(built_chain), "Chain verification failed"


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


@given("a completed t-test result", target_fixture="completed_test")
def completed_test_result(validator: StatisticalValidator) -> StatTestResult:
    return validator.run_test(
        "t_test",
        [10.1, 10.5, 9.8, 10.3, 10.0],
        [12.1, 12.5, 11.8, 12.3, 12.0],
    )


@given(
    parsers.parse('a provenance chain for finding "{finding_id}"'),
    target_fixture="report_chain",
)
def provenance_chain_for_finding(tracker: ProvenanceTracker, finding_id: str) -> ProvenanceChain:
    steps = [
        ProvenanceStep(
            node_id=str(uuid.uuid4()),
            node_type="subject",
            description="Test subject",
            timestamp=datetime.now(UTC),
        ),
        ProvenanceStep(
            node_id=str(uuid.uuid4()),
            node_type="finding",
            description="Test finding",
            timestamp=datetime.now(UTC),
        ),
    ]
    return tracker.build_chain(finding_id, steps)


@when("I generate a validation report", target_fixture="report")
def generate_report(
    validator: StatisticalValidator,
    completed_test: StatTestResult,
    report_chain: ProvenanceChain,
) -> ValidationReport:
    return validator.validate_finding(
        finding_id=report_chain.finding_id,
        tests=[completed_test],
        provenance=report_chain,
    )


@then("the report contains the test results")
def check_report_has_tests(report: ValidationReport) -> None:
    assert report.tests, "Report has no test results"
    assert len(report.tests) >= 1


@then("the report contains the provenance chain")
def check_report_has_provenance(report: ValidationReport) -> None:
    assert report.provenance is not None
    assert report.provenance.steps


@then("the report has a conclusion status")
def check_report_conclusion(report: ValidationReport) -> None:
    from labclaw.core.schemas import HypothesisStatus

    assert report.conclusion in list(HypothesisStatus), f"Invalid conclusion: {report.conclusion}"
