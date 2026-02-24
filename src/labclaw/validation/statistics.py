"""Statistical validation — effect sizes, confidence intervals, multiple comparison correction.

Spec: docs/specs/L3-validation.md
Design doc: section 5.5 (Validator)
"""

from __future__ import annotations

import logging
import math
import random
import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from labclaw.core.events import event_registry
from labclaw.core.schemas import HypothesisStatus

try:
    from scipy import stats as scipy_stats
except ImportError:  # pragma: no cover
    scipy_stats = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------

class StatTestResult(BaseModel):
    """Result of a single statistical test."""

    test_name: str
    statistic: float
    p_value: float
    effect_size: float | None = None
    confidence_interval: tuple[float, float] | None = None
    sample_sizes: dict[str, int]
    significant: bool
    correction_method: str | None = None
    warnings: list[str] = Field(default_factory=list)


class ProvenanceStep(BaseModel):
    """A single step in a provenance chain."""

    node_id: str
    node_type: str
    description: str
    timestamp: datetime = Field(default_factory=_now)


class ProvenanceChain(BaseModel):
    """Full traceability from a finding back to raw data."""

    chain_id: str = Field(default_factory=_uuid)
    finding_id: str
    steps: list[ProvenanceStep]
    created_at: datetime = Field(default_factory=_now)


class ValidationReport(BaseModel):
    """Complete validation report for a finding."""

    report_id: str = Field(default_factory=_uuid)
    finding_id: str
    tests: list[StatTestResult]
    provenance: ProvenanceChain
    conclusion: HypothesisStatus
    confidence: float
    summary: str
    created_at: datetime = Field(default_factory=_now)


class ValidationConfig(BaseModel):
    """Configuration for validation thresholds."""

    alpha: float = 0.05
    correction_method: str = "bonferroni"
    min_effect_size: float = 0.2
    min_sample_size: int = 5


# ---------------------------------------------------------------------------
# Register events
# ---------------------------------------------------------------------------

_VALIDATION_EVENTS = [
    "validation.test.completed",
    "validation.report.generated",
    "validation.provenance.built",
]

for _evt in _VALIDATION_EVENTS:
    if not event_registry.is_registered(_evt):
        event_registry.register(_evt)


# ---------------------------------------------------------------------------
# StatisticalValidator
# ---------------------------------------------------------------------------

