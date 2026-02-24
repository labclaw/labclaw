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
