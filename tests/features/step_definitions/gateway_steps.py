"""BDD step definitions for Layer 2 — Gateway and Event Bus.

Provides Given/When/Then steps for gateway_registration.feature
and event_bus.feature.
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, then, when

from labclaw.core.event_bus import EventBus
from labclaw.core.events import event_registry
from labclaw.core.gateway import (
    ConnectionInfo,
    Gateway,
    GatewayMessage,
    RegistrationRequest,
)
from labclaw.core.schemas import LabEvent
from tests.features.conftest import EventCapture

# ---------------------------------------------------------------------------
# Captured messages helper
# ---------------------------------------------------------------------------


class MessageCapture:
    """Captures gateway messages for assertion."""

    def __init__(self) -> None:
        self.messages: list[GatewayMessage] = []

    def __call__(self, message: GatewayMessage) -> None:
        self.messages.append(message)


# ---------------------------------------------------------------------------
# Gateway fixtures / Given steps
# ---------------------------------------------------------------------------


@given("the gateway is initialized", target_fixture="gateway")
def gateway_initialized(event_capture: EventCapture) -> Gateway:
    """Provide a fresh Gateway and wire event capture."""
    for evt_name in event_registry.list_events():
        if evt_name.startswith("infra.gateway."):
            event_registry.subscribe(evt_name, event_capture)
    return Gateway()


@pytest.fixture()
def gateway_client_ids() -> dict[str, str]:
    """Map of client_id to connection_id for test lookup."""
    return {}


@pytest.fixture()
def message_capture() -> MessageCapture:
    """Capture routed messages."""
    return MessageCapture()


@given(
    parsers.parse('client "{client_id}" of type "{client_type}" is registered'),
    target_fixture="_gw_registered",
)
def client_is_registered(
    gateway: Gateway,
    gateway_client_ids: dict[str, str],
    message_capture: MessageCapture,
    client_id: str,
    client_type: str,
) -> ConnectionInfo:
    request = RegistrationRequest(client_id=client_id, client_type=client_type)
    conn = gateway.register_client(request)
    gateway_client_ids[client_id] = conn.connection_id
    gateway.subscribe_client(client_id, message_capture)
    return conn


# ---------------------------------------------------------------------------
# When steps — Gateway
# ---------------------------------------------------------------------------


@when(
    parsers.parse('I register a client "{client_id}" of type "{client_type}"'),
    target_fixture="registered_connection",
)
def register_client(
    gateway: Gateway,
    gateway_client_ids: dict[str, str],
    message_capture: MessageCapture,
    client_id: str,
    client_type: str,
) -> ConnectionInfo:
    request = RegistrationRequest(client_id=client_id, client_type=client_type)
    conn = gateway.register_client(request)
    gateway_client_ids[client_id] = conn.connection_id
    gateway.subscribe_client(client_id, message_capture)
    return conn


@when(parsers.parse('I unregister client "{client_id}"'))
def unregister_client(
    gateway: Gateway,
    gateway_client_ids: dict[str, str],
    client_id: str,
) -> None:
    conn_id = gateway_client_ids[client_id]
    gateway.unregister_client(conn_id)


@when(
    parsers.parse('I send a message from "{source}" to "{target}" with type "{msg_type}"'),
    target_fixture="sent_message",
)
def send_message(
    gateway: Gateway,
    source: str,
    target: str,
    msg_type: str,
) -> GatewayMessage:
    msg = GatewayMessage(source=source, target=target, message_type=msg_type)
    gateway.send(msg)
    return msg


@when(
    parsers.parse('I broadcast a message from "{source}" with type "{msg_type}"'),
    target_fixture="broadcast_message",
)
def broadcast_message(
    gateway: Gateway,
    source: str,
    msg_type: str,
) -> GatewayMessage:
    msg = GatewayMessage(source=source, message_type=msg_type)
    gateway.broadcast(msg)
    return msg


@when(
    parsers.parse('I try to send a message to nonexistent client "{client_id}"'),
    target_fixture="gw_error",
)
def try_send_to_nonexistent(gateway: Gateway, client_id: str) -> Exception | None:
    try:
        msg = GatewayMessage(source="system", target=client_id, message_type="ping")
        gateway.send(msg)
        return None
    except KeyError as exc:
        return exc


# ---------------------------------------------------------------------------
# Then steps — Gateway
# ---------------------------------------------------------------------------


@then(parsers.parse("the gateway has {count:d} connection"))
def gateway_has_n_connections_singular(gateway: Gateway, count: int) -> None:
    conns = gateway.get_connections()
    assert len(conns) == count, f"Expected {count}, got {len(conns)}"


@then(parsers.parse("the gateway has {count:d} connections"))
def gateway_has_n_connections(gateway: Gateway, count: int) -> None:
    conns = gateway.get_connections()
    assert len(conns) == count, f"Expected {count}, got {len(conns)}"


@then(parsers.parse('the connection has client_id "{client_id}"'))
def connection_has_client_id(
    registered_connection: ConnectionInfo,
    client_id: str,
) -> None:
    assert registered_connection.client_id == client_id


@then("the message is routed successfully")
def message_routed(message_capture: MessageCapture) -> None:
    assert len(message_capture.messages) > 0, "No messages were routed"


@then("the message reaches all connected clients")
def message_reaches_all(gateway: Gateway, message_capture: MessageCapture) -> None:
    conn_count = len(gateway.get_connections())
    assert len(message_capture.messages) >= conn_count, (
        f"Expected {conn_count} deliveries, got {len(message_capture.messages)}"
    )


@then(parsers.parse('the connection type is "{client_type}"'))
def connection_type_is(gateway: Gateway, client_type: str) -> None:
    conns = gateway.get_connections()
    assert len(conns) == 1
    assert conns[0].client_type == client_type, (
        f"Expected type {client_type!r}, got {conns[0].client_type!r}"
    )


@then("a KeyError is raised")
def keyerror_raised(gw_error: Exception | None) -> None:
    assert gw_error is not None, "Expected a KeyError but no exception was raised"
    assert isinstance(gw_error, KeyError), f"Expected KeyError, got {type(gw_error).__name__}"


@then("no gateway exception is raised")
def no_gateway_exception(gateway: Gateway) -> None:
    # If we got here without exception, the broadcast succeeded
    assert gateway is not None


@then("the connection has a connection_id")
def connection_has_connection_id(registered_connection: ConnectionInfo) -> None:
    assert registered_connection.connection_id
    assert len(registered_connection.connection_id) > 0


@then("the connection has a connected_at timestamp")
def connection_has_timestamp(registered_connection: ConnectionInfo) -> None:
    assert registered_connection.connected_at is not None


@then("I can retrieve the connection by its connection_id")
def retrieve_by_connection_id(
    gateway: Gateway,
    registered_connection: ConnectionInfo,
) -> None:
    conn = gateway.get_connection(registered_connection.connection_id)
    assert conn.client_id == registered_connection.client_id


# ---------------------------------------------------------------------------
# Event Bus fixtures / Given steps
# ---------------------------------------------------------------------------


@given("the event bus is initialized", target_fixture="event_bus")
def event_bus_initialized() -> EventBus:
    return EventBus()


@pytest.fixture()
def bus_capture() -> EventCapture:
    return EventCapture()


@pytest.fixture()
def wildcard_capture() -> EventCapture:
    return EventCapture()


@pytest.fixture()
def event_bus_error() -> dict:
    """Mutable container to capture errors from event bus operations."""
    return {}


@given(
    parsers.parse('a subscriber listening for "{event_name}"'),
)
def subscriber_listening(
    event_bus: EventBus,
    bus_capture: EventCapture,
    event_name: str,
) -> None:
    event_bus.subscribe(event_name, bus_capture)


@given("a wildcard subscriber listening for all events")
def wildcard_subscriber(
    event_bus: EventBus,
    wildcard_capture: EventCapture,
) -> None:
    event_bus.subscribe("*", wildcard_capture)


# ---------------------------------------------------------------------------
# When steps — Event Bus
# ---------------------------------------------------------------------------


@when(
    parsers.parse('I publish an event "{event_name}" with payload key "{key}" value "{value}"'),
    target_fixture="published_event",
)
def publish_event_with_payload(
    event_bus: EventBus,
    event_name: str,
    key: str,
    value: str,
) -> LabEvent:
    return event_bus.create_event(event_name, payload={key: value})


@when(parsers.parse('I publish an event "{event_name}"'))
def publish_event(event_bus: EventBus, event_name: str) -> LabEvent:
    return event_bus.create_event(event_name)


@when(parsers.parse('I unsubscribe from "{event_name}"'))
def unsubscribe_from(
    event_bus: EventBus,
    bus_capture: EventCapture,
    event_name: str,
) -> None:
    event_bus.unsubscribe(event_name, bus_capture)


@when(
    parsers.parse('I register event type "{event_name}"'),
    target_fixture="registered_event_name",
)
def register_event_type(event_bus: EventBus, event_name: str) -> str:
    if not event_bus._registry.is_registered(event_name):
        event_bus._registry.register(event_name)
    return event_name


@when(
    "I publish an event \"discovery.mining.complete\" with nested payload",
    target_fixture="published_event",
)
def publish_nested_payload_event(
    event_bus: EventBus,
) -> LabEvent:
    payload = {
        "results": {
            "patterns": [{"type": "trend", "confidence": 0.9}],
            "metadata": {"source": "miner-v1"},
        },
        "count": 1,
    }
    return event_bus.create_event("discovery.mining.complete", payload=payload)


@when(
    parsers.parse('I publish an event "{event_name}" with no subscribers'),
    target_fixture="orphan_event_result",
)
def publish_orphan_event(  # noqa: E501
    event_bus: EventBus,
    event_name: str,
    event_bus_error: dict,
) -> LabEvent | None:
    try:
        result = event_bus.create_event(event_name)
        return result
    except Exception as exc:
        event_bus_error["exc"] = exc
        return None


@when(
    parsers.parse('I create an event with name "{event_name}"'),
    target_fixture="created_event",
)
def create_event_for_inspection(event_bus: EventBus, event_name: str) -> LabEvent:
    return event_bus.create_event(event_name)


@when(
    parsers.parse('I try to register an event with invalid name "{bad_name}"'),
    target_fixture="registration_error",
)
def try_register_invalid_event(bad_name: str) -> Exception | None:
    from labclaw.core.events import EventRegistry as _EventRegistry
    reg = _EventRegistry()
    try:
        reg.register(bad_name)
        return None
    except (ValueError, Exception) as exc:
        return exc


@when(
    "I check 5 different actions as PI",
    target_fixture="checked_5_decisions",
)
def check_5_actions_pi(gov_engine) -> list:  # noqa: ANN001
    decisions = []
    for i in range(5):
        d = gov_engine.check(action=f"action_{i}", actor="dr_pi", role="pi")
        decisions.append(d)
    return decisions


# ---------------------------------------------------------------------------
# Then steps — Event Bus
# ---------------------------------------------------------------------------


@then("the subscriber receives the event")
def subscriber_received(bus_capture: EventCapture) -> None:
    assert len(bus_capture.events) > 0, "Subscriber received no events"


@then(parsers.parse('the event payload contains "{key}"'))
def event_payload_contains(bus_capture: EventCapture, key: str) -> None:
    event = bus_capture.last
    assert key in event.payload, f"Payload missing key {key!r}: {event.payload}"


@then(parsers.parse("the wildcard subscriber received {count:d} events"))
def wildcard_received_n(wildcard_capture: EventCapture, count: int) -> None:
    assert len(wildcard_capture.events) == count, (
        f"Expected {count}, got {len(wildcard_capture.events)}"
    )


@then(parsers.parse("the subscriber received {count:d} events"))
def subscriber_received_n(bus_capture: EventCapture, count: int) -> None:
    assert len(bus_capture.events) == count, f"Expected {count}, got {len(bus_capture.events)}"


@then(parsers.parse('the event type "{event_name}" is registered'))
def event_type_is_registered(event_bus: EventBus, event_name: str) -> None:
    assert event_bus._registry.is_registered(event_name), (
        f"Event {event_name!r} should be registered"
    )


@then(parsers.parse('the event has layer "{layer}" module "{module}" action "{action}"'))
def event_has_parts(created_event: LabEvent, layer: str, module: str, action: str) -> None:
    assert created_event.event_name.layer == layer
    assert created_event.event_name.module == module
    assert created_event.event_name.action == action


@then("the event registry lists at least 1 event")
def event_registry_has_events(event_bus: EventBus) -> None:
    events = event_bus._registry.list_events()
    assert len(events) >= 1, f"Expected >= 1 registered events, got {len(events)}"


@then("the event has a timestamp")
def event_has_timestamp(bus_capture: EventCapture) -> None:
    event = bus_capture.last
    assert event.timestamp is not None


@then("the event has an event_id")
def event_has_event_id(bus_capture: EventCapture) -> None:
    event = bus_capture.last
    assert event.event_id is not None
    assert len(event.event_id) > 0


@then("no exception is raised")
def no_exception_raised(orphan_event_result: LabEvent | None, event_bus_error: dict) -> None:
    assert "exc" not in event_bus_error, (
        f"Unexpected exception: {event_bus_error.get('exc')}"
    )


@then("a ValueError is raised")
def valueerror_raised(registration_error: Exception | None) -> None:
    assert registration_error is not None, "Expected a ValueError but no exception was raised"
    assert isinstance(registration_error, ValueError), (
        f"Expected ValueError, got {type(registration_error).__name__}: {registration_error}"
    )
