"""Edge quality checker — basic quality checks on incoming data files.

Spec: docs/specs/L2-edge.md (Quality Checks section)
Design doc: section 5.1 (Session Chronicle — edge quality gate)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from labclaw.core.events import event_registry
from labclaw.core.schemas import FileReference, QualityLevel, QualityMetric

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Register events at module import time
# ---------------------------------------------------------------------------

_EVENTS = [
    "hardware.quality.checked",
]

for _evt in _EVENTS:
    if not event_registry.is_registered(_evt):
        event_registry.register(_evt)


# ---------------------------------------------------------------------------
# Known video extensions
# ---------------------------------------------------------------------------

_VIDEO_EXTENSIONS = {".avi", ".mp4", ".mkv", ".mov", ".wmv", ".flv", ".webm"}


# ---------------------------------------------------------------------------
# Quality checker
# ---------------------------------------------------------------------------


class QualityChecker:
    """Performs basic quality checks on incoming data files."""

    def check_file(self, file_ref: FileReference) -> QualityMetric:
        """Check a file's quality (exists, non-empty, readable).

        Returns a single QualityMetric summarising the check.
        """
        path = file_ref.path
        now = datetime.now(UTC)

        if not path.exists():
            metric = QualityMetric(
                name="file_exists",
                value=0.0,
                level=QualityLevel.CRITICAL,
                timestamp=now,
            )
            self._emit_checked(file_ref, metric)
            return metric

        size = path.stat().st_size

        if size == 0:
            metric = QualityMetric(
                name="file_non_empty",
                value=0.0,
                level=QualityLevel.WARNING,
                timestamp=now,
            )
            self._emit_checked(file_ref, metric)
            return metric

        # Try to read a small chunk to verify readability
        try:
            with open(path, "rb") as f:
                f.read(1024)
        except OSError:
            metric = QualityMetric(
                name="file_readable",
                value=0.0,
                level=QualityLevel.CRITICAL,
                timestamp=now,
            )
            self._emit_checked(file_ref, metric)
            return metric

        metric = QualityMetric(
            name="file_basic",
            value=float(size),
            unit="bytes",
            level=QualityLevel.GOOD,
            timestamp=now,
        )
        self._emit_checked(file_ref, metric)
        return metric

    def check_video(self, file_ref: FileReference) -> list[QualityMetric]:
        """Basic video quality checks (file size, extension).

        Returns a list of QualityMetrics.
        """
        metrics: list[QualityMetric] = []
        now = datetime.now(UTC)

        # First run the generic check
        basic = self.check_file(file_ref)
        metrics.append(basic)

        # Extension check
        ext = file_ref.path.suffix.lower()
        if ext in _VIDEO_EXTENSIONS:
            metrics.append(
                QualityMetric(
                    name="video_extension",
                    value=1.0,
                    level=QualityLevel.GOOD,
                    timestamp=now,
                )
            )
        else:
            metrics.append(
                QualityMetric(
                    name="video_extension",
                    value=0.0,
                    level=QualityLevel.WARNING,
                    timestamp=now,
                )
            )

        return metrics

    def check_generic(self, file_ref: FileReference) -> list[QualityMetric]:
        """Generic file quality checks.

        Returns a list of QualityMetrics covering existence, size, readability.
        """
        metrics: list[QualityMetric] = []
        now = datetime.now(UTC)
        path = file_ref.path

        # Existence
        exists = path.exists()
        metrics.append(
            QualityMetric(
                name="file_exists",
                value=1.0 if exists else 0.0,
                level=QualityLevel.GOOD if exists else QualityLevel.CRITICAL,
                timestamp=now,
            )
        )

        if not exists:
            return metrics

        # Size
        size = path.stat().st_size
        if size == 0:
            metrics.append(
                QualityMetric(
                    name="file_size",
                    value=0.0,
                    unit="bytes",
                    level=QualityLevel.WARNING,
                    timestamp=now,
                )
            )
        else:
            metrics.append(
                QualityMetric(
                    name="file_size",
                    value=float(size),
                    unit="bytes",
                    level=QualityLevel.GOOD,
                    timestamp=now,
                )
            )

        # Readability
        try:
            with open(path, "rb") as f:
                f.read(1024)
            metrics.append(
                QualityMetric(
                    name="file_readable",
                    value=1.0,
                    level=QualityLevel.GOOD,
                    timestamp=now,
                )
            )
        except OSError:
            metrics.append(
                QualityMetric(
                    name="file_readable",
                    value=0.0,
                    level=QualityLevel.CRITICAL,
                    timestamp=now,
                )
            )

        return metrics

    @staticmethod
    def _emit_checked(file_ref: FileReference, metric: QualityMetric) -> None:
        """Emit quality.checked event."""
        event_registry.emit(
            "hardware.quality.checked",
            payload={
                "path": str(file_ref.path),
                "metric_name": metric.name,
                "level": metric.level.value,
                "value": metric.value,
            },
        )
