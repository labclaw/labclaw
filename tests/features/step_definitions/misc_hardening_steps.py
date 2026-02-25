"""Step definitions for Miscellaneous Infrastructure Hardening BDD scenarios."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from pytest_bdd import given, then, when

# ---------------------------------------------------------------------------
# Recovery — atomic writes
# ---------------------------------------------------------------------------


@given("a state recovery instance with a temporary directory", target_fixture="hardening_ctx")
def _given_recovery_instance(tmp_path: Path) -> dict[str, Any]:
    from labclaw.recovery import StateRecovery

    return {"recovery": StateRecovery(memory_root=tmp_path), "tmp_path": tmp_path}


@given(
    "a state recovery instance with a saved state containing cycle_count 3",
    target_fixture="hardening_ctx",
)
def _given_recovery_with_saved_state(tmp_path: Path) -> dict[str, Any]:
    from labclaw.recovery import StateRecovery

    sr = StateRecovery(memory_root=tmp_path)
    sr.save_state({"cycle_count": 3})
    return {"recovery": sr, "tmp_path": tmp_path}


@when("I save state with cycle_count 7")
def _when_save_state_7(hardening_ctx: dict[str, Any]) -> None:
    hardening_ctx["recovery"].save_state({"cycle_count": 7})


@when("a leftover .tmp file is present from a previous interrupted write")
def _when_leftover_tmp_file(hardening_ctx: dict[str, Any]) -> None:
    sr: Any = hardening_ctx["recovery"]
    tmp_file = sr.state_file.with_suffix(".tmp")
    tmp_file.write_text('{"partial": true}')
    hardening_ctx["leftover_tmp"] = tmp_file


@when("I load the state")
def _when_load_state(hardening_ctx: dict[str, Any]) -> None:
    hardening_ctx["loaded_state"] = hardening_ctx["recovery"].load_state()


@then("the state file exists and contains cycle_count 7")
def _then_state_file_cycle_7(hardening_ctx: dict[str, Any]) -> None:
    sr: Any = hardening_ctx["recovery"]
    assert sr.state_file.exists()
    data = json.loads(sr.state_file.read_text())
    assert data["cycle_count"] == 7


@then("no leftover .tmp files remain")
def _then_no_tmp_files(hardening_ctx: dict[str, Any]) -> None:
    tmp_path: Path = hardening_ctx["tmp_path"]
    tmp_files = list(tmp_path.glob("*.tmp"))
    assert tmp_files == [], f"Leftover .tmp files found: {tmp_files}"


@then("the loaded state contains cycle_count 3")
def _then_loaded_cycle_3(hardening_ctx: dict[str, Any]) -> None:
    state = hardening_ctx["loaded_state"]
    assert state is not None
    assert state["cycle_count"] == 3


# ---------------------------------------------------------------------------
# Daemon — plugin path trust
# ---------------------------------------------------------------------------


@given(
    "a daemon instance with data_dir inside the trusted memory root",
    target_fixture="hardening_ctx",
)
def _given_daemon_inside_trusted(tmp_path: Path) -> dict[str, Any]:
    from labclaw.daemon import LabClawDaemon

    # data_dir = tmp_path/lab/data → candidate = tmp_path/lab/plugins
    # memory_root = tmp_path/lab/memory → trusted_root = tmp_path/lab
    # tmp_path/lab/plugins IS relative to tmp_path/lab → accepted
    memory_root = tmp_path / "lab" / "memory"
    data_dir = tmp_path / "lab" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    memory_root.mkdir(parents=True, exist_ok=True)
    with patch("labclaw.daemon.set_memory_root"), patch("labclaw.daemon.set_data_dir"):
        daemon = LabClawDaemon(data_dir=data_dir, memory_root=memory_root)
    return {"daemon": daemon, "tmp_path": tmp_path}


@given(
    "a daemon instance with data_dir outside the trusted memory root",
    target_fixture="hardening_ctx",
)
def _given_daemon_outside_trusted(tmp_path: Path) -> dict[str, Any]:
    from labclaw.daemon import LabClawDaemon

    # data_dir parent plugins dir must NOT be under memory_root.parent
    # data_dir = tmp_path/outside/data → candidate = tmp_path/outside/plugins
    # memory_root = tmp_path/inside/memory → trusted_root = tmp_path/inside
    # tmp_path/outside/plugins is not relative to tmp_path/inside → rejected
    data_dir = tmp_path / "outside" / "data"
    memory_root = tmp_path / "inside" / "memory"
    data_dir.mkdir(parents=True, exist_ok=True)
    memory_root.mkdir(parents=True, exist_ok=True)
    with patch("labclaw.daemon.set_memory_root"), patch("labclaw.daemon.set_data_dir"):
        daemon = LabClawDaemon(data_dir=data_dir, memory_root=memory_root)
    return {"daemon": daemon, "tmp_path": tmp_path}


@when("the daemon resolves the local plugin directory")
def _when_resolve_plugin_dir(hardening_ctx: dict[str, Any]) -> None:
    hardening_ctx["plugin_dir"] = hardening_ctx["daemon"]._resolve_local_plugin_dir()


@then("the returned path is inside the trusted root")
def _then_path_inside_trusted(hardening_ctx: dict[str, Any]) -> None:
    plugin_dir: Path | None = hardening_ctx["plugin_dir"]
    assert plugin_dir is not None
    daemon = hardening_ctx["daemon"]
    trusted_root = daemon.memory_root.parent.resolve()
    assert plugin_dir.is_relative_to(trusted_root)


@then("the returned path is None")
def _then_path_is_none(hardening_ctx: dict[str, Any]) -> None:
    assert hardening_ctx["plugin_dir"] is None


# ---------------------------------------------------------------------------
# MCP server — security
# ---------------------------------------------------------------------------


@when("I call create_server", target_fixture="hardening_ctx")
def _when_create_server(tmp_path: Path) -> dict[str, Any]:
    from labclaw.mcp.server import create_server

    server = create_server()
    return {"server": server, "tmp_path": tmp_path}


@then("an MCP FastMCP instance is returned")
def _then_mcp_instance_returned(hardening_ctx: dict[str, Any]) -> None:
    from mcp.server.fastmcp import FastMCP

    assert isinstance(hardening_ctx["server"], FastMCP)


@given("the MCP server is created", target_fixture="hardening_ctx")
def _given_mcp_server_created(tmp_path: Path) -> dict[str, Any]:
    from labclaw.mcp.server import create_server

    server = create_server()
    return {"server": server, "tmp_path": tmp_path}


def _call_tool(server: Any, name: str, **kwargs: Any) -> str:
    tool_mgr = server._tool_manager
    tool = tool_mgr._tools[name]
    return tool.fn(**kwargs)


@when("I call the discover tool with no session data", target_fixture="hardening_ctx")
def _when_call_discover_no_data(hardening_ctx: dict[str, Any]) -> dict[str, Any]:
    with patch(
        "labclaw.api.deps.get_session_chronicle",
        side_effect=RuntimeError("no data"),
    ):
        result = _call_tool(hardening_ctx["server"], "discover")
    hardening_ctx["mcp_result"] = result
    return hardening_ctx


@when(
    'I call the provenance tool with finding_id "unknown-abc"',
    target_fixture="hardening_ctx",
)
def _when_call_provenance_unknown(hardening_ctx: dict[str, Any]) -> dict[str, Any]:
    result = _call_tool(hardening_ctx["server"], "provenance", finding_id="unknown-abc")
    hardening_ctx["mcp_result"] = result
    return hardening_ctx


@then("the result is valid JSON")
def _then_result_is_valid_json(hardening_ctx: dict[str, Any]) -> None:
    parsed = json.loads(hardening_ctx["mcp_result"])
    assert parsed is not None


@then('the result contains "No experiment data available"')
def _then_result_contains_no_data(hardening_ctx: dict[str, Any]) -> None:
    assert "No experiment data available" in hardening_ctx["mcp_result"]


@then('the result contains "No provenance chain registered"')
def _then_result_contains_no_provenance(hardening_ctx: dict[str, Any]) -> None:
    assert "No provenance chain registered" in hardening_ctx["mcp_result"]


# ---------------------------------------------------------------------------
# CLI reproduce — C5 REPRODUCE
# ---------------------------------------------------------------------------


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


@given("a data directory with CSV files for reproduce", target_fixture="hardening_ctx")
def _given_reproduce_data_dir(tmp_path: Path) -> dict[str, Any]:
    d = tmp_path / "data"
    d.mkdir()
    rows = [{"x": str(i), "y": str(i * 2), "speed": str(i * 0.5)} for i in range(20)]
    _write_csv(d / "session.csv", rows)
    return {"data_dir": d, "tmp_path": tmp_path}


@when('I run "labclaw reproduce" with seed 42', target_fixture="hardening_ctx")
def _when_run_reproduce_seed_42(
    hardening_ctx: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> dict[str, Any]:
    from labclaw.cli import main

    with patch.object(
        sys,
        "argv",
        [
            "labclaw",
            "reproduce",
            "--data-dir",
            str(hardening_ctx["data_dir"]),
            "--seed",
            "42",
        ],
    ):
        main()
    out = capsys.readouterr().out
    hardening_ctx["reproduce_output"] = out
    hardening_ctx["reproduce_result"] = json.loads(out)
    return hardening_ctx


@when('I run "labclaw reproduce --help"', target_fixture="hardening_ctx")
def _when_run_reproduce_help(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> dict[str, Any]:
    from labclaw.cli import main

    with patch.object(sys, "argv", ["labclaw", "reproduce", "--help"]):
        main()
    out = capsys.readouterr().out
    return {"reproduce_output": out, "tmp_path": tmp_path}


@when('I run "labclaw reproduce" with no arguments', target_fixture="hardening_ctx")
def _when_run_reproduce_no_args(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> dict[str, Any]:
    from labclaw.cli import main

    with (
        patch.object(sys, "argv", ["labclaw", "reproduce"]),
        pytest.raises(SystemExit) as exc_info,
    ):
        main()
    return {"exit_code": exc_info.value.code, "tmp_path": tmp_path}


@then("the output is valid JSON")
def _then_reproduce_output_is_json(hardening_ctx: dict[str, Any]) -> None:
    assert isinstance(hardening_ctx["reproduce_result"], dict)


@then('"reproducible" is true in the result')
def _then_reproducible_is_true(hardening_ctx: dict[str, Any]) -> None:
    assert hardening_ctx["reproduce_result"]["reproducible"] is True


@then('"diff" is null in the result')
def _then_diff_is_null(hardening_ctx: dict[str, Any]) -> None:
    assert hardening_ctx["reproduce_result"]["diff"] is None


@then("the output contains run1 and run2 findings")
def _then_output_contains_findings(hardening_ctx: dict[str, Any]) -> None:
    result = hardening_ctx["reproduce_result"]
    assert "run1" in result
    assert "run2" in result
    assert "findings" in result["run1"]
    assert "findings" in result["run2"]
    # findings must be lists (not zeroed out)
    assert isinstance(result["run1"]["findings"], list)
    assert isinstance(result["run2"]["findings"], list)


@then('the reproduce output contains "data-dir"')
def _then_reproduce_help_contains_data_dir(hardening_ctx: dict[str, Any]) -> None:
    assert "data-dir" in hardening_ctx["reproduce_output"]


@then("the reproduce command exits with an error")
def _then_reproduce_exits_error(hardening_ctx: dict[str, Any]) -> None:
    assert hardening_ctx["exit_code"] != 0
