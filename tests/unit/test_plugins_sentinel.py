"""Tests for plugins/sentinel.py — DomainPlugin → AlertRule translation."""

from __future__ import annotations

from labclaw.edge.sentinel import AlertRule
from labclaw.plugins.sentinel import translate_sentinel_rule, translate_sentinel_rules

# ---------------------------------------------------------------------------
# translate_sentinel_rule
# ---------------------------------------------------------------------------


def test_translate_basic_less_than() -> None:
    rule = {"metric": "temperature", "operator": "<", "threshold": 20.0}
    result = translate_sentinel_rule(rule, plugin_name="test")
    assert result is not None
    assert result.metric_name == "temperature"
    assert result.comparison == "below"
    assert result.threshold == 20.0


def test_translate_basic_greater_than() -> None:
    rule = {"metric": "pressure", "operator": ">", "threshold": 100.0}
    result = translate_sentinel_rule(rule, plugin_name="test")
    assert result is not None
    assert result.comparison == "above"


def test_translate_accepts_metric_name_key() -> None:
    rule = {"metric_name": "speed", "operator": "<", "threshold": 5.0}
    result = translate_sentinel_rule(rule, plugin_name="test")
    assert result is not None
    assert result.metric_name == "speed"


def test_translate_accepts_comparison_key() -> None:
    rule = {"metric": "x", "comparison": "above", "threshold": 10.0}
    result = translate_sentinel_rule(rule, plugin_name="test")
    assert result is not None
    assert result.comparison == "above"


def test_translate_missing_metric_returns_none() -> None:
    rule = {"operator": "<", "threshold": 1.0}
    result = translate_sentinel_rule(rule, plugin_name="test")
    assert result is None


def test_translate_missing_threshold_returns_none() -> None:
    rule = {"metric": "x", "operator": "<"}
    result = translate_sentinel_rule(rule, plugin_name="test")
    assert result is None


def test_translate_unknown_operator_returns_none() -> None:
    rule = {"metric": "x", "operator": "!=", "threshold": 1.0}
    result = translate_sentinel_rule(rule, plugin_name="test")
    assert result is None


def test_translate_uses_custom_name() -> None:
    rule = {"name": "my_rule", "metric": "x", "operator": "<", "threshold": 1.0}
    result = translate_sentinel_rule(rule, plugin_name="test")
    assert result is not None
    assert result.name == "my_rule"


def test_translate_default_name_from_plugin_metric() -> None:
    rule = {"metric": "speed", "operator": ">", "threshold": 50.0}
    result = translate_sentinel_rule(rule, plugin_name="phys")
    assert result is not None
    assert result.name == "phys:speed"


def test_translate_level_warning() -> None:
    rule = {"metric": "x", "operator": "<", "threshold": 1.0, "level": "warning"}
    result = translate_sentinel_rule(rule, plugin_name="test")
    assert result is not None
    assert result.level.value == "warning"


def test_translate_level_invalid_defaults_warning() -> None:
    rule = {"metric": "x", "operator": "<", "threshold": 1.0, "level": "bogus"}
    result = translate_sentinel_rule(rule, plugin_name="test")
    assert result is not None
    assert result.level.value == "warning"


def test_translate_le_maps_to_below() -> None:
    rule = {"metric": "x", "operator": "<=", "threshold": 1.0}
    result = translate_sentinel_rule(rule, plugin_name="test")
    assert result is not None
    assert result.comparison == "below"


def test_translate_ge_maps_to_above() -> None:
    rule = {"metric": "x", "operator": ">=", "threshold": 1.0}
    result = translate_sentinel_rule(rule, plugin_name="test")
    assert result is not None
    assert result.comparison == "above"


def test_translate_string_below_passthrough() -> None:
    rule = {"metric": "x", "operator": "below", "threshold": 1.0}
    result = translate_sentinel_rule(rule, plugin_name="test")
    assert result is not None
    assert result.comparison == "below"


def test_translate_string_above_passthrough() -> None:
    rule = {"metric": "x", "operator": "above", "threshold": 1.0}
    result = translate_sentinel_rule(rule, plugin_name="test")
    assert result is not None
    assert result.comparison == "above"


# ---------------------------------------------------------------------------
# translate_sentinel_rules (batch)
# ---------------------------------------------------------------------------


def test_translate_rules_batch_filters_malformed() -> None:
    rules = [
        {"metric": "a", "operator": "<", "threshold": 1.0},
        {"operator": "<", "threshold": 2.0},  # missing metric
        {"metric": "b", "operator": ">", "threshold": 3.0},
    ]
    result = translate_sentinel_rules(rules, plugin_name="test")
    assert len(result) == 2
    assert all(isinstance(r, AlertRule) for r in result)


def test_translate_rules_empty_input() -> None:
    result = translate_sentinel_rules([], plugin_name="test")
    assert result == []
