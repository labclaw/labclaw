"""Sentinel — real-time quality monitoring and alerting for lab sessions.

Spec: docs/specs/L2-edge.md (Sentinel section)
Design doc: section 5.2 (Sentinel quality monitoring)

Aggregates quality checks across a session and generates alerts
when quality degrades below configured thresholds.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from labclaw.core.events import event_registry
from labclaw.core.schemas import QualityLevel, QualityMetric

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Register events at module import time
# ---------------------------------------------------------------------------

_EVENTS = [
    "sentinel.alert.raised",
    "sentinel.check.completed",
]

for _evt in _EVENTS:
    if not event_registry.is_registered(_evt):
        event_registry.register(_evt)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class AlertRule(BaseModel):
    """A rule that triggers an alert when quality degrades."""

    name: str
    metric_name: str
    threshold: float
    comparison: str = "below"  # "below" or "above"
    level: QualityLevel = QualityLevel.WARNING


class QualityAlert(BaseModel):
    """An alert raised by the sentinel."""

    alert_id: str = Field(default_factory=_uuid)
    rule_name: str
    metric: QualityMetric
    message: str
    level: QualityLevel
    session_id: str | None = None
    timestamp: datetime = Field(default_factory=_now)


class SessionQualitySummary(BaseModel):
    """Aggregated quality for a session."""

    session_id: str
    metrics: list[QualityMetric]
    overall_level: QualityLevel
    alerts: list[QualityAlert]
    checked_at: datetime = Field(default_factory=_now)


# ---------------------------------------------------------------------------
# Sentinel
# ---------------------------------------------------------------------------


class Sentinel:
    """Real-time quality monitoring and alerting."""

    def __init__(self, rules: list[AlertRule] | None = None) -> None:
        self._rules: list[AlertRule] = rules or []
        self._alerts: list[QualityAlert] = []
        self._summaries: dict[str, SessionQualitySummary] = {}

    def add_rule(self, rule: AlertRule) -> None:
        """Add a monitoring rule."""
        self._rules.append(rule)

    def check_metric(
        self, metric: QualityMetric, session_id: str | None = None
    ) -> list[QualityAlert]:
        """Check a metric against all rules. Return any triggered alerts."""
        triggered: list[QualityAlert] = []

        for rule in self._rules:
            if rule.metric_name != metric.name:
                continue

            fired = False
            if rule.comparison == "below" and metric.value < rule.threshold:
                fired = True
            elif rule.comparison == "above" and metric.value > rule.threshold:
                fired = True

            if fired:
                alert = QualityAlert(
                    rule_name=rule.name,
                    metric=metric,
                    message=(
                        f"Metric {metric.name}={metric.value} "
                        f"{rule.comparison} threshold {rule.threshold}"
                    ),
                    level=rule.level,
                    session_id=session_id,
                )
                triggered.append(alert)
                self._alerts.append(alert)

                event_registry.emit(
                    "sentinel.alert.raised",
                    payload={
                        "alert_id": alert.alert_id,
                        "rule_name": rule.name,
                        "metric_name": metric.name,
                        "value": metric.value,
                        "level": alert.level.value,
                        "session_id": session_id,
                    },
                )
                logger.warning(
                    "Alert raised: %s (rule=%s, value=%s, threshold=%s)",
                    alert.message,
                    rule.name,
                    metric.value,
                    rule.threshold,
                )

        return triggered

    def check_session(
        self, session_id: str, metrics: Sequence[QualityMetric]
    ) -> SessionQualitySummary:
        """Check all metrics for a session, produce summary."""
        session_alerts: list[QualityAlert] = []

        for metric in metrics:
            alerts = self.check_metric(metric, session_id=session_id)
            session_alerts.extend(alerts)

        overall = _compute_overall_level(list(metrics), session_alerts)

        summary = SessionQualitySummary(
            session_id=session_id,
            metrics=list(metrics),
            overall_level=overall,
            alerts=session_alerts,
        )
        self._summaries[session_id] = summary

        event_registry.emit(
            "sentinel.check.completed",
            payload={
                "session_id": session_id,
                "overall_level": overall.value,
                "metric_count": len(metrics),
                "alert_count": len(session_alerts),
            },
        )

        return summary

    def get_alerts(self, session_id: str | None = None) -> list[QualityAlert]:
        """Get alerts, optionally filtered by session."""
        if session_id is None:
            return list(self._alerts)
        return [a for a in self._alerts if a.session_id == session_id]

    def get_summary(self, session_id: str) -> SessionQualitySummary | None:
        """Get the quality summary for a session."""
        return self._summaries.get(session_id)


def _compute_overall_level(
    metrics: list[QualityMetric], alerts: list[QualityAlert]
) -> QualityLevel:
    """Compute overall quality level from metrics and alerts.

    CRITICAL if any alert is CRITICAL, WARNING if any alert is WARNING,
    otherwise GOOD.
    """
    levels: set[QualityLevel] = set()

    for alert in alerts:
        levels.add(alert.level)

    for metric in metrics:
        if metric.level != QualityLevel.UNKNOWN:
            levels.add(metric.level)

    if QualityLevel.CRITICAL in levels:
        return QualityLevel.CRITICAL
    if QualityLevel.WARNING in levels:
        return QualityLevel.WARNING
    return QualityLevel.GOOD