class StatisticalValidator:
    """Statistical testing engine with multiple comparison correction."""

    SUPPORTED_TESTS = {"t_test", "mann_whitney", "permutation"}
    SUPPORTED_CORRECTIONS = {"bonferroni", "holm"}

    def run_test(
        self,
        test_name: str,
        group_a: list[float],
        group_b: list[float],
        config: ValidationConfig | None = None,
    ) -> StatTestResult:
        """Run a named statistical test on two groups."""
        if test_name not in self.SUPPORTED_TESTS:
            raise ValueError(
                f"Unknown test {test_name!r}. Supported: {sorted(self.SUPPORTED_TESTS)}"
            )
        if not group_a or not group_b:
            raise ValueError("Both groups must be non-empty")

        cfg = config or ValidationConfig()
        warnings: list[str] = []

        if len(group_a) < cfg.min_sample_size or len(group_b) < cfg.min_sample_size:
            warnings.append(
                f"Sample size below minimum ({cfg.min_sample_size}): "
                f"group_a={len(group_a)}, group_b={len(group_b)}"
            )

        if test_name == "t_test":
            result = self._t_test(group_a, group_b, cfg)
        elif test_name == "mann_whitney":
            result = self._mann_whitney(group_a, group_b, cfg)
        elif test_name == "permutation":
            result = self._permutation_test(group_a, group_b, cfg)
        else:
            raise ValueError(f"Unknown test: {test_name!r}")  # pragma: no cover

        result.warnings = warnings

        event_registry.emit(
            "validation.test.completed",
            payload={
                "test_name": result.test_name,
                "p_value": float(result.p_value),
                "significant": result.significant,
            },
        )

        return result

    def apply_correction(
        self,
        results: list[StatTestResult],
        method: str = "bonferroni",
        alpha: float = 0.05,
    ) -> list[StatTestResult]:
        """Apply multiple comparison correction to test results."""
        if method not in self.SUPPORTED_CORRECTIONS:
            raise ValueError(
                f"Unknown correction {method!r}. Supported: {sorted(self.SUPPORTED_CORRECTIONS)}"
            )

        if method == "bonferroni":
            return self._bonferroni(results, alpha)
        return self._holm(results, alpha)

    def validate_finding(
        self,
        finding_id: str,
        tests: list[StatTestResult],
        provenance: ProvenanceChain,
        config: ValidationConfig | None = None,
    ) -> ValidationReport:
        """Generate a full ValidationReport for a finding."""
        cfg = config or ValidationConfig()

        # Apply correction if multiple tests
        corrected = (
            self.apply_correction(tests, cfg.correction_method, cfg.alpha)
            if len(tests) > 1
            else tests
        )

        # Determine conclusion
        conclusion = self._determine_conclusion(corrected, cfg)

        # Compute confidence as fraction of significant tests
        sig_count = sum(1 for t in corrected if t.significant)
        confidence = sig_count / len(corrected) if corrected else 0.0

        summary = (
            f"Validation of finding {finding_id}: "
            f"{sig_count}/{len(corrected)} tests significant. "
            f"Conclusion: {conclusion.value}."
        )

        report = ValidationReport(
            finding_id=finding_id,
            tests=corrected,
            provenance=provenance,
            conclusion=conclusion,
            confidence=confidence,
            summary=summary,
        )

        event_registry.emit(
            "validation.report.generated",
            payload={
                "report_id": report.report_id,
                "finding_id": finding_id,
                "conclusion": conclusion.value,
            },
        )

        return report

    # ----- Private test implementations -----

    def _t_test(
        self, group_a: list[float], group_b: list[float], cfg: ValidationConfig
    ) -> StatTestResult:
        if scipy_stats is None:
            raise ImportError("scipy is required for t_test")  # pragma: no cover

        stat, p_val = scipy_stats.ttest_ind(group_a, group_b)
        effect = _cohens_d(group_a, group_b)

        return StatTestResult(
            test_name="t_test",
            statistic=float(stat),
            p_value=float(p_val),
            effect_size=effect,
            sample_sizes={"group_a": len(group_a), "group_b": len(group_b)},
            significant=float(p_val) < cfg.alpha,
        )

    def _mann_whitney(
        self, group_a: list[float], group_b: list[float], cfg: ValidationConfig
    ) -> StatTestResult:
        if scipy_stats is None:
            raise ImportError("scipy is required for mann_whitney")  # pragma: no cover

        stat, p_val = scipy_stats.mannwhitneyu(group_a, group_b, alternative="two-sided")

        return StatTestResult(
            test_name="mann_whitney",
            statistic=float(stat),
            p_value=float(p_val),
            effect_size=None,
            sample_sizes={"group_a": len(group_a), "group_b": len(group_b)},
            significant=float(p_val) < cfg.alpha,
        )

    def _permutation_test(
        self, group_a: list[float], group_b: list[float], cfg: ValidationConfig
    ) -> StatTestResult:
        combined = group_a + group_b
        n_a = len(group_a)
        observed_diff = abs(_mean(group_a) - _mean(group_b))

        n_perms = 1000
        count_extreme = 0
        rng = random.Random(42)  # Deterministic for reproducibility

        for _ in range(n_perms):
            rng.shuffle(combined)
            perm_a = combined[:n_a]
            perm_b = combined[n_a:]
            perm_diff = abs(_mean(perm_a) - _mean(perm_b))
            if perm_diff >= observed_diff:
                count_extreme += 1

        p_val = count_extreme / n_perms

        return StatTestResult(
            test_name="permutation",
            statistic=observed_diff,
            p_value=p_val,
            effect_size=None,
            sample_sizes={"group_a": len(group_a), "group_b": len(group_b)},
            significant=p_val < cfg.alpha,
        )

    # ----- Correction implementations -----

    def _bonferroni(
        self, results: list[StatTestResult], alpha: float = 0.05,
    ) -> list[StatTestResult]:
        n = len(results)
        corrected = []
        for r in results:
            new_p = min(r.p_value * n, 1.0)
            corrected.append(r.model_copy(update={
                "p_value": new_p,
                "significant": new_p < alpha,
                "correction_method": "bonferroni",
            }))
        return corrected

    def _holm(
        self, results: list[StatTestResult], alpha: float = 0.05,
    ) -> list[StatTestResult]:
        n = len(results)
        indexed = sorted(enumerate(results), key=lambda x: x[1].p_value)
        corrected: list[StatTestResult | None] = [None] * n
        running_max = 0.0

        for rank, (orig_idx, r) in enumerate(indexed):
            multiplier = n - rank
            unadjusted = min(r.p_value * multiplier, 1.0)
            running_max = max(running_max, unadjusted)
            corrected[orig_idx] = r.model_copy(update={
                "p_value": running_max,
                "significant": running_max < alpha,
                "correction_method": "holm",
            })

        if any(c is None for c in corrected):  # pragma: no cover
            raise RuntimeError("Holm correction failed to fill all result slots")
        return [c for c in corrected if c is not None]

    # ----- Conclusion logic -----

    @staticmethod
    def _determine_conclusion(
        tests: list[StatTestResult], cfg: ValidationConfig
    ) -> HypothesisStatus:
        if not tests:
            return HypothesisStatus.INCONCLUSIVE

        sig_count = sum(1 for t in tests if t.significant)
        total = len(tests)

        if sig_count == total:
            return HypothesisStatus.CONFIRMED
        if sig_count == 0:
            return HypothesisStatus.REJECTED
        return HypothesisStatus.INCONCLUSIVE


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _cohens_d(group_a: list[float], group_b: list[float]) -> float:
    """Compute Cohen's d effect size for two independent groups."""
    n_a = len(group_a)
    n_b = len(group_b)
    mean_a = _mean(group_a)
    mean_b = _mean(group_b)

    var_a = sum((x - mean_a) ** 2 for x in group_a) / max(n_a - 1, 1)
    var_b = sum((x - mean_b) ** 2 for x in group_b) / max(n_b - 1, 1)

    pooled_std = math.sqrt(((n_a - 1) * var_a + (n_b - 1) * var_b) / max(n_a + n_b - 2, 1))
    if pooled_std == 0:
        return 0.0

    return (mean_a - mean_b) / pooled_std
