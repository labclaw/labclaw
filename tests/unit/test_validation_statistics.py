from __future__ import annotations

import pytest

from labclaw.validation.statistics import StatisticalValidator, StatTestResult


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
