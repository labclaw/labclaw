"""BDD step definitions for Sentinel quality monitoring (OBSERVE + ANALYZE).

Provides Given/When/Then steps for sentinel.feature.
Tests quality metric checks, alert rules, and session summaries.
"""

from __future__ import annotations

from pytest_bdd import given, parsers, then, when

from labclaw.core.events import event_registry
from labclaw.core.schemas import QualityLevel, QualityMetric
from labclaw.edge.sentinel import (
    AlertRule,
    QualityAlert,
    Sentinel,
    SessionQualitySummary,
)
from tests.features.conftest import EventCapture

# ---------------------------------------------------------------------------
# Background / fixtures
# ---------------------------------------------------------------------------


@given("the sentinel is initialized", target_fixture="sentinel")
def sentinel_initialized(event_capture: EventCapture) -> Sentinel:
    """Provide a fresh Sentinel and wire event capture."""
    for evt_name in event_registry.list_events():
        if evt_name.startswith("sentinel."):
            event_registry.subscribe(evt_name, event_capture)
    return Sentinel()


# ---------------------------------------------------------------------------
# Given steps
# ---------------------------------------------------------------------------


@given(
    parsers.parse('a rule "{rule_name}" for metric "{metric_name}" below threshold {threshold:g}'),
    target_fixture="current_rule",
)
def add_rule_below(
    sentinel: Sentinel, rule_name: str, metric_name: str, threshold: float
) -> AlertRule:
    """Add a rule that triggers when a metric falls below the threshold."""
    rule = AlertRule(
        name=rule_name,
        metric_name=metric_name,
        threshold=threshold,
        comparison="below",
        level=QualityLevel.WARNING,
    )
    sentinel.add_rule(rule)
    return rule


@given(
    parsers.parse('a rule "{rule_name}" for metric "{metric_name}" above threshold {threshold:g}'),
    target_fixture="current_rule",
)
def add_rule_above(
    sentinel: Sentinel, rule_name: str, metric_name: str, threshold: float
) -> AlertRule:
    """Add a rule that triggers when a metric goes above the threshold."""
    rule = AlertRule(
        name=rule_name,
        metric_name=metric_name,
        threshold=threshold,
        comparison="above",
        level=QualityLevel.WARNING,
    )
    sentinel.add_rule(rule)
    return rule


@given(
    parsers.parse(
        'a critical rule "{rule_name}" for metric "{metric_name}" below threshold {threshold:g}'
    ),
    target_fixture="current_rule",
)
def add_critical_rule_below(
    sentinel: Sentinel, rule_name: str, metric_name: str, threshold: float
) -> AlertRule:
    """Add a CRITICAL-level rule that triggers when metric falls below threshold."""
    rule = AlertRule(
        name=rule_name,
        metric_name=metric_name,
        threshold=threshold,
        comparison="below",
        level=QualityLevel.CRITICAL,
    )
    sentinel.add_rule(rule)
    return rule


@given(
    parsers.parse('I check session "{session_id}" with a passing metric'),
    target_fixture="passing_summary",
)
def check_session_passing(sentinel: Sentinel, session_id: str) -> SessionQualitySummary:
    """Check a session with a metric that passes all rules."""
    metric = QualityMetric(name="snr", value=10.0, level=QualityLevel.GOOD)
    return sentinel.check_session(session_id, [metric])


@given(
    parsers.parse('I check session "{session_id}" with a failing metric'),
    target_fixture="failing_summary",
)
def check_session_failing(sentinel: Sentinel, session_id: str) -> SessionQualitySummary:
    """Check a session with a metric that fails a rule."""
    metric = QualityMetric(name="snr", value=1.0, level=QualityLevel.GOOD)
    return sentinel.check_session(session_id, [metric])


# ---------------------------------------------------------------------------
# When steps
# ---------------------------------------------------------------------------


@when(
    parsers.parse('I check a metric "{metric_name}" with value {value:g}'),
    target_fixture="check_alerts",
)
def check_single_metric(sentinel: Sentinel, metric_name: str, value: float) -> list[QualityAlert]:
    """Check a single metric and capture the resulting alerts."""
    metric = QualityMetric(name=metric_name, value=value, level=QualityLevel.GOOD)
    # Use check_session with a dummy session to also emit check.completed
    summary = sentinel.check_session("__single_check__", [metric])
    return summary.alerts


@when(
    parsers.parse('I check session "{session_id}" with metrics:'),
    target_fixture="session_summary",
)
def check_session_with_table(
    sentinel: Sentinel, session_id: str, datatable: list[list[str]]
) -> SessionQualitySummary:
    """Check a session with metrics from a data table."""
    headers = [str(c) for c in datatable[0]]
    rows = [{headers[i]: str(cell) for i, cell in enumerate(row)} for row in datatable[1:]]
    metrics = [
        QualityMetric(
            name=row["name"],
            value=float(row["value"]),
            level=QualityLevel.GOOD,
        )
        for row in rows
    ]
    return sentinel.check_session(session_id, metrics)


@when(
    parsers.parse('I get alerts for session "{session_id}"'),
    target_fixture="filtered_alerts",
)
def get_alerts_for_session(sentinel: Sentinel, session_id: str) -> list[QualityAlert]:
    """Get alerts filtered by session ID."""
    return sentinel.get_alerts(session_id=session_id)


@when("I get all alerts", target_fixture="all_alerts")
def get_all_alerts(sentinel: Sentinel) -> list[QualityAlert]:
    """Get all alerts regardless of session."""
    return sentinel.get_alerts()


# ---------------------------------------------------------------------------
# Then steps
# ---------------------------------------------------------------------------


@then("no alerts are raised")
def no_alerts(check_alerts: list[QualityAlert]) -> None:
    assert len(check_alerts) == 0, f"Expected 0 alerts, got {len(check_alerts)}"


@then(parsers.parse('{count:d} alert is raised with level "{level}"'))
def n_alerts_with_level(check_alerts: list[QualityAlert], count: int, level: str) -> None:
    assert len(check_alerts) == count, f"Expected {count} alerts, got {len(check_alerts)}"
    for alert in check_alerts:
        assert alert.level.value == level, f"Expected level {level!r}, got {alert.level.value!r}"


@then(parsers.parse('the session summary overall level is "{level}"'))
def session_overall_level(session_summary: SessionQualitySummary, level: str) -> None:
    assert session_summary.overall_level.value == level, (
        f"Expected overall level {level!r}, got {session_summary.overall_level.value!r}"
    )


@then(parsers.parse("the session has {count:d} alerts"))
def session_alert_count(session_summary: SessionQualitySummary, count: int) -> None:
    assert len(session_summary.alerts) == count, (
        f"Expected {count} alerts, got {len(session_summary.alerts)}"
    )


@then(parsers.parse("the session has {count:d} alert"))
def session_alert_count_singular(session_summary: SessionQualitySummary, count: int) -> None:
    assert len(session_summary.alerts) == count, (
        f"Expected {count} alerts, got {len(session_summary.alerts)}"
    )


@then(parsers.parse("I get {count:d} alert"))
def got_n_alerts(filtered_alerts: list[QualityAlert], count: int) -> None:
    assert len(filtered_alerts) == count, f"Expected {count} alerts, got {len(filtered_alerts)}"


@then(parsers.parse("I get at least {count:d} alerts total"))
def got_at_least_n_alerts(all_alerts: list[QualityAlert], count: int) -> None:
    assert len(all_alerts) >= count, f"Expected >= {count} alerts total, got {len(all_alerts)}"
