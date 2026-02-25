"""Extended tests for EventRegistry covering duplicate registration, wildcard handlers,
schema retrieval, and clear().
"""

from __future__ import annotations

from labclaw.core.events import EventRegistry
from labclaw.core.schemas import LabEvent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _reg_with(*names: str) -> EventRegistry:
    """Create a fresh EventRegistry pre-loaded with the given event names."""
    reg = EventRegistry()
    for name in names:
        reg.register(name)
    return reg


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def test_register_duplicate_raises() -> None:
    reg = EventRegistry()
    reg.register("hardware.file.detected")
    try:
        reg.register("hardware.file.detected")
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError for duplicate registration")


def test_register_with_custom_schema_stored() -> None:
    reg = EventRegistry()

    class MyEvent(LabEvent):
        pass

    reg.register("hardware.device.online", schema=MyEvent)
    assert reg.get_schema("hardware.device.online") is MyEvent


# ---------------------------------------------------------------------------
# Emit
# ---------------------------------------------------------------------------


def test_emit_unregistered_raises() -> None:
    reg = EventRegistry()
    try:
        reg.emit("hardware.file.detected")
    except KeyError:
        pass
    else:
        raise AssertionError("Expected KeyError for unregistered event")


def test_emit_returns_lab_event() -> None:
    reg = _reg_with("hardware.device.online")
    event = reg.emit("hardware.device.online", payload={"device_id": "cam-1"})
    assert isinstance(event, LabEvent)
    assert event.payload["device_id"] == "cam-1"


# ---------------------------------------------------------------------------
# Subscribe + emit
# ---------------------------------------------------------------------------


def test_subscribe_and_emit_calls_handler() -> None:
    reg = _reg_with("hardware.file.detected")
    received: list[LabEvent] = []
    reg.subscribe("hardware.file.detected", received.append)

    reg.emit("hardware.file.detected", payload={"path": "/tmp/x.csv"})

    assert len(received) == 1
    assert received[0].payload["path"] == "/tmp/x.csv"


def test_handler_exception_doesnt_crash() -> None:
    reg = _reg_with("hardware.file.detected")

    def bad_handler(event: LabEvent) -> None:
        raise RuntimeError("intentional failure")

    reg.subscribe("hardware.file.detected", bad_handler)
    # Should not propagate; event still returned
    event = reg.emit("hardware.file.detected")
    assert isinstance(event, LabEvent)


# ---------------------------------------------------------------------------
# Wildcard handler
# ---------------------------------------------------------------------------


def test_wildcard_handler_receives_any_event() -> None:
    reg = _reg_with("hardware.file.detected", "hardware.device.online")
    wildcard_events: list[LabEvent] = []
    reg.subscribe("*", wildcard_events.append)

    reg.emit("hardware.file.detected")
    reg.emit("hardware.device.online")

    assert len(wildcard_events) == 2


def test_wildcard_handler_exception_doesnt_crash() -> None:
    reg = _reg_with("hardware.file.detected")

    def bad_wildcard(event: LabEvent) -> None:
        raise RuntimeError("wildcard failure")

    reg.subscribe("*", bad_wildcard)
    event = reg.emit("hardware.file.detected")
    assert isinstance(event, LabEvent)


# ---------------------------------------------------------------------------
# get_schema
# ---------------------------------------------------------------------------


def test_get_schema_returns_none_for_unknown() -> None:
    reg = EventRegistry()
    assert reg.get_schema("hardware.file.detected") is None


def test_get_schema_returns_default_lab_event() -> None:
    reg = _reg_with("hardware.file.detected")
    schema = reg.get_schema("hardware.file.detected")
    assert schema is LabEvent


# ---------------------------------------------------------------------------
# list_events / is_registered / clear
# ---------------------------------------------------------------------------


def test_list_events_sorted() -> None:
    reg = _reg_with("hardware.file.detected", "hardware.device.online")
    events = reg.list_events()
    assert events == sorted(events)
    assert "hardware.file.detected" in events
    assert "hardware.device.online" in events


def test_is_registered_true_and_false() -> None:
    reg = _reg_with("hardware.file.detected")
    assert reg.is_registered("hardware.file.detected") is True
    assert reg.is_registered("hardware.device.online") is False


def test_unsubscribe_removes_handler() -> None:
    reg = _reg_with("hardware.file.detected")
    received: list[LabEvent] = []
    reg.subscribe("hardware.file.detected", received.append)
    reg.unsubscribe("hardware.file.detected", received.append)

    reg.emit("hardware.file.detected")

    assert received == []


def test_unsubscribe_noop_when_not_subscribed() -> None:
    reg = _reg_with("hardware.file.detected")
    # Should not raise even if handler was never registered
    reg.unsubscribe("hardware.file.detected", lambda e: None)
    reg.unsubscribe("hardware.device.online", lambda e: None)


def test_clear_empties_registry() -> None:
    reg = _reg_with("hardware.file.detected", "hardware.device.online")
    received: list[LabEvent] = []
    reg.subscribe("hardware.file.detected", received.append)

    reg.clear()

    assert reg.list_events() == []
    assert not reg.is_registered("hardware.file.detected")
    # After clear, handlers also gone — re-register and emit produces no old calls
    reg.register("hardware.file.detected")
    reg.emit("hardware.file.detected")
    assert received == []  # handler was cleared
