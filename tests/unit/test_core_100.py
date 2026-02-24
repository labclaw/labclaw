"""Tests to bring core/ modules to 100% coverage.

Covers:
- core/graph.py: get_node_type() error path (lines 268-272)
- core/safety.py: check_command BLOCKED safety level path (lines 178-184)
- core/schemas.py: EventName validation error paths (lines 113, 127)
"""

from __future__ import annotations

import pytest

from labclaw.core.graph import get_node_type
from labclaw.core.safety import HardwareSafetyGuard
from labclaw.core.schemas import DeviceStatus, EventName, SafetyLevel

# ---------------------------------------------------------------------------
# core/graph.py — get_node_type unknown type
# ---------------------------------------------------------------------------


def test_get_node_type_unknown_raises() -> None:
    with pytest.raises(KeyError, match="Unknown node type"):
        get_node_type("nonexistent_type")


def test_get_node_type_known() -> None:
    node_cls = get_node_type("experiment")
    assert node_cls.__name__ == "ExperimentNode"


# ---------------------------------------------------------------------------
# core/safety.py — BLOCKED safety level path
# ---------------------------------------------------------------------------


def test_check_command_blocked_safety_level() -> None:
    ctrl = HardwareSafetyGuard()
    result = ctrl.check_command(
        device_id="dev1",
        action="read",
        device_status=DeviceStatus.ONLINE,
        safety_level=SafetyLevel.BLOCKED,
    )
    assert result.allowed is False
    assert "blocked by safety level BLOCKED" in result.reason


# ---------------------------------------------------------------------------
# core/schemas.py — EventName validation errors
# ---------------------------------------------------------------------------


def test_event_name_empty_component_raises() -> None:
    with pytest.raises(ValueError, match="non-empty and dot-free"):
        EventName(layer="", module="mod", action="act")


def test_event_name_dot_in_component_raises() -> None:
    with pytest.raises(ValueError, match="non-empty and dot-free"):
        EventName(layer="lay.er", module="mod", action="act")


def test_event_name_parse_wrong_parts_raises() -> None:
    with pytest.raises(ValueError, match="must be"):
        EventName.parse("only.two")

    with pytest.raises(ValueError, match="must be"):
        EventName.parse("too.many.parts.here")
