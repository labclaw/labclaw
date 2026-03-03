"""Tests for proactive engine — triggers, commitments, event matching."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from labclaw.core.event_bus import EventBus
from labclaw.core.events import EventRegistry
from labclaw.core.proactive import (
    Commitment,
    CommitmentStatus,
    ProactiveEngine,
    Trigger,
)
from labclaw.core.schemas import EventName, LabEvent, Layer


def _make_event(name: str = "infra.test.action", payload: dict | None = None) -> LabEvent:
    return LabEvent(
        event_name=EventName.parse(name),
        source_layer=Layer.INFRA,
        payload=payload or {},
    )


# ---------------------------------------------------------------------------
# Trigger schema
# ---------------------------------------------------------------------------


class TestTrigger:
    def test_defaults(self) -> None:
        t = Trigger(name="test-trigger", event_pattern="infra.*.action")
        assert t.enabled is True
        assert t.cooldown_seconds == 0.0
        assert t.condition == "True"
        assert t.trigger_id

    def test_custom_values(self) -> None:
        t = Trigger(
            name="custom",
            event_pattern="memory.*.*",
            condition="payload.get('size') > 100",
            cooldown_seconds=30.0,
            action="analyze-data",
        )
        assert t.cooldown_seconds == 30.0
        assert t.action == "analyze-data"


# ---------------------------------------------------------------------------
# Commitment schema
# ---------------------------------------------------------------------------


class TestCommitment:
    def test_defaults(self) -> None:
        c = Commitment(description="Submit report")
        assert c.status == CommitmentStatus.PENDING
        assert c.due_at is None
        assert c.commitment_id

    def test_with_due_date(self) -> None:
        due = datetime(2026, 12, 31, tzinfo=UTC)
        c = Commitment(description="Year-end review", due_at=due, assigned_to="alice")
        assert c.due_at == due
        assert c.assigned_to == "alice"


# ---------------------------------------------------------------------------
# ProactiveEngine — triggers
# ---------------------------------------------------------------------------


class TestProactiveEngineTriggers:
    def test_register_and_list(self) -> None:
        bus = EventBus(registry=EventRegistry())
        engine = ProactiveEngine(event_bus=bus)
        t = Trigger(name="t1", event_pattern="infra.*.*")
        engine.register_trigger(t)
        assert len(engine.list_triggers()) == 1
        assert engine.get_trigger(t.trigger_id) is not None

    def test_remove_trigger(self) -> None:
        bus = EventBus(registry=EventRegistry())
        engine = ProactiveEngine(event_bus=bus)
        t = Trigger(name="t1", event_pattern="*")
        engine.register_trigger(t)
        engine.remove_trigger(t.trigger_id)
        assert len(engine.list_triggers()) == 0

    def test_remove_nonexistent_raises(self) -> None:
        bus = EventBus(registry=EventRegistry())
        engine = ProactiveEngine(event_bus=bus)
        with pytest.raises(KeyError, match="not found"):
            engine.remove_trigger("ghost")

    def test_trigger_fires_on_matching_event(self) -> None:
        bus = EventBus(registry=EventRegistry())
        engine = ProactiveEngine(event_bus=bus)
        t = Trigger(name="match", event_pattern="infra.test.action")
        engine.register_trigger(t)

        event = _make_event("infra.test.action")
        fired = engine.on_event(event)
        assert t.trigger_id in fired

    def test_trigger_does_not_fire_on_mismatch(self) -> None:
        bus = EventBus(registry=EventRegistry())
        engine = ProactiveEngine(event_bus=bus)
        t = Trigger(name="no-match", event_pattern="memory.*.action")
        engine.register_trigger(t)

        event = _make_event("infra.test.action")
        fired = engine.on_event(event)
        assert len(fired) == 0

    def test_wildcard_pattern(self) -> None:
        bus = EventBus(registry=EventRegistry())
        engine = ProactiveEngine(event_bus=bus)
        t = Trigger(name="wildcard", event_pattern="infra.*.*")
        engine.register_trigger(t)

        event = _make_event("infra.anything.happens")
        fired = engine.on_event(event)
        assert t.trigger_id in fired

    def test_star_matches_all(self) -> None:
        bus = EventBus(registry=EventRegistry())
        engine = ProactiveEngine(event_bus=bus)
        t = Trigger(name="all", event_pattern="*")
        engine.register_trigger(t)

        event = _make_event("memory.graph.updated")
        fired = engine.on_event(event)
        assert t.trigger_id in fired

    def test_disabled_trigger_does_not_fire(self) -> None:
        bus = EventBus(registry=EventRegistry())
        engine = ProactiveEngine(event_bus=bus)
        t = Trigger(name="disabled", event_pattern="*", enabled=False)
        engine.register_trigger(t)

        event = _make_event()
        fired = engine.on_event(event)
        assert len(fired) == 0

    def test_condition_filters_events(self) -> None:
        bus = EventBus(registry=EventRegistry())
        engine = ProactiveEngine(event_bus=bus)
        t = Trigger(
            name="conditional",
            event_pattern="infra.*.*",
            condition="payload.get('size', 0) > 100",
        )
        engine.register_trigger(t)

        small = _make_event(payload={"size": 50})
        assert len(engine.on_event(small)) == 0

        big = _make_event(payload={"size": 200})
        assert len(engine.on_event(big)) == 1

    def test_bad_condition_returns_false(self) -> None:
        bus = EventBus(registry=EventRegistry())
        engine = ProactiveEngine(event_bus=bus)
        t = Trigger(name="bad", event_pattern="*", condition="1/0")
        engine.register_trigger(t)

        event = _make_event()
        fired = engine.on_event(event)
        assert len(fired) == 0

    def test_cooldown_prevents_spam(self) -> None:
        bus = EventBus(registry=EventRegistry())
        engine = ProactiveEngine(event_bus=bus)
        t = Trigger(name="cool", event_pattern="*", cooldown_seconds=3600)
        engine.register_trigger(t)

        event = _make_event()
        first = engine.on_event(event)
        assert len(first) == 1

        second = engine.on_event(event)
        assert len(second) == 0

    def test_no_cooldown_fires_every_time(self) -> None:
        bus = EventBus(registry=EventRegistry())
        engine = ProactiveEngine(event_bus=bus)
        t = Trigger(name="no-cool", event_pattern="*", cooldown_seconds=0)
        engine.register_trigger(t)

        event = _make_event()
        assert len(engine.on_event(event)) == 1
        assert len(engine.on_event(event)) == 1

    def test_empty_condition_treated_as_true(self) -> None:
        bus = EventBus(registry=EventRegistry())
        engine = ProactiveEngine(event_bus=bus)
        t = Trigger(name="empty-cond", event_pattern="*", condition="")
        engine.register_trigger(t)

        event = _make_event()
        assert len(engine.on_event(event)) == 1

    def test_trigger_emits_event(self) -> None:
        bus = EventBus(registry=EventRegistry())
        engine = ProactiveEngine(event_bus=bus)
        t = Trigger(name="emitter", event_pattern="infra.test.action")
        engine.register_trigger(t)

        captured: list[str] = []
        from labclaw.core.events import event_registry

        def handler(e):  # type: ignore[no-untyped-def]
            captured.append(e.event_name.full)

        event_registry.subscribe("infra.proactive.trigger_fired", handler)
        try:
            engine.on_event(_make_event())
            assert "infra.proactive.trigger_fired" in captured
        finally:
            event_registry.unsubscribe("infra.proactive.trigger_fired", handler)


# ---------------------------------------------------------------------------
# ProactiveEngine — commitments
# ---------------------------------------------------------------------------


class TestProactiveEngineCommitments:
    def test_add_and_get(self) -> None:
        bus = EventBus(registry=EventRegistry())
        engine = ProactiveEngine(event_bus=bus)
        c = Commitment(description="Submit paper")
        cid = engine.add_commitment(c)
        assert engine.get_commitment(cid) is not None

    def test_get_nonexistent_returns_none(self) -> None:
        bus = EventBus(registry=EventRegistry())
        engine = ProactiveEngine(event_bus=bus)
        assert engine.get_commitment("ghost") is None

    def test_fulfill_commitment(self) -> None:
        bus = EventBus(registry=EventRegistry())
        engine = ProactiveEngine(event_bus=bus)
        c = Commitment(description="Write tests")
        cid = engine.add_commitment(c)
        fulfilled = engine.fulfill_commitment(cid)
        assert fulfilled.status == CommitmentStatus.FULFILLED

    def test_fulfill_nonexistent_raises(self) -> None:
        bus = EventBus(registry=EventRegistry())
        engine = ProactiveEngine(event_bus=bus)
        with pytest.raises(KeyError, match="not found"):
            engine.fulfill_commitment("ghost")

    def test_list_commitments_all(self) -> None:
        bus = EventBus(registry=EventRegistry())
        engine = ProactiveEngine(event_bus=bus)
        engine.add_commitment(Commitment(description="a"))
        engine.add_commitment(Commitment(description="b"))
        assert len(engine.list_commitments()) == 2

    def test_list_commitments_by_status(self) -> None:
        bus = EventBus(registry=EventRegistry())
        engine = ProactiveEngine(event_bus=bus)
        c1 = Commitment(description="pending")
        c2 = Commitment(description="done")
        engine.add_commitment(c1)
        cid2 = engine.add_commitment(c2)
        engine.fulfill_commitment(cid2)

        pending = engine.list_commitments(status=CommitmentStatus.PENDING)
        assert len(pending) == 1
        assert pending[0].description == "pending"

    def test_check_overdue(self) -> None:
        bus = EventBus(registry=EventRegistry())
        engine = ProactiveEngine(event_bus=bus)
        past = datetime.now(UTC) - timedelta(hours=1)
        c = Commitment(description="late", due_at=past)
        engine.add_commitment(c)

        overdue = engine.check_commitments()
        assert len(overdue) == 1
        assert overdue[0].status == CommitmentStatus.OVERDUE

    def test_check_not_overdue(self) -> None:
        bus = EventBus(registry=EventRegistry())
        engine = ProactiveEngine(event_bus=bus)
        future = datetime.now(UTC) + timedelta(hours=24)
        c = Commitment(description="future", due_at=future)
        engine.add_commitment(c)

        overdue = engine.check_commitments()
        assert len(overdue) == 0

    def test_check_no_due_date_not_overdue(self) -> None:
        bus = EventBus(registry=EventRegistry())
        engine = ProactiveEngine(event_bus=bus)
        c = Commitment(description="no-due")
        engine.add_commitment(c)

        overdue = engine.check_commitments()
        assert len(overdue) == 0

    def test_fulfilled_not_checked_for_overdue(self) -> None:
        bus = EventBus(registry=EventRegistry())
        engine = ProactiveEngine(event_bus=bus)
        past = datetime.now(UTC) - timedelta(hours=1)
        c = Commitment(description="done-past", due_at=past)
        cid = engine.add_commitment(c)
        engine.fulfill_commitment(cid)

        overdue = engine.check_commitments()
        assert len(overdue) == 0

    def test_overdue_emits_event(self) -> None:
        bus = EventBus(registry=EventRegistry())
        engine = ProactiveEngine(event_bus=bus)
        past = datetime.now(UTC) - timedelta(hours=1)
        c = Commitment(description="emit-test", due_at=past)
        engine.add_commitment(c)

        captured: list[str] = []
        from labclaw.core.events import event_registry

        def handler(e):  # type: ignore[no-untyped-def]
            captured.append(e.event_name.full)

        event_registry.subscribe("infra.proactive.commitment_overdue", handler)
        try:
            engine.check_commitments()
            assert "infra.proactive.commitment_overdue" in captured
        finally:
            event_registry.unsubscribe("infra.proactive.commitment_overdue", handler)


# ---------------------------------------------------------------------------
# ProactiveEngine — lifecycle
# ---------------------------------------------------------------------------


class TestProactiveEngineLifecycle:
    @pytest.mark.asyncio
    async def test_start_subscribes_to_bus(self) -> None:
        bus = EventBus(registry=EventRegistry())
        engine = ProactiveEngine(event_bus=bus)
        await engine.start()
        assert engine._running is True
        assert engine._handle_event in bus._handlers.get("*", [])
        await engine.stop()

    @pytest.mark.asyncio
    async def test_stop_unsubscribes(self) -> None:
        bus = EventBus(registry=EventRegistry())
        engine = ProactiveEngine(event_bus=bus)
        await engine.start()
        await engine.stop()
        assert engine._running is False
        assert engine._handle_event not in bus._handlers.get("*", [])

    @pytest.mark.asyncio
    async def test_stop_without_start(self) -> None:
        bus = EventBus(registry=EventRegistry())
        engine = ProactiveEngine(event_bus=bus)
        await engine.stop()  # should not raise

    @pytest.mark.asyncio
    async def test_pattern_matching_static(self) -> None:
        assert ProactiveEngine._matches_pattern("infra.*.*", "infra.test.action")
        assert not ProactiveEngine._matches_pattern("memory.*.*", "infra.test.action")
        assert ProactiveEngine._matches_pattern("*", "anything.goes.here")
        assert ProactiveEngine._matches_pattern("infra.test.*", "infra.test.anything")

    @pytest.mark.asyncio
    async def test_trigger_enqueues_task_when_queue_provided(self) -> None:
        from labclaw.core.task_queue import TaskQueue

        bus = EventBus(registry=EventRegistry())
        q = TaskQueue()
        await q.init_db()
        try:
            engine = ProactiveEngine(event_bus=bus, task_queue=q)
            t = Trigger(name="enqueue-test", event_pattern="*", action="run-analysis")
            engine.register_trigger(t)

            event = _make_event()
            engine.on_event(event)
            # Let the enqueue task run
            await asyncio.sleep(0.05)

            tasks = await q.list_tasks()
            assert len(tasks) == 1
            assert tasks[0].name == "run-analysis"
        finally:
            await q.close()

    def test_handle_event_delegates_to_on_event(self) -> None:
        bus = EventBus(registry=EventRegistry())
        engine = ProactiveEngine(event_bus=bus)
        t = Trigger(name="wrapper-test", event_pattern="*")
        engine.register_trigger(t)

        event = _make_event()
        engine._handle_event(event)
        # _handle_event delegates to on_event which fires the trigger
        assert t.trigger_id in engine._last_fired

    @pytest.mark.asyncio
    async def test_stop_cancels_check_task(self) -> None:
        bus = EventBus(registry=EventRegistry())
        engine = ProactiveEngine(event_bus=bus)
        await engine.start()
        assert engine._check_task is not None
        await engine.stop()
        assert engine._check_task is None

    @pytest.mark.asyncio
    async def test_start_creates_commitment_check_loop(self) -> None:
        bus = EventBus(registry=EventRegistry())
        engine = ProactiveEngine(event_bus=bus, commitment_check_interval=0.05)
        past = datetime.now(UTC) - timedelta(hours=1)
        engine.add_commitment(Commitment(description="overdue-loop", due_at=past))

        await engine.start()
        await asyncio.sleep(0.15)
        await engine.stop()

        overdue = engine.list_commitments(status=CommitmentStatus.OVERDUE)
        assert len(overdue) == 1
        assert overdue[0].description == "overdue-loop"

    def test_on_event_no_loop_logs_warning(self) -> None:
        """Trigger with action should not crash when no event loop is running."""
        from labclaw.core.task_queue import TaskQueue

        bus = EventBus(registry=EventRegistry())
        q = TaskQueue()
        engine = ProactiveEngine(event_bus=bus, task_queue=q)
        t = Trigger(name="no-loop", event_pattern="*", action="do-stuff")
        engine.register_trigger(t)

        event = _make_event()
        fired = engine.on_event(event)
        assert t.trigger_id in fired
