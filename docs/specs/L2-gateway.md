# L2 Gateway Spec

**Layer:** Infrastructure (L2)
**Design doc reference:** Section 3 (Architecture)

## Purpose

The gateway is the single control plane for devices, agents, and clients. It handles real-time message routing, session management, and heartbeat monitoring. For MVP, this is an in-memory message router — no actual WebSocket transport needed yet. All system events flow through the EventBus with publish/subscribe semantics.

---

## Pydantic Schemas

### GatewayMessage

```python
class GatewayMessage(BaseModel):
    """A message routed through the gateway."""
    message_id: str = Field(default_factory=_uuid)
    source: str                          # client_id of sender
    target: str | None = None            # client_id of recipient; None = broadcast
    message_type: str                    # "register" | "heartbeat" | "command" | "event" | "response"
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=_now)
```

### ConnectionInfo

```python
class ConnectionInfo(BaseModel):
    """Tracks a connected client session."""
    connection_id: str = Field(default_factory=_uuid)
    client_type: str                     # "device" | "agent" | "dashboard"
    client_id: str
    connected_at: datetime = Field(default_factory=_now)
    last_heartbeat: datetime = Field(default_factory=_now)
```

### RegistrationRequest

```python
class RegistrationRequest(BaseModel):
    """Payload for a client registration request."""
    client_id: str
    client_type: str                     # "device" | "agent" | "dashboard"
    capabilities: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
```

---

## Public Interfaces

### Gateway

In-memory message router. Routes messages between connected clients and emits infrastructure events.

```python
class Gateway:
    def __init__(self) -> None: ...

    def register_client(self, request: RegistrationRequest) -> ConnectionInfo:
        """Register a new client. Emits infra.gateway.client_registered."""

    def unregister_client(self, connection_id: str) -> None:
        """Remove a client. Emits infra.gateway.client_disconnected. Raises KeyError if not found."""

    def send(self, message: GatewayMessage) -> None:
        """Route a message to its target. Emits infra.gateway.message_routed. Raises KeyError if target not found."""

    def broadcast(self, message: GatewayMessage) -> None:
        """Deliver a message to all connected clients. Emits infra.gateway.message_routed."""

    def get_connections(self) -> list[ConnectionInfo]:
        """Return all active connections."""

    def get_connection(self, connection_id: str) -> ConnectionInfo:
        """Get a connection by ID. Raises KeyError if not found."""
```

### EventBus

Wraps EventRegistry with clean pub/sub interface. Supports wildcard (`*`) subscriptions.

```python
class EventBus:
    def __init__(self, registry: EventRegistry | None = None) -> None: ...

    def publish(self, event: LabEvent) -> None:
        """Publish an event to all matching subscribers."""

    def subscribe(self, event_name: str, handler: Callable[[LabEvent], None]) -> None:
        """Subscribe to events by name. Use '*' for all events."""

    def unsubscribe(self, event_name: str, handler: Callable[[LabEvent], None]) -> None:
        """Remove a handler from an event name."""
```

---

## Events

| Event Name | Payload | Emitted By |
|---|---|---|
| `infra.gateway.client_registered` | `{connection_id, client_id, client_type}` | Gateway.register_client() |
| `infra.gateway.client_disconnected` | `{connection_id, client_id, client_type}` | Gateway.unregister_client() |
| `infra.gateway.message_routed` | `{message_id, source, target, message_type}` | Gateway.send() / Gateway.broadcast() |

---

## Boundary Contracts

- Connection IDs and message IDs are UUIDs (auto-generated)
- All timestamps are timezone-aware UTC
- client_type is one of: `"device"`, `"agent"`, `"dashboard"`
- message_type is one of: `"register"`, `"heartbeat"`, `"command"`, `"event"`, `"response"`
- Events follow `{layer}.{module}.{action}` naming convention
- Gateway and EventBus are in-memory only (MVP)

## Error Conditions

| Condition | Exception | Raised By |
|---|---|---|
| Unregister nonexistent connection | `KeyError` | Gateway.unregister_client() |
| Get nonexistent connection | `KeyError` | Gateway.get_connection() |
| Send to nonexistent target | `KeyError` | Gateway.send() |
| Unsubscribe handler not registered | `ValueError` | EventBus.unsubscribe() |

## Storage

- MVP: in-memory `dict[str, ConnectionInfo]` for connections
- MVP: in-memory handler lists for message routing
- Future: Redis Streams for persistent event bus, WebSocket transport

## Acceptance Criteria

- [ ] GatewayMessage, ConnectionInfo, RegistrationRequest validate correctly
- [ ] Gateway registers/unregisters clients with events emitted
- [ ] Gateway routes targeted messages to correct client
- [ ] Gateway broadcasts messages to all connected clients
- [ ] EventBus publishes events to matching subscribers
- [ ] EventBus supports wildcard subscriptions
- [ ] EventBus unsubscribe stops delivery
- [ ] All BDD scenarios pass
