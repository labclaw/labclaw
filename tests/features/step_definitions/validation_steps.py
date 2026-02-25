"""BDD step definitions for L3 Validation (CONCLUDE).

Spec: docs/specs/L3-validation.md
Uses conftest fixtures: event_capture
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pytest_bdd import given, parsers, then, when

from labclaw.core.events import event_registry
from labclaw.validation.cross_validation import holdout_validate, kfold_validate, permutation_test
from labclaw.validation.provenance import ProvenanceTracker, from_dict, to_dict
from labclaw.validation.report import to_markdown
from labclaw.validation.statistics import (
    ProvenanceChain,
    ProvenanceStep,
    StatisticalValidator,
    StatTestResult,
    ValidationConfig,
    ValidationReport,
    _cohens_d,
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
    stripped = values.strip()
    if not stripped:
        return []
    return [float(v.strip()) for v in stripped.split(",")]


@given("group A is empty", target_fixture="group_a")
def group_a_empty() -> list[float]:
    return []


@given(
    parsers.parse("group B has values [{values}]"),
    target_fixture="group_b",
)
def group_b_values(values: str) -> list[float]:
    stripped = values.strip()
    if not stripped:
        return []
    return [float(v.strip()) for v in stripped.split(",")]


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


@when(
    parsers.parse('I run an unknown test "{test_name}"'),
    target_fixture="unknown_test_error",
)
def run_unknown_test(
    validator: StatisticalValidator,
    test_name: str,
    group_a: list[float],
    group_b: list[float],
) -> Exception | None:
    try:
        validator.run_test(test_name, group_a, group_b)
        return None
    except ValueError as exc:
        return exc


@when("I run a t-test with empty group", target_fixture="empty_group_error")
def run_empty_group_test(
    validator: StatisticalValidator,
    group_a: list[float],
    group_b: list[float],
) -> Exception | None:
    try:
        validator.run_test("t_test", group_a, group_b)
        return None
    except ValueError as exc:
        return exc


# ---------------------------------------------------------------------------
# Test result assertions
# ---------------------------------------------------------------------------


@then("the test result has a p-value less than 0.05")
def check_p_value(test_result: StatTestResult) -> None:
    assert test_result.p_value < 0.05, f"p-value {test_result.p_value} >= 0.05"


@then("the test is significant")
def check_significant(test_result: StatTestResult) -> None:
    assert test_result.significant, "Test result is not significant"


@then("the test is not significant")
def check_not_significant(test_result: StatTestResult) -> None:
    assert not test_result.significant, (
        f"Expected non-significant result, but p={test_result.p_value}"
    )


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


@then("the permutation p-value is close to 1.0")
def check_permutation_high_pval(test_result: StatTestResult) -> None:
    assert test_result.p_value >= 0.8, (
        f"Expected permutation p-value close to 1.0, got {test_result.p_value}"
    )


@then("a ValueError is raised for unknown test")
def check_value_error_unknown_test(unknown_test_error: Exception | None) -> None:
    assert unknown_test_error is not None, "Expected ValueError but none raised"
    assert isinstance(unknown_test_error, ValueError)


@then("a ValueError is raised for empty group")
def check_value_error_empty_group(empty_group_error: Exception | None) -> None:
    assert empty_group_error is not None, "Expected ValueError but none raised"
    assert isinstance(empty_group_error, ValueError)


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


@when("I try to build a chain with empty steps", target_fixture="empty_steps_error")
def build_chain_empty_steps(tracker: ProvenanceTracker) -> Exception | None:
    try:
        tracker.build_chain("finding-x", [])
        return None
    except ValueError as exc:
        return exc


@then("a ValueError is raised for empty steps")
def check_value_error_empty_steps(empty_steps_error: Exception | None) -> None:
    assert empty_steps_error is not None, "Expected ValueError but none raised"
    assert isinstance(empty_steps_error, ValueError)


@when("I build a chain with empty finding_id", target_fixture="bad_chain")
def build_chain_empty_finding(tracker: ProvenanceTracker) -> ProvenanceChain:
    step = ProvenanceStep(
        node_id=str(uuid.uuid4()),
        node_type="subject",
        description="test",
        timestamp=datetime.now(UTC),
    )
    # Bypass validation by building directly
    return ProvenanceChain(finding_id="", steps=[step])


@then("the chain verification returns false")
def check_chain_verify_false(tracker: ProvenanceTracker, bad_chain: ProvenanceChain) -> None:
    assert tracker.verify_chain(bad_chain) is False


@when("I build a chain with a step missing node_id", target_fixture="bad_chain")
def build_chain_missing_node_id(tracker: ProvenanceTracker) -> ProvenanceChain:
    # Bypass Pydantic by directly constructing with empty node_id
    step = ProvenanceStep(
        node_id="",
        node_type="subject",
        description="test",
        timestamp=datetime.now(UTC),
    )
    return ProvenanceChain(finding_id="finding-test", steps=[step])


@when("I build a chain with a step missing node_type", target_fixture="bad_chain")
def build_chain_missing_node_type(tracker: ProvenanceTracker) -> ProvenanceChain:
    step = ProvenanceStep(
        node_id=str(uuid.uuid4()),
        node_type="",
        description="test",
        timestamp=datetime.now(UTC),
    )
    return ProvenanceChain(finding_id="finding-test", steps=[step])


@when("I serialize and deserialize the chain", target_fixture="round_tripped_chain")
def serialize_deserialize_chain(report_chain: ProvenanceChain) -> ProvenanceChain:
    d = to_dict(report_chain)
    return from_dict(d)


@then("the round-tripped chain matches the original")
def check_round_trip(
    report_chain: ProvenanceChain, round_tripped_chain: ProvenanceChain
) -> None:
    assert round_tripped_chain.finding_id == report_chain.finding_id
    assert len(round_tripped_chain.steps) == len(report_chain.steps)
    assert round_tripped_chain.chain_id == report_chain.chain_id


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


@when("I validate a finding with t_test and permutation tests", target_fixture="report")
def validate_finding_multi(
    validator: StatisticalValidator,
    tracker: ProvenanceTracker,
    group_a: list[float],
    group_b: list[float],
) -> ValidationReport:
    t_result = validator.run_test("t_test", group_a, group_b)
    perm_result = validator.run_test("permutation", group_a, group_b)
    steps = [
        ProvenanceStep(
            node_id=str(uuid.uuid4()),
            node_type="finding",
            description="Multi-test finding",
            timestamp=datetime.now(UTC),
        )
    ]
    chain = tracker.build_chain("multi-find-001", steps)
    return validator.validate_finding(
        finding_id="multi-find-001",
        tests=[t_result, perm_result],
        provenance=chain,
    )


@then(parsers.parse("the validation report has {n:d} tests"))
def check_report_test_count(report: ValidationReport, n: int) -> None:
    assert len(report.tests) == n, f"Expected {n} tests, got {len(report.tests)}"


@then("the report conclusion is not empty")
def check_report_conclusion_not_empty(report: ValidationReport) -> None:
    assert report.conclusion is not None
    assert report.conclusion.value


@when("I convert the report to markdown", target_fixture="markdown_output")
def convert_to_markdown(report: ValidationReport) -> str:
    return to_markdown(report)


@then(parsers.parse('the markdown contains "{section}"'))
def check_markdown_contains(markdown_output: str, section: str) -> None:
    assert section in markdown_output, (
        f"Expected {section!r} in markdown. Got:\n{markdown_output[:500]}"
    )


@when("I compute cohens d with identical groups", target_fixture="cohens_d_value")
def compute_cohens_d_identical() -> float:
    return _cohens_d([5.0, 5.0, 5.0], [5.0, 5.0, 5.0])


@then("cohens d is 0.0")
def check_cohens_d_zero(cohens_d_value: float) -> None:
    assert cohens_d_value == 0.0, f"Expected 0.0, got {cohens_d_value}"


# ---------------------------------------------------------------------------
# Cross-validation
# ---------------------------------------------------------------------------


@when(
    parsers.parse("I run holdout validation on {n:d} data points"),
    target_fixture="holdout_result",
)
def run_holdout(n: int) -> dict[str, float]:
    data = [float(i) for i in range(n)]
    return holdout_validate(data, train_fraction=0.8, seed=42)


@then("the holdout result has train_mean and test_mean and mae")
def check_holdout_result(holdout_result: dict[str, float]) -> None:
    assert "train_mean" in holdout_result
    assert "test_mean" in holdout_result
    assert "mae" in holdout_result
    assert holdout_result["mae"] >= 0.0


@when(
    parsers.parse("I run kfold validation on {n:d} data points with k={k:d}"),
    target_fixture="kfold_result",
)
def run_kfold(n: int, k: int) -> dict[str, Any]:
    data = [float(i) for i in range(n)]
    return kfold_validate(data, k=k, seed=42)


@then(parsers.parse("the kfold result has {k:d} fold_maes"))
def check_kfold_folds(kfold_result: dict[str, Any], k: int) -> None:
    assert len(kfold_result["fold_maes"]) == k, (
        f"Expected {k} fold MAEs, got {len(kfold_result['fold_maes'])}"
    )


@then("the mean_mae is non-negative")
def check_mean_mae(kfold_result: dict[str, Any]) -> None:
    assert kfold_result["mean_mae"] >= 0.0, f"mean_mae is negative: {kfold_result['mean_mae']}"


@when("I run cv permutation test with identical groups", target_fixture="cv_perm_result")
def run_cv_permutation_identical() -> dict[str, float | int]:
    group = [5.0, 5.0, 5.0, 5.0, 5.0]
    return permutation_test(group, group, n_perms=1000, seed=42)


@then(parsers.parse("the cv permutation p-value is at least {threshold:g}"))
def check_cv_permutation_pval(cv_perm_result: dict[str, float | int], threshold: float) -> None:
    pval = float(cv_perm_result["p_value"])
    assert pval >= threshold, f"CV permutation p-value {pval} < {threshold}"
