"""Plugin→Sentinel translation — converts DomainPlugin sentinel rules to AlertRule format.

DomainPlugin sentinel rules use: ``{operator: "<", metric: "...", threshold: N}``
AlertRule uses:                   ``{comparison: "below", metric_name: "...", threshold: N}``

This module bridges the two without duplicating the Sentinel system.
"""

from __future__ import annotations

import logging
from typing import Any

from labclaw.core.schemas import QualityLevel
from labclaw.edge.sentinel import AlertRule

logger = logging.getLogger(__name__)

_OPERATOR_MAP: dict[str, str] = {
    "<": "below",
    "<=": "below",
    ">": "above",
    ">=": "above",
    "below": "below",
    "above": "above",
}


def translate_sentinel_rule(
    rule: dict[str, Any],
    *,
    plugin_name: str = "",
) -> AlertRule | None:
    """Convert a DomainPlugin sentinel rule dict to an AlertRule.

    Returns ``None`` if the rule is malformed (logged as warning).
    """
    metric = rule.get("metric") or rule.get("metric_name")
    if not metric:
        logger.warning("Plugin %s: sentinel rule missing 'metric': %s", plugin_name, rule)
        return None

    threshold = rule.get("threshold")
    if threshold is None:
        logger.warning("Plugin %s: sentinel rule missing 'threshold': %s", plugin_name, rule)
        return None

    operator = rule.get("operator") or rule.get("comparison", "<")
    comparison = _OPERATOR_MAP.get(str(operator))
    if comparison is None:
        logger.warning(
            "Plugin %s: unknown operator %r in sentinel rule: %s",
            plugin_name,
            operator,
            rule,
        )
        return None

    level_raw = rule.get("level", "warning")
    try:
        level = QualityLevel(level_raw)
    except ValueError:
        level = QualityLevel.WARNING

    name = rule.get("name", f"{plugin_name}:{metric}")

    return AlertRule(
        name=name,
        metric_name=str(metric),
        threshold=float(threshold),
        comparison=comparison,
        level=level,
    )


def translate_sentinel_rules(
    rules: list[dict[str, Any]],
    *,
    plugin_name: str = "",
) -> list[AlertRule]:
    """Convert a list of DomainPlugin sentinel rules to AlertRule list.

    Malformed rules are skipped (logged as warnings).
    """
    result: list[AlertRule] = []
    for rule in rules:
        alert_rule = translate_sentinel_rule(rule, plugin_name=plugin_name)
        if alert_rule is not None:
            result.append(alert_rule)
    return result
