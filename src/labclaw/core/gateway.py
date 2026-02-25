"""Gateway — single control plane for devices, agents, and clients.

In-memory message router for MVP. Routes messages between connected clients,
manages sessions, and emits infrastructure events.

Spec: docs/specs/L2-gateway.md
Design doc: section 3 (Architecture)
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from labclaw.core.events import event_registry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class GatewayMessage(BaseModel):
    """A message routed through the gateway."""

    message_id: str = Field(default_factory=_uuid)
    source: str
    target: str | None = None
    message_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=_now)


class ConnectionInfo(BaseModel):
    """Tracks a connected client session."""

    connection_id: str = Field(default_factory=_uuid)
    client_type: str
    client_id: str
    connected_at: datetime = Field(default_factory=_now)
    last_heartbeat: datetime = Field(default_factory=_now)


class RegistrationRequest(BaseModel):
    """Payload for a client registration request."""

    client_id: str
    client_type: str
    capabilities: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Register gateway events at import time
# ---------------------------------------------------------------------------

_GATEWAY_EVENTS = [
    "infra.gateway.client_registered",
    "infra.gateway.client_disconnected",
    "infra.gateway.message_routed",
]

for _evt in _GATEWAY_EVENTS:
    if not event_registry.is_registered(_evt):
        event_registry.register(_evt)


# ---------------------------------------------------------------------------
# Gateway
# ---------------------------------------------------------------------------


class Gateway:
    """In-memory message router for the lab control plane."""

    def __init__(self) -> None:
        self._connections: dict[str, ConnectionInfo] = {}
        self._client_id_to_connection_id: dict[str, str] = {}
        self._message_handlers: dict[str, list[Callable[[GatewayMessage], None]]] = {}

    def register_client(self, request: RegistrationRequest) -> ConnectionInfo:
        """Register a new client connection.

        Args:
            request: Registration details including client_id and type.

        Returns:
            ConnectionInfo for the new connection.
        """
        # Evict stale connection if the same client_id reconnects
        old_conn_id = self._client_id_to_connection_id.pop(request.client_id, None)
        if old_conn_id is not None:
            self._connections.pop(old_conn_id, None)
            logger.info("Evicted stale connection %s for client %s", old_conn_id, request.client_id)

        conn = ConnectionInfo(
            client_type=request.client_type,
            client_id=request.client_id,
        )
        self._connections[conn.connection_id] = conn
        self._client_id_to_connection_id[request.client_id] = conn.connection_id
        logger.info(
            "Client registered: %s (%s) -> %s",
            request.client_id,
            request.client_type,
            conn.connection_id,
        )

        event_registry.emit(
            "infra.gateway.client_registered",
            payload={
                "connection_id": conn.connection_id,
                "client_id": request.client_id,
                "client_type": request.client_type,
            },
        )
        return conn

    def unregister_client(self, connection_id: str) -> None:
        """Remove a client connection.

        Args:
            connection_id: The connection to remove.

        Raises:
            KeyError: If connection_id is not found.
        """
        conn = self._get_connection_or_by_client_id(connection_id)
        del self._connections[conn.connection_id]
        self._client_id_to_connection_id.pop(conn.client_id, None)
        self._message_handlers.pop(conn.client_id, None)
        logger.info(
            "Client disconnected: %s (%s)",
            conn.client_id,
            conn.connection_id,
        )

        event_registry.emit(
            "infra.gateway.client_disconnected",
            payload={
                "connection_id": conn.connection_id,
                "client_id": conn.client_id,
                "client_type": conn.client_type,
            },
        )

    def send(self, message: GatewayMessage) -> None:
        """Route a targeted message to its recipient.

        Args:
            message: The message to route. message.target must be set.

        Raises:
            KeyError: If the target client is not connected.
        """
        if message.target is None:
            raise ValueError("Cannot send a message without a target; use broadcast()")

        if message.target not in self._client_id_to_connection_id:
            raise KeyError(f"Target client {message.target!r} is not connected")

        # Deliver to handlers registered for the target client_id
        handlers = self._message_handlers.get(message.target, [])
        for handler in handlers:
            try:
                handler(message)
            except Exception:
                logger.exception("Handler error routing message %s", message.message_id)

        event_registry.emit(
            "infra.gateway.message_routed",
            payload={
                "message_id": message.message_id,
                "source": message.source,
                "target": message.target,
                "message_type": message.message_type,
            },
        )

    def broadcast(self, message: GatewayMessage) -> None:
        """Deliver a message to all connected clients.

        Args:
            message: The message to broadcast. target is ignored.
        """
        for client_id, handlers in self._message_handlers.items():
            for handler in handlers:
                try:
                    handler(message)
                except Exception:
                    logger.exception("Handler error broadcasting to %s", client_id)

        event_registry.emit(
            "infra.gateway.message_routed",
            payload={
                "message_id": message.message_id,
                "source": message.source,
                "target": None,
                "message_type": message.message_type,
            },
        )

    def get_connections(self) -> list[ConnectionInfo]:
        """Return all active connections."""
        return list(self._connections.values())

    def get_connection(self, connection_id: str) -> ConnectionInfo:
        """Get a connection by ID.

        Raises:
            KeyError: If connection_id is not found.
        """
        try:
            return self._connections[connection_id]
        except KeyError:
            raise KeyError(f"Connection {connection_id!r} not found") from None

    def subscribe_client(self, client_id: str, handler: Callable[[GatewayMessage], None]) -> None:
        """Register a message handler for a client.

        Args:
            client_id: The client to receive messages for.
            handler: Callback invoked when a message targets this client.
        """
        self._message_handlers.setdefault(client_id, []).append(handler)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_connection_or_by_client_id(self, id_: str) -> ConnectionInfo:
        """Look up by connection_id first, then try client_id."""
        if id_ in self._connections:
            return self._connections[id_]
        if id_ in self._client_id_to_connection_id:
            conn_id = self._client_id_to_connection_id[id_]
            return self._connections[conn_id]
        raise KeyError(f"Connection or client {id_!r} not found")
