"""Validation — statistical rigor and full provenance.

Maps to the CONCLUDE + ITERATE steps of the scientific method:
every finding must survive rigorous validation before being reported.

Spec: docs/specs/L3-validation.md
"""

from __future__ import annotations

from labclaw.validation.cross_validation import holdout_validate, kfold_validate, permutation_test
from labclaw.validation.provenance import ProvenanceTracker, from_dict, to_dict
from labclaw.validation.report import ReportGenerator, to_markdown
from labclaw.validation.statistics import (
    ProvenanceChain,
    ProvenanceStep,
    StatisticalValidator,
    StatTestResult,
    ValidationConfig,
    ValidationReport,
)

__all__ = [
    "ProvenanceChain",
    "ProvenanceStep",
    "ProvenanceTracker",
    "ReportGenerator",
    "StatisticalValidator",
    "StatTestResult",
    "ValidationConfig",
    "ValidationReport",
    "from_dict",
    "holdout_validate",
    "kfold_validate",
    "permutation_test",
    "to_dict",
    "to_markdown",
]
