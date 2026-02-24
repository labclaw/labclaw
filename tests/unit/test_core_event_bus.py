"""Tests for EventBus in labclaw.core.event_bus.

Uses fresh EventRegistry instances for every test to prevent state leakage
between tests. Covers publish, subscribe/unsubscribe, wildcard handlers,
exception isolation, and create_event convenience method.
"""

from __future__ import annotations

import pytest

from labclaw.core.event_bus import EventBus
from labclaw.core.events import EventRegistry
from labclaw.core.schemas import EventName, LabEvent, Layer

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_bus(event_names: list[str] | None = None) -> tuple[EventBus, EventRegistry]:
    """Create a fresh EventBus backed by a fresh EventRegistry.

    Registers the given event names so tests can emit them without errors.
    """
    reg = EventRegistry()
    for name in event_names or []:
        reg.register(name)
    bus = EventBus(registry=reg)
    return bus, reg


def _lab_event(name: str = "infra.bus.test", layer: Layer = Layer.INFRA) -> LabEvent:
    """Build a minimal LabEvent."""
    return LabEvent(
        event_name=EventName.parse(name),
        source_layer=layer,
    )


# ---------------------------------------------------------------------------
# Publish and subscribe
# ---------------------------------------------------------------------------


def test_publish_calls_subscribers() -> None:
    """A subscribed handler is called once when a matching event is published."""
    bus, reg = _make_bus(["infra.bus.test"])
    received: list[LabEvent] = []
    bus.subscribe("infra.bus.test", received.append)

    event = _lab_event("infra.bus.test")
    bus.publish(event)

    assert len(received) == 1
    assert received[0].event_id == event.event_id


def test_publish_handler_exception_no_crash() -> None:
    """A handler that raises must not propagate the exception to the caller."""
    bus, _ = _make_bus()

    def bad_handler(_: LabEvent) -> None:
        raise RuntimeError("intentional failure")

    bus.subscribe("infra.bus.boom", bad_handler)
    event = _lab_event("infra.bus.boom")
    # Must not raise
    bus.publish(event)


def test_publish_wildcard_handler() -> None:
    """A handler subscribed to '*' is called for any published event."""
    bus, _ = _make_bus()
    received: list[LabEvent] = []
    bus.subscribe("*", received.append)

    e1 = _lab_event("infra.bus.alpha")
    e2 = _lab_event("infra.bus.beta")
    bus.publish(e1)
    bus.publish(e2)

    assert len(received) == 2


def test_publish_wildcard_exception_no_crash() -> None:
    """A wildcard handler that raises must not crash the publisher."""
    bus, _ = _make_bus()

    def noisy(_: LabEvent) -> None:
        raise ValueError("wildcard boom")

    bus.subscribe("*", noisy)
    # Must not raise
    bus.publish(_lab_event("infra.bus.anything"))


# ---------------------------------------------------------------------------
# Unsubscribe
# ---------------------------------------------------------------------------


def test_subscribe_and_unsubscribe() -> None:
    """After unsubscribing, the handler is no longer called on publish."""
    bus, _ = _make_bus()
    received: list[LabEvent] = []
    bus.subscribe("infra.bus.track", received.append)
    bus.unsubscribe("infra.bus.track", received.append)

    bus.publish(_lab_event("infra.bus.track"))

    assert received == []


def test_unsubscribe_not_found_raises() -> None:
    """Unsubscribing a handler that was never registered raises ValueError."""
    bus, _ = _make_bus()

    def handler(_: LabEvent) -> None:
        pass

    with pytest.raises(ValueError, match="not found"):
        bus.unsubscribe("infra.bus.missing", handler)


# ---------------------------------------------------------------------------
# create_event
# ---------------------------------------------------------------------------


def test_create_event_auto_registers() -> None:
    """create_event registers the event name if not already registered, then publishes."""
    bus, reg = _make_bus()  # no pre-registered events
    received: list[LabEvent] = []
    bus.subscribe("infra.bus.new", received.append)

    event = bus.create_event("infra.bus.new", payload={"key": "value"})

    assert reg.is_registered("infra.bus.new")
    assert event.payload == {"key": "value"}
    assert len(received) == 1


def test_create_event_non_standard_layer() -> None:
    """A layer string not in the Layer enum is mapped to Layer.INFRA."""
    bus, _ = _make_bus()

    # "custom" is not a valid Layer value
    event = bus.create_event("custom.module.action")

    assert event.source_layer == Layer.INFRA
