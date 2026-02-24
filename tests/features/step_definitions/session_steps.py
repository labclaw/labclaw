"""BDD step definitions for Session Chronicle (OBSERVE).

Provides Given/When/Then steps for session_chronicle.feature.
Tests file detection, quality checks, and session assembly.
"""

from __future__ import annotations

from pathlib import Path

from pytest_bdd import given, parsers, then, when
from watchdog.events import FileCreatedEvent

from labclaw.core.events import event_registry
from labclaw.core.graph import SessionNode
from labclaw.core.schemas import FileReference, QualityMetric
from labclaw.edge.quality import QualityChecker
from labclaw.edge.session_chronicle import SessionChronicle
from labclaw.edge.watcher import FileDetectedHandler
from tests.features.conftest import EventCapture

# ---------------------------------------------------------------------------
# Fixtures exposed as step targets
# ---------------------------------------------------------------------------


@given("the session chronicle is initialized", target_fixture="chronicle")
def session_chronicle_initialized(event_capture: EventCapture) -> SessionChronicle:
    """Provide a fresh SessionChronicle and wire event capture."""
    for evt_name in event_registry.list_events():
        if evt_name.startswith("session."):
            event_registry.subscribe(evt_name, event_capture)
    return SessionChronicle()


@given("the edge watcher is initialized", target_fixture="watcher_ctx")
def edge_watcher_initialized(event_capture: EventCapture) -> dict:
    """Provide context dict for file watcher tests (no real Observer threads)."""
    for evt_name in event_registry.list_events():
        if evt_name.startswith("hardware."):
            event_registry.subscribe(evt_name, event_capture)
    return {"handlers": {}, "watch_dirs": {}, "detected_files": []}


# ---------------------------------------------------------------------------
# Given steps
# ---------------------------------------------------------------------------


@given(
    parsers.parse('a watched directory for device "{device_id}"'),
    target_fixture="watch_dir",
)
def watched_directory(
    tmp_path: Path, watcher_ctx: dict, device_id: str
) -> Path:
    """Create a temp directory and a handler for the device."""
    watch_dir = tmp_path / f"watch_{device_id}"
    watch_dir.mkdir(parents=True, exist_ok=True)

    handler = FileDetectedHandler(device_id=device_id)
    watcher_ctx["handlers"][device_id] = handler
    watcher_ctx["watch_dirs"][device_id] = watch_dir
    return watch_dir


@given(
    parsers.parse('a file "{filename}" with {size:d} bytes of content'),
    target_fixture="test_file_ref",
)
def file_with_content(tmp_path: Path, filename: str, size: int) -> FileReference:
    """Create a file with the given size."""
    fpath = tmp_path / filename
    fpath.write_bytes(b"x" * size)
    return FileReference(path=fpath, size_bytes=size)


@given(
    parsers.parse('an empty file "{filename}"'),
    target_fixture="test_file_ref",
)
def empty_file(tmp_path: Path, filename: str) -> FileReference:
    """Create an empty file."""
    fpath = tmp_path / filename
    fpath.write_bytes(b"")
    return FileReference(path=fpath, size_bytes=0)


@given(
    parsers.parse("{count:d} completed sessions"),
    target_fixture="session_list_count",
)
def completed_sessions(chronicle: SessionChronicle, count: int) -> int:
    """Create N completed sessions."""
    for i in range(count):
        s = chronicle.start_session(operator_id=f"operator-{i}")
        chronicle.end_session(s.node_id)
    return count


# ---------------------------------------------------------------------------
# When steps
# ---------------------------------------------------------------------------


@when(
    parsers.parse('a new file "{filename}" appears in the directory'),
    target_fixture="detected_filename",
)
def new_file_appears(watch_dir: Path, watcher_ctx: dict, filename: str) -> str:
    """Simulate a file creation event by directly calling the handler."""
    fpath = watch_dir / filename
    fpath.write_bytes(b"fake video data " * 10)

    # Find the handler for this directory
    for device_id, d in watcher_ctx["watch_dirs"].items():
        if d == watch_dir:
            handler = watcher_ctx["handlers"][device_id]
            fake_event = FileCreatedEvent(str(fpath))
            handler.on_created(fake_event)
            watcher_ctx["detected_files"].extend(handler.detected_files)
            break

    return filename


@when(
    parsers.parse('I start a session with operator "{operator}"'),
    target_fixture="current_session",
)
def start_session(chronicle: SessionChronicle, operator: str) -> SessionNode:
    return chronicle.start_session(operator_id=operator)


@when(
    parsers.parse('I add a recording with modality "{modality}" and file "{filename}"'),
    target_fixture="recording_added",
)
def add_recording(
    chronicle: SessionChronicle, current_session: SessionNode, tmp_path: Path,
    modality: str, filename: str,
) -> bool:
    fpath = tmp_path / filename
    fpath.write_bytes(b"recording data " * 10)
    file_ref = FileReference(path=fpath, size_bytes=fpath.stat().st_size)
    chronicle.add_recording(
        session_id=current_session.node_id,
        file_ref=file_ref,
        modality=modality,
    )
    return True


@when("I end the session", target_fixture="ended_session")
def end_session(chronicle: SessionChronicle, current_session: SessionNode) -> SessionNode:
    return chronicle.end_session(current_session.node_id)


@when("I run a quality check on the file", target_fixture="quality_result")
def run_quality_check(test_file_ref: FileReference) -> QualityMetric:
    checker = QualityChecker()
    return checker.check_file(test_file_ref)


@when("I list all sessions", target_fixture="listed_sessions")
def list_all_sessions(chronicle: SessionChronicle) -> list[SessionNode]:
    return chronicle.list_sessions()


# ---------------------------------------------------------------------------
# Then steps
# ---------------------------------------------------------------------------


@then("the file is detected")
def file_is_detected(watcher_ctx: dict) -> None:
    assert len(watcher_ctx["detected_files"]) > 0, "No files detected"


@then("a SessionNode is created")
def session_node_created(current_session: SessionNode) -> None:
    assert current_session is not None
    assert current_session.node_id


@then(
    parsers.parse("the session has {count:d} recording"),
)
def session_has_recordings(
    chronicle: SessionChronicle, current_session: SessionNode, count: int
) -> None:
    recordings = chronicle.get_recordings(current_session.node_id)
    assert len(recordings) == count, f"Expected {count}, got {len(recordings)}"


@then("the session has a duration")
def session_has_duration(ended_session: SessionNode) -> None:
    assert ended_session.duration_seconds is not None
    assert ended_session.duration_seconds >= 0


@then("the quality check returns metrics")
def quality_returns_metrics(quality_result: QualityMetric) -> None:
    assert quality_result is not None
    assert quality_result.name


@then(parsers.parse('the quality level is "{level}"'))
def quality_level_is(quality_result: QualityMetric, level: str) -> None:
    assert quality_result.level.value == level, (
        f"Expected {level!r}, got {quality_result.level.value!r}"
    )


@then(parsers.parse("I get {count:d} sessions"))
def got_n_sessions(listed_sessions: list[SessionNode], count: int) -> None:
    assert len(listed_sessions) == count, f"Expected {count}, got {len(listed_sessions)}"
