from __future__ import annotations

from labclaw.core.events import event_registry
from labclaw.edge.session_chronicle import SessionChronicle


def _ensure_session_events() -> None:
    for name in (
        "session.chronicle.started",
        "session.recording.added",
        "session.chronicle.ended",
    ):
        if not event_registry.is_registered(name):
            event_registry.register(name)


def test_session_chronicle_capacity_does_not_crash_on_active_eviction() -> None:
    _ensure_session_events()
    chronicle = SessionChronicle(max_sessions=1)

    first = chronicle.start_session(operator_id="op-1")
    second = chronicle.start_session(operator_id="op-2")

    assert first.node_id != second.node_id
    sessions = chronicle.list_sessions()
    assert len(sessions) == 1
    assert sessions[0].node_id == second.node_id


def test_session_chronicle_prefers_eviction_of_completed_sessions() -> None:
    _ensure_session_events()
    chronicle = SessionChronicle(max_sessions=1)

    first = chronicle.start_session(operator_id="op-1")
    chronicle.end_session(first.node_id)
    second = chronicle.start_session(operator_id="op-2")

    assert first.node_id != second.node_id
    sessions = chronicle.list_sessions()
    assert len(sessions) == 1
    assert sessions[0].node_id == second.node_id
