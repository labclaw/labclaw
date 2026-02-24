"""Automated figure and statistical report generation.

Spec: docs/specs/L3-validation.md
Design doc: section 5.5 (Validator)
"""

from __future__ import annotations

import logging

from labclaw.validation.statistics import (
    ProvenanceChain,
    StatisticalValidator,
    StatTestResult,
    ValidationConfig,
    ValidationReport,
)

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Combines statistical results and provenance into a ValidationReport."""

    def __init__(self, validator: StatisticalValidator | None = None) -> None:
        self._validator = validator or StatisticalValidator()

    def generate(
        self,
        finding_id: str,
        tests: list[StatTestResult],
        provenance: ProvenanceChain,
        config: ValidationConfig | None = None,
    ) -> ValidationReport:
        """Generate a validation report for a finding.

        Delegates to StatisticalValidator.validate_finding which handles
        correction, conclusion determination, and event emission.
        """
        return self._validator.validate_finding(
            finding_id=finding_id,
            tests=tests,
            provenance=provenance,
            config=config,
        )


def to_markdown(report: ValidationReport) -> str:
    """Render a ValidationReport as a markdown string.

    Args:
        report: The validation report to render.

    Returns:
        Formatted markdown string with Summary, Statistical Tests,
        Provenance, and Conclusion sections.
    """
    lines: list[str] = []

    lines.append(f"# Validation Report: {report.finding_id}")
    lines.append("")

    lines.append("## Summary")
    lines.append(report.summary)
    lines.append("")

    lines.append("## Statistical Tests")
    lines.append("| Test | Statistic | p-value | Significant | Correction |")
    lines.append("| --- | --- | --- | --- | --- |")
    for t in report.tests:
        correction = t.correction_method or "none"
        lines.append(
            f"| {t.test_name} | {t.statistic:.4f} | {t.p_value:.4f}"
            f" | {t.significant} | {correction} |"
        )
    lines.append("")

    lines.append("## Provenance")
    for i, step in enumerate(report.provenance.steps, start=1):
        lines.append(f"{i}. {step.node_type}: {step.node_id} — {step.description}")
    lines.append("")

    lines.append("## Conclusion")
    confidence_pct = report.confidence * 100
    lines.append(f"{report.conclusion.value} (confidence: {confidence_pct:.1f}%)")

    return "\n".join(lines)
