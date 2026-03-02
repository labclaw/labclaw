"""BDD step definitions for proactive engine (L2 Scheduling)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from pytest_bdd import given, parsers, then, when

from labclaw.core.event_bus import EventBus
from labclaw.core.events import EventRegistry
from labclaw.core.proactive import Commitment, CommitmentStatus, ProactiveEngine, Trigger
from labclaw.core.schemas import EventName, LabEvent, Layer


def _make_event(name: str = "infra.test.action", payload: dict | None = None) -> LabEvent:
    return LabEvent(
        event_name=EventName.parse(name),
        source_layer=Layer.INFRA,
        payload=payload or {},
    )


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------


@given("a proactive engine", target_fixture="pe_ctx")
def proactive_engine() -> dict[str, Any]:
    bus = EventBus(registry=EventRegistry())
    engine = ProactiveEngine(event_bus=bus)
    return {"engine": engine, "bus": bus, "trigger_id": None, "commitment_id": None, "fired": []}


@given(
    parsers.parse('a trigger "{name}" matching "{pattern}"'),
    target_fixture="pe_ctx",
)
def add_trigger(pe_ctx: dict[str, Any], name: str, pattern: str) -> dict[str, Any]:
    t = Trigger(name=name, event_pattern=pattern)
    pe_ctx["engine"].register_trigger(t)
    pe_ctx["trigger_id"] = t.trigger_id
    pe_ctx["trigger_name"] = name
    return pe_ctx


@given(
    parsers.parse('a disabled trigger "{name}" matching "{pattern}"'),
    target_fixture="pe_ctx",
)
def add_disabled_trigger(pe_ctx: dict[str, Any], name: str, pattern: str) -> dict[str, Any]:
    t = Trigger(name=name, event_pattern=pattern, enabled=False)
    pe_ctx["engine"].register_trigger(t)
    pe_ctx["trigger_id"] = t.trigger_id
    return pe_ctx


@given(
    parsers.parse('a trigger "{name}" matching "{pattern}" with cooldown {seconds:d} seconds'),
    target_fixture="pe_ctx",
)
def add_cooldown_trigger(
    pe_ctx: dict[str, Any], name: str, pattern: str, seconds: int
) -> dict[str, Any]:
    t = Trigger(name=name, event_pattern=pattern, cooldown_seconds=float(seconds))
    pe_ctx["engine"].register_trigger(t)
    pe_ctx["trigger_id"] = t.trigger_id
    pe_ctx["trigger_name"] = name
    return pe_ctx


@given(
    parsers.parse('a trigger "{name}" matching "{pattern}" with condition "{condition}"'),
    target_fixture="pe_ctx",
)
def add_conditional_trigger(
    pe_ctx: dict[str, Any], name: str, pattern: str, condition: str
) -> dict[str, Any]:
    t = Trigger(name=name, event_pattern=pattern, condition=condition)
    pe_ctx["engine"].register_trigger(t)
    pe_ctx["trigger_id"] = t.trigger_id
    pe_ctx["trigger_name"] = name
    return pe_ctx


@given(
    parsers.parse('a commitment "{description}" is added'),
    target_fixture="pe_ctx",
)
def add_commitment(pe_ctx: dict[str, Any], description: str) -> dict[str, Any]:
    c = Commitment(description=description)
    cid = pe_ctx["engine"].add_commitment(c)
    pe_ctx["commitment_id"] = cid
    return pe_ctx


@given(
    parsers.parse('a commitment "{description}" due {hours:d} hour ago'),
    target_fixture="pe_ctx",
)
def add_overdue_commitment(pe_ctx: dict[str, Any], description: str, hours: int) -> dict[str, Any]:
    past = datetime.now(UTC) - timedelta(hours=hours)
    c = Commitment(description=description, due_at=past)
    cid = pe_ctx["engine"].add_commitment(c)
    pe_ctx["commitment_id"] = cid
    return pe_ctx


@given(
    parsers.parse('a commitment "{description}" due in {hours:d} hours'),
    target_fixture="pe_ctx",
)
def add_future_commitment(pe_ctx: dict[str, Any], description: str, hours: int) -> dict[str, Any]:
    future = datetime.now(UTC) + timedelta(hours=hours)
    c = Commitment(description=description, due_at=future)
    cid = pe_ctx["engine"].add_commitment(c)
    pe_ctx["commitment_id"] = cid
    return pe_ctx


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when(
    parsers.parse('the event "{event_name}" occurs'),
    target_fixture="pe_ctx",
)
def event_occurs(pe_ctx: dict[str, Any], event_name: str) -> dict[str, Any]:
    event = _make_event(event_name)
    fired = pe_ctx["engine"].on_event(event)
    pe_ctx["fired"] = fired
    return pe_ctx


@when(
    parsers.parse('the event "{event_name}" occurs twice'),
    target_fixture="pe_ctx",
)
def event_occurs_twice(pe_ctx: dict[str, Any], event_name: str) -> dict[str, Any]:
    event = _make_event(event_name)
    first = pe_ctx["engine"].on_event(event)
    second = pe_ctx["engine"].on_event(event)
    pe_ctx["fired"] = first
    pe_ctx["fired_second"] = second
    return pe_ctx


@when(
    parsers.parse('the event "{event_name}" occurs with size {size:d}'),
    target_fixture="pe_ctx",
)
def event_with_size(pe_ctx: dict[str, Any], event_name: str, size: int) -> dict[str, Any]:
    event = _make_event(event_name, payload={"size": size})
    fired = pe_ctx["engine"].on_event(event)
    pe_ctx["fired"] = fired
    return pe_ctx


@when("I fulfill the commitment", target_fixture="pe_ctx")
def fulfill(pe_ctx: dict[str, Any]) -> dict[str, Any]:
    pe_ctx["engine"].fulfill_commitment(pe_ctx["commitment_id"])
    return pe_ctx


@when("I check commitments", target_fixture="pe_ctx")
def check_commitments(pe_ctx: dict[str, Any]) -> dict[str, Any]:
    overdue = pe_ctx["engine"].check_commitments()
    pe_ctx["overdue"] = overdue
    return pe_ctx


@when(
    parsers.parse('I remove the trigger "{name}"'),
    target_fixture="pe_ctx",
)
def remove_trigger(pe_ctx: dict[str, Any], name: str) -> dict[str, Any]:
    engine = pe_ctx["engine"]
    for t in engine.list_triggers():
        if t.name == name:
            engine.remove_trigger(t.trigger_id)
            break
    return pe_ctx


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------


@then(parsers.parse('the trigger "{name}" fires'))
def check_trigger_fired(pe_ctx: dict[str, Any], name: str) -> None:
    assert len(pe_ctx["fired"]) > 0, "Expected trigger to fire"


@then("no triggers fire")
def check_no_triggers(pe_ctx: dict[str, Any]) -> None:
    assert len(pe_ctx["fired"]) == 0, f"Expected no triggers, got {pe_ctx['fired']}"


@then("the trigger fires only once")
def check_fired_once(pe_ctx: dict[str, Any]) -> None:
    assert len(pe_ctx["fired"]) == 1
    assert len(pe_ctx.get("fired_second", [])) == 0


@then(parsers.parse('the commitment status is "{status}"'))
def check_commitment_status(pe_ctx: dict[str, Any], status: str) -> None:
    c = pe_ctx["engine"].get_commitment(pe_ctx["commitment_id"])
    assert c is not None
    assert c.status == CommitmentStatus(status)


@then("the commitment is overdue")
def check_overdue(pe_ctx: dict[str, Any]) -> None:
    assert len(pe_ctx["overdue"]) > 0


@then("no commitments are overdue")
def check_not_overdue(pe_ctx: dict[str, Any]) -> None:
    assert len(pe_ctx["overdue"]) == 0


@then("no triggers are registered")
def check_no_triggers_registered(pe_ctx: dict[str, Any]) -> None:
    assert len(pe_ctx["engine"].list_triggers()) == 0
