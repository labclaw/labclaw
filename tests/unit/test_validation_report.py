from __future__ import annotations

from labclaw.core.schemas import HypothesisStatus
from labclaw.validation.report import ReportGenerator, to_markdown
from labclaw.validation.statistics import (
    ProvenanceChain,
    ProvenanceStep,
    StatTestResult,
    ValidationReport,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_test_result(name: str = "t_test", p: float = 0.01) -> StatTestResult:
    return StatTestResult(
        test_name=name,
        statistic=3.5,
        p_value=p,
        sample_sizes={"group_a": 10, "group_b": 10},
        significant=p < 0.05,
    )


def _make_chain(finding_id: str = "find-001") -> ProvenanceChain:
    return ProvenanceChain(
        finding_id=finding_id,
        steps=[
            ProvenanceStep(
                node_id="raw-001",
                node_type="RawDataNode",
                description="Raw calcium imaging data",
            )
        ],
    )


# ---------------------------------------------------------------------------
# ReportGenerator.generate
# ---------------------------------------------------------------------------


def test_generate_returns_validation_report_with_correct_finding_id() -> None:
    gen = ReportGenerator()
    chain = _make_chain("hyp-42")
    report = gen.generate(
        finding_id="hyp-42",
        tests=[_make_test_result()],
        provenance=chain,
    )

    assert isinstance(report, ValidationReport)
    assert report.finding_id == "hyp-42"


def test_generate_with_none_validator_uses_default() -> None:
    gen = ReportGenerator(None)
    chain = _make_chain("hyp-99")
    report = gen.generate(
        finding_id="hyp-99",
        tests=[_make_test_result(p=0.001)],
        provenance=chain,
    )

    assert report.conclusion == HypothesisStatus.CONFIRMED


# ---------------------------------------------------------------------------
# to_markdown
# ---------------------------------------------------------------------------


def test_to_markdown_contains_required_sections() -> None:
    gen = ReportGenerator()
    chain = _make_chain("find-md-01")
    report = gen.generate(
        finding_id="find-md-01",
        tests=[_make_test_result("my_test", p=0.02)],
        provenance=chain,
    )

    md = to_markdown(report)

    assert "# Validation Report" in md
    assert "## Summary" in md
    assert "## Statistical Tests" in md
    assert "## Conclusion" in md
    assert "find-md-01" in md
    assert "my_test" in md
