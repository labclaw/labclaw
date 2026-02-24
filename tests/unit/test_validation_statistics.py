from __future__ import annotations

import pytest

from labclaw.core.schemas import HypothesisStatus
from labclaw.validation.statistics import (
    ProvenanceChain,
    ProvenanceStep,
    StatisticalValidator,
    StatTestResult,
    ValidationConfig,
    _cohens_d,
    _mean,
)


def _build_results(p_values: list[float]) -> list[StatTestResult]:
    return [
        StatTestResult(
            test_name=f"test_{idx}",
            statistic=1.0,
            p_value=p_value,
            sample_sizes={"group_a": 10, "group_b": 10},
            significant=p_value < 0.05,
        )
        for idx, p_value in enumerate(p_values)
    ]


@pytest.mark.parametrize(
    ("p_values", "expected_p_values", "expected_significant"),
    [
        ([0.01, 0.04, 0.045], [0.03, 0.08, 0.08], [True, False, False]),
        ([0.01, 0.03, 0.04], [0.03, 0.06, 0.06], [True, False, False]),
    ],
)
def test_holm_step_down_is_monotonic_and_updates_significance(
    p_values: list[float],
    expected_p_values: list[float],
    expected_significant: list[bool],
) -> None:
    validator = StatisticalValidator()
    corrected = validator.apply_correction(_build_results(p_values), method="holm", alpha=0.05)

    assert [result.p_value for result in corrected] == pytest.approx(expected_p_values)
    assert [result.significant for result in corrected] == expected_significant


def test_holm_preserves_original_order_in_output() -> None:
    validator = StatisticalValidator()
    corrected = validator.apply_correction(
        _build_results([0.04, 0.01, 0.045]), method="holm", alpha=0.05
    )

    assert [result.test_name for result in corrected] == ["test_0", "test_1", "test_2"]
    assert [result.p_value for result in corrected] == pytest.approx([0.08, 0.03, 0.08])
    assert [result.significant for result in corrected] == [False, True, False]


# ---------------------------------------------------------------------------
# Helpers for new tests
# ---------------------------------------------------------------------------


def _make_chain(finding_id: str = "find-001") -> ProvenanceChain:
    return ProvenanceChain(
        finding_id=finding_id,
        steps=[
            ProvenanceStep(
                node_id="node-1",
                node_type="DataNode",
                description="raw data",
            )
        ],
    )


# ---------------------------------------------------------------------------
# run_test
# ---------------------------------------------------------------------------


def test_run_test_t_test_significant() -> None:
    v = StatisticalValidator()
    result = v.run_test("t_test", [10, 11, 12, 13, 14], [1, 2, 3, 4, 5])

    assert result.significant is True
    assert result.test_name == "t_test"


def test_run_test_mann_whitney_significant() -> None:
    v = StatisticalValidator()
    result = v.run_test("mann_whitney", [10, 11, 12, 13, 14], [1, 2, 3, 4, 5])

    assert result.significant is True


def test_run_test_permutation_significant() -> None:
    v = StatisticalValidator()
    result = v.run_test("permutation", [0.0] * 20, [10.0] * 20)

    assert result.significant is True


def test_run_test_unknown_raises() -> None:
    v = StatisticalValidator()
    with pytest.raises(ValueError, match="Unknown test"):
        v.run_test("chi_square", [1.0, 2.0], [3.0, 4.0])


def test_run_test_empty_groups_raises() -> None:
    v = StatisticalValidator()
    with pytest.raises(ValueError, match="non-empty"):
        v.run_test("t_test", [], [1.0, 2.0])


def test_run_test_small_sample_warning() -> None:
    v = StatisticalValidator()
    cfg = ValidationConfig(min_sample_size=5)
    result = v.run_test("permutation", [1.0, 2.0, 3.0], [4.0, 5.0, 6.0], config=cfg)

    assert len(result.warnings) > 0


# ---------------------------------------------------------------------------
# Bonferroni correction
# ---------------------------------------------------------------------------


def test_bonferroni_single_test_p_unchanged() -> None:
    v = StatisticalValidator()
    results = _build_results([0.03])
    corrected = v.apply_correction(results, method="bonferroni", alpha=0.05)

    assert corrected[0].p_value == pytest.approx(0.03)


def test_bonferroni_three_tests_p_multiplied() -> None:
    v = StatisticalValidator()
    results = _build_results([0.01, 0.01, 0.01])
    corrected = v.apply_correction(results, method="bonferroni", alpha=0.05)

    for r in corrected:
        assert r.p_value == pytest.approx(0.03)


# ---------------------------------------------------------------------------
# validate_finding
# ---------------------------------------------------------------------------


def test_validate_finding_single_significant_test_confirmed() -> None:
    v = StatisticalValidator()
    tests = _build_results([0.01])
    report = v.validate_finding("find-sig", tests, _make_chain("find-sig"))

    assert report.conclusion == HypothesisStatus.CONFIRMED


def test_validate_finding_multiple_mixed_inconclusive() -> None:
    v = StatisticalValidator()
    tests = _build_results([0.01, 0.5])
    report = v.validate_finding("find-mix", tests, _make_chain("find-mix"))

    assert report.conclusion == HypothesisStatus.INCONCLUSIVE


# ---------------------------------------------------------------------------
# _determine_conclusion
# ---------------------------------------------------------------------------


def test_determine_conclusion_all_significant_confirmed() -> None:
    tests = _build_results([0.01, 0.02])
    conclusion = StatisticalValidator._determine_conclusion(tests, ValidationConfig())

    assert conclusion == HypothesisStatus.CONFIRMED


def test_determine_conclusion_none_significant_rejected() -> None:
    tests = _build_results([0.1, 0.9])
    conclusion = StatisticalValidator._determine_conclusion(tests, ValidationConfig())

    assert conclusion == HypothesisStatus.REJECTED


def test_determine_conclusion_empty_inconclusive() -> None:
    conclusion = StatisticalValidator._determine_conclusion([], ValidationConfig())

    assert conclusion == HypothesisStatus.INCONCLUSIVE


# ---------------------------------------------------------------------------
# _cohens_d and _mean
# ---------------------------------------------------------------------------


def test_cohens_d_zero_std_returns_zero() -> None:
    result = _cohens_d([5.0, 5.0, 5.0], [5.0, 5.0, 5.0])

    assert result == 0.0


def test_mean_empty_returns_zero() -> None:
    assert _mean([]) == 0.0
