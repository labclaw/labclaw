"""Proactive engine — autonomous triggers, commitment tracking.

Enables autonomous behavior: monitoring for anomalies, triggering analysis
when new data arrives, sending notifications, tracking commitments.
Bridges the event bus with the task queue for 7x24 always-on capability.
"""

from __future__ import annotations

import asyncio
import fnmatch
import logging
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from labclaw.core.event_bus import EventBus
from labclaw.core.events import event_registry
from labclaw.core.schemas import LabEvent
from labclaw.core.task_queue import TaskItem, TaskQueue

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Register events
# ---------------------------------------------------------------------------

_PROACTIVE_EVENTS = [
    "infra.proactive.trigger_fired",
    "infra.proactive.commitment_overdue",
]
for _evt in _PROACTIVE_EVENTS:
    if not event_registry.is_registered(_evt):
        event_registry.register(_evt)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class CommitmentStatus(StrEnum):
    PENDING = "pending"
    FULFILLED = "fulfilled"
    OVERDUE = "overdue"


def _uuid() -> str:
    return str(uuid.uuid4())


class Trigger(BaseModel):
    """Event-driven trigger that enqueues tasks when conditions are met."""

    trigger_id: str = Field(default_factory=_uuid)
    name: str
    event_pattern: str
    condition: str = "True"
    action: str = ""
    enabled: bool = True
    cooldown_seconds: float = 0.0


class Commitment(BaseModel):
    """A tracked promise or obligation."""

    commitment_id: str = Field(default_factory=_uuid)
    description: str
    due_at: datetime | None = None
    status: CommitmentStatus = CommitmentStatus.PENDING
    created_by: str = ""
    assigned_to: str = ""


# ---------------------------------------------------------------------------
# ProactiveEngine
# ---------------------------------------------------------------------------


