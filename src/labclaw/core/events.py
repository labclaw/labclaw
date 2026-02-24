"""Event registry — layers register their own events, central bus dispatches.

Spec: docs/specs/cross-foundations.md (Event Registry section)
Design doc: section 3 (Architecture), all layers emit events
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import Any

from labclaw.core.schemas import EventName, LabEvent, Layer

logger = logging.getLogger(__name__)


class EventRegistry:
    """Central registry for event types. Layers register their own events at import time."""

    def __init__(self) -> None:
        self._schemas: dict[str, type[LabEvent]] = {}
        self._handlers: dict[str, list[Callable[[LabEvent], None]]] = {}
        self._lock = threading.Lock()

    def register(self, name: str, schema: type[LabEvent] | None = None) -> None:
        """Register an event type by name.

        Args:
            name: Event name in {layer}.{module}.{action} format.
            schema: Optional Pydantic model subclass for this event's payload.
        """
        # Validate name format
        EventName.parse(name)

        with self._lock:
            if name in self._schemas:
                raise ValueError(f"Event {name!r} already registered")
            self._schemas[name] = schema or LabEvent
        logger.debug("Registered event: %s", name)

    def emit(self, name: str, payload: dict[str, Any] | None = None, **kwargs: Any) -> LabEvent:
        """Create and dispatch an event.

        Args:
            name: Registered event name.
            payload: Event-specific data.
            **kwargs: Additional LabEvent fields (correlation_id, actor_id, etc.).

        Returns:
            The created LabEvent instance.
        """
        if name not in self._schemas:
            available = ", ".join(sorted(self._schemas))
            raise KeyError(f"Event {name!r} not registered. Available: {available}")

        parsed = EventName.parse(name)
        source_layer = _resolve_layer(parsed.layer)

        event = LabEvent(
            event_name=parsed,
            source_layer=source_layer,
            payload=payload or {},
            **kwargs,
        )

        # Copy handler lists under lock before iterating
        with self._lock:
            handlers = list(self._handlers.get(name, []))
            wildcards = list(self._handlers.get("*", []))

        # Dispatch to handlers
        for handler in handlers:
            try:
                handler(event)
            except Exception:
                logger.exception("Handler error for event %s", name)

        # Also dispatch to wildcard handlers
        for handler in wildcards:
            try:
                handler(event)
            except Exception:
                logger.exception("Wildcard handler error for event %s", name)

        return event

    def subscribe(self, name: str, handler: Callable[[LabEvent], None]) -> None:
        """Subscribe a handler to an event name. Use '*' for all events."""
        with self._lock:
            self._handlers.setdefault(name, []).append(handler)

    def get_schema(self, name: str) -> type[LabEvent] | None:
        return self._schemas.get(name)

    def list_events(self) -> list[str]:
        return sorted(self._schemas)

    def is_registered(self, name: str) -> bool:
        return name in self._schemas

    def clear(self) -> None:
        """Clear all registrations and handlers. For testing only."""
        self._schemas.clear()
        self._handlers.clear()


def _resolve_layer(layer_str: str) -> Layer:
    """Map event layer string to Layer enum, with fallback."""
    try:
        return Layer(layer_str)
    except ValueError:
        # Allow non-standard layers (e.g. "session", "file") — map to INFRA
        return Layer.INFRA


# Global singleton
event_registry = EventRegistry()
