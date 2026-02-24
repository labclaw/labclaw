"""Common BDD step definitions shared across all layers.

Pattern for all step_definitions:
  - Import from pytest_bdd: given, when, then, parsers, scenarios
  - Fixtures return state for downstream steps
  - Use parsers.parse() for parameterized steps
"""

from __future__ import annotations

from pytest_bdd import given, parsers, then

from labclaw.core.events import EventRegistry


@given("the event registry is initialized", target_fixture="registry")
def event_registry_initialized() -> EventRegistry:
    """Provide a fresh event registry for the scenario."""
    return EventRegistry()


@then(parsers.parse('an event "{event_name}" is emitted'))
def check_event_emitted(event_capture: object, event_name: str) -> None:
    """Verify an event was emitted by name."""
    # event_capture is the EventCapture fixture from conftest
    cap = event_capture  # type: ignore[attr-defined]
    assert event_name in cap.names, (
        f"Expected event {event_name!r}, got {cap.names}"
    )


@then(parsers.parse('an event "{event_name}" is emitted with {key} "{value}"'))
def check_event_emitted_with_payload(
    event_capture: object, event_name: str, key: str, value: str
) -> None:
    """Verify an event was emitted with specific payload key/value."""
    cap = event_capture  # type: ignore[attr-defined]
    matching = [e for e in cap.events if e.event_name.full == event_name]
    assert matching, f"No events with name {event_name!r}"
    last = matching[-1]
    assert key in last.payload, f"Payload missing key {key!r}: {last.payload}"
    assert str(last.payload[key]) == value, (
        f"Expected payload[{key!r}] == {value!r}, got {last.payload[key]!r}"
    )


@then("no events are emitted")
def check_no_events(event_capture: object) -> None:
    cap = event_capture  # type: ignore[attr-defined]
    assert not cap.events, f"Expected no events, got {cap.names}"
