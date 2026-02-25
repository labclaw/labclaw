"""Step definitions for Production Stability BDD scenarios (v0.0.9)."""

from __future__ import annotations

import json
import logging
from io import StringIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given, then, when

from labclaw.api.app import app
from labclaw.api.deps import reset_all
from labclaw.api.health_collector import reset_health_collector
from labclaw.logging_config import JSONFormatter, configure_logging
from labclaw.recovery import StateRecovery

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def stability_context(tmp_path: Path) -> dict:
    return {"tmp_path": tmp_path}


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------


@given("a daemon with 5 completed cycles", target_fixture="stability_context")
def _given_daemon_with_cycles(tmp_path: Path) -> dict:
    ctx: dict = {"tmp_path": tmp_path, "cycle_count": 5}
    return ctx


@given("a corrupt state file", target_fixture="stability_context")
def _given_corrupt_state_file(tmp_path: Path) -> dict:
    state_file = tmp_path / ".labclaw_state.json"
    state_file.write_text("CORRUPT{{{{[[[")
    return {"tmp_path": tmp_path, "state_file": state_file}


@given("a running API server", target_fixture="stability_context")
def _given_running_api(tmp_path: Path) -> dict:
    reset_all()
    reset_health_collector()
    client = TestClient(app)
    return {"client": client, "tmp_path": tmp_path}


@given("structured logging is configured", target_fixture="stability_context")
def _given_structured_logging(tmp_path: Path) -> dict:
    configure_logging(level="DEBUG", json_output=True)
    return {"tmp_path": tmp_path}


@given("a state file being written", target_fixture="stability_context")
def _given_state_file_being_written(tmp_path: Path) -> dict:
    sr = StateRecovery(memory_root=tmp_path)
    # Write an initial valid state
    sr.save_state({"cycle_count": 3})
    return {"tmp_path": tmp_path, "recovery": sr}


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when("the daemon state is saved")
def _when_state_is_saved(stability_context: dict) -> None:
    tmp_path = stability_context["tmp_path"]
    sr = StateRecovery(memory_root=tmp_path)
    sr.save_state({"cycle_count": stability_context["cycle_count"]})
    stability_context["recovery"] = sr


@when("the daemon is restarted")
def _when_daemon_restarted(stability_context: dict) -> None:
    # Simulate restart: create a new StateRecovery pointing at same directory
    tmp_path = stability_context["tmp_path"]
    stability_context["recovery_after_restart"] = StateRecovery(memory_root=tmp_path)


@when("the daemon starts")
def _when_daemon_starts(stability_context: dict) -> None:
    tmp_path = stability_context["tmp_path"]
    sr = StateRecovery(memory_root=tmp_path)
    stability_context["loaded_state"] = sr.load_state()


@when("I check the health endpoint")
def _when_check_health(stability_context: dict) -> None:
    client: TestClient = stability_context["client"]
    stability_context["health_response"] = client.get("/api/health")


@when("a log message is emitted")
def _when_log_message_emitted(stability_context: dict) -> None:
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JSONFormatter())
    test_logger = logging.getLogger("stability.test")
    test_logger.addHandler(handler)
    test_logger.setLevel(logging.DEBUG)
    test_logger.info("test stability message")
    test_logger.removeHandler(handler)
    stability_context["log_output"] = stream.getvalue()


@when("the write is interrupted")
def _when_write_interrupted(stability_context: dict) -> None:
    # Simulate: a .tmp file is left behind (write interrupted before rename).
    recovery: StateRecovery = stability_context["recovery"]
    tmp_file = recovery.state_file.with_suffix(".tmp")
    tmp_file.write_text('{"partial": true}')
    stability_context["tmp_file"] = tmp_file


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------


@then("the recovered state shows 5 completed cycles")
def _then_recovered_state_shows_cycles(stability_context: dict) -> None:
    sr: StateRecovery = stability_context["recovery_after_restart"]
    state = sr.load_state()
    assert state is not None, "Expected non-None state after restart"
    assert state["cycle_count"] == 5


@then("it initializes fresh state without error")
def _then_fresh_state_no_error(stability_context: dict) -> None:
    # load_state must have returned None (not raised an exception)
    assert stability_context["loaded_state"] is None


@then("all components show status")
def _then_components_show_status(stability_context: dict) -> None:
    resp = stability_context["health_response"]
    assert resp.status_code in (200, 503)
    data = resp.json()
    assert "components" in data, f"'components' key missing: {data}"
    assert isinstance(data["components"], dict)
    assert len(data["components"]) > 0


@then("uptime is reported")
def _then_uptime_reported(stability_context: dict) -> None:
    data = stability_context["health_response"].json()
    assert "uptime_seconds" in data
    assert isinstance(data["uptime_seconds"], (int, float))
    assert data["uptime_seconds"] >= 0


@then("the output is valid JSON with timestamp and level")
def _then_json_output_valid(stability_context: dict) -> None:
    raw = stability_context["log_output"].strip()
    assert raw, "Expected non-empty log output"
    parsed = json.loads(raw)
    assert "timestamp" in parsed
    assert "level" in parsed
    assert parsed["level"] == "INFO"


@then("the previous state file is intact")
def _then_previous_state_intact(stability_context: dict) -> None:
    recovery: StateRecovery = stability_context["recovery"]
    # The original state file (from before the interrupted write) must still
    # contain valid JSON with cycle_count == 3.
    state = recovery.load_state()
    assert state is not None
    assert state["cycle_count"] == 3