class ProactiveEngine:
    """Autonomous engine that monitors events and manages commitments."""

    def __init__(
        self,
        event_bus: EventBus,
        task_queue: TaskQueue | None = None,
        *,
        commitment_check_interval: float = 60.0,
    ) -> None:
        self._event_bus = event_bus
        self._task_queue = task_queue
        self._commitment_check_interval = commitment_check_interval
        self._triggers: dict[str, Trigger] = {}
        self._commitments: dict[str, Commitment] = {}
        self._last_fired: dict[str, datetime] = {}
        self._running = False
        self._check_task: asyncio.Task[None] | None = None

    def _handle_event(self, event: LabEvent) -> None:
        """Event bus callback — delegates to on_event, discards return."""
        self.on_event(event)

    def register_trigger(self, trigger: Trigger) -> None:
        """Register an event-driven trigger."""
        self._triggers[trigger.trigger_id] = trigger

    def remove_trigger(self, trigger_id: str) -> None:
        """Remove a trigger by ID. Raises KeyError if not found."""
        if trigger_id not in self._triggers:
            raise KeyError(f"Trigger {trigger_id!r} not found")
        del self._triggers[trigger_id]

    def get_trigger(self, trigger_id: str) -> Trigger | None:
        """Get a trigger by ID."""
        return self._triggers.get(trigger_id)

    def list_triggers(self) -> list[Trigger]:
        """List all registered triggers."""
        return list(self._triggers.values())

    def on_event(self, event: LabEvent) -> list[str]:
        """Evaluate triggers against an event. Returns list of fired trigger IDs."""
        fired: list[str] = []
        event_name = event.event_name.full

        for trigger in self._triggers.values():
            if not trigger.enabled:
                continue
            if not self._matches_pattern(trigger.event_pattern, event_name):
                continue
            if not self._evaluate_condition(trigger.condition, event):
                continue
            if self._in_cooldown(trigger):
                continue

            self._last_fired[trigger.trigger_id] = datetime.now(UTC)
            fired.append(trigger.trigger_id)

            if self._task_queue and trigger.action:
                task = TaskItem(name=trigger.action, args={"trigger_id": trigger.trigger_id})
                try:
                    asyncio.get_running_loop().create_task(self._task_queue.enqueue(task))
                except RuntimeError:
                    logger.warning(
                        "No running event loop — cannot enqueue action %r", trigger.action
                    )

            event_registry.emit(
                "infra.proactive.trigger_fired",
                payload={
                    "trigger_id": trigger.trigger_id,
                    "trigger_name": trigger.name,
                    "event_name": event_name,
                },
            )

        return fired

    def add_commitment(self, commitment: Commitment) -> str:
        """Track a new commitment. Returns commitment_id."""
        self._commitments[commitment.commitment_id] = commitment
        return commitment.commitment_id

    def get_commitment(self, commitment_id: str) -> Commitment | None:
        """Get a commitment by ID."""
        return self._commitments.get(commitment_id)

    def fulfill_commitment(self, commitment_id: str) -> Commitment:
        """Mark a commitment as fulfilled. Raises KeyError if not found."""
        if commitment_id not in self._commitments:
            raise KeyError(f"Commitment {commitment_id!r} not found")
        c = self._commitments[commitment_id]
        updated = c.model_copy(update={"status": CommitmentStatus.FULFILLED})
        self._commitments[commitment_id] = updated
        return updated

    def list_commitments(self, status: CommitmentStatus | None = None) -> list[Commitment]:
        """List commitments, optionally filtered by status."""
        if status is None:
            return list(self._commitments.values())
        return [c for c in self._commitments.values() if c.status == status]

    def check_commitments(self) -> list[Commitment]:
        """Find overdue commitments and emit alerts."""
        now = datetime.now(UTC)
        overdue: list[Commitment] = []

        for cid, commitment in self._commitments.items():
            if commitment.status != CommitmentStatus.PENDING:
                continue
            if commitment.due_at is None:
                continue
            if commitment.due_at <= now:
                updated = commitment.model_copy(update={"status": CommitmentStatus.OVERDUE})
                self._commitments[cid] = updated
                overdue.append(updated)

                event_registry.emit(
                    "infra.proactive.commitment_overdue",
                    payload={
                        "commitment_id": cid,
                        "description": commitment.description,
                    },
                )

        return overdue

    async def start(self) -> None:
        """Start the proactive engine — subscribe to event bus."""
        self._running = True
        self._event_bus.subscribe("*", self._handle_event)
        self._check_task = asyncio.create_task(self._commitment_check_loop())

    async def stop(self) -> None:
        """Stop the proactive engine — unsubscribe from event bus."""
        self._running = False
        try:
            self._event_bus.unsubscribe("*", self._handle_event)
        except ValueError:
            pass
        if self._check_task:
            self._check_task.cancel()
            try:
                await self._check_task
            except asyncio.CancelledError:
                pass
            self._check_task = None

    async def _commitment_check_loop(self) -> None:
        """Periodically check for overdue commitments."""
        while self._running:
            await asyncio.sleep(self._commitment_check_interval)
            if not self._running:
                break
            self.check_commitments()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _matches_pattern(pattern: str, event_name: str) -> bool:
        """Match event name against a pattern with wildcard support."""
        return fnmatch.fnmatch(event_name, pattern)

    @staticmethod
    def _evaluate_condition(condition: str, event: LabEvent) -> bool:
        """Evaluate a condition string against an event.

        Supports simple Python expressions with access to event payload.
        """
        if condition == "True" or not condition:
            return True
        try:
            safe_globals: dict[str, Any] = {"__builtins__": {}}
            safe_locals = {
                "payload": event.payload,
                "event_name": event.event_name.full,
                "source_layer": str(event.source_layer),
            }
            return bool(eval(condition, safe_globals, safe_locals))  # noqa: S307  # nosec B307
        except Exception:
            logger.warning("Condition evaluation failed: %r", condition, exc_info=True)
            return False

    def _in_cooldown(self, trigger: Trigger) -> bool:
        """Check if a trigger is in cooldown period."""
        if trigger.cooldown_seconds <= 0:
            return False
        last = self._last_fired.get(trigger.trigger_id)
        if last is None:
            return False
        elapsed = (datetime.now(UTC) - last).total_seconds()
        return elapsed < trigger.cooldown_seconds
