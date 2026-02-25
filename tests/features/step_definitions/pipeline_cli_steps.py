"""BDD step definitions for pipeline CLI command."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from pytest_bdd import given, parsers, then, when

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _make_behavioral_rows(n: int = 20) -> list[dict[str, str]]:
    return [{"x": str(i), "y": str(i * 2), "speed": str(i * 0.5)} for i in range(n)]


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------


@given("a data directory with behavioral CSV files", target_fixture="pipeline_data_dir")
def pipeline_data_dir(tmp_path: Path) -> Path:
    d = tmp_path / "pipeline_data"
    d.mkdir()
    _write_csv(d / "session.csv", _make_behavioral_rows())
    return d


@given("an empty data directory", target_fixture="pipeline_data_dir")
def empty_data_dir(tmp_path: Path) -> Path:
    d = tmp_path / "empty_data"
    d.mkdir()
    return d


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when('I run "labclaw pipeline --once --data-dir DATA_DIR"', target_fixture="pipeline_result")
def run_pipeline_once(
    pipeline_data_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> dict[str, Any]:
    memory = tmp_path / "memory"
    from labclaw.cli import main

    with patch.object(
        sys,
        "argv",
        [
            "labclaw",
            "pipeline",
            "--once",
            "--data-dir",
            str(pipeline_data_dir),
            "--memory-root",
            str(memory),
        ],
    ):
        main()
    out = capsys.readouterr().out
    return json.loads(out)


@when("I run the pipeline command twice with --seed 42", target_fixture="pipeline_result")
def run_pipeline_twice_with_seed(
    pipeline_data_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> list[dict[str, Any]]:
    from labclaw.cli import main

    results = []
    for i in range(2):
        mem = tmp_path / f"mem_{i}"
        with patch.object(
            sys,
            "argv",
            [
                "labclaw",
                "pipeline",
                "--once",
                "--data-dir",
                str(pipeline_data_dir),
                "--memory-root",
                str(mem),
                "--seed",
                "42",
            ],
        ):
            main()
        out = capsys.readouterr().out
        results.append(json.loads(out))
    return results


@when('I run "labclaw pipeline" with no data directory', target_fixture="pipeline_exit_code")
def run_pipeline_no_data_dir(capsys: pytest.CaptureFixture[str]) -> int:
    from labclaw.cli import main

    with patch.object(sys, "argv", ["labclaw", "pipeline"]):
        with pytest.raises(SystemExit) as exc_info:
            main()
    return exc_info.value.code  # type: ignore[return-value]


@when('I run "labclaw pipeline --once --data-dir EMPTY_DIR"', target_fixture="pipeline_exit_code")
def run_pipeline_empty_dir(pipeline_data_dir: Path, capsys: pytest.CaptureFixture[str]) -> int:
    from labclaw.cli import main

    with patch.object(
        sys,
        "argv",
        [
            "labclaw",
            "pipeline",
            "--once",
            "--data-dir",
            str(pipeline_data_dir),
        ],
    ):
        with pytest.raises(SystemExit) as exc_info:
            main()
    return exc_info.value.code  # type: ignore[return-value]


@when("I run the pipeline command without a memory root", target_fixture="pipeline_result")
def run_pipeline_without_memory_root(
    pipeline_data_dir: Path, capsys: pytest.CaptureFixture[str]
) -> dict[str, Any]:
    from labclaw.cli import main

    with patch.object(
        sys,
        "argv",
        [
            "labclaw",
            "pipeline",
            "--once",
            "--data-dir",
            str(pipeline_data_dir),
        ],
    ):
        main()
    out = capsys.readouterr().out
    return json.loads(out)


@when('I run "labclaw pipeline --help"', target_fixture="pipeline_result")
def run_pipeline_help(capsys: pytest.CaptureFixture[str]) -> str:
    from labclaw.cli import main

    with patch.object(sys, "argv", ["labclaw", "pipeline", "--help"]):
        main()
    return capsys.readouterr().out


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------


@then("the output is valid JSON")
def output_is_valid_json(pipeline_result: Any) -> None:
    # If we got here it was already parsed in the When step
    assert isinstance(pipeline_result, dict)


@then("the result shows success")
def result_shows_success(pipeline_result: dict[str, Any]) -> None:
    assert pipeline_result["success"] is True


@then("both results have the same patterns_found count")
def both_results_same_patterns(pipeline_result: list[dict[str, Any]]) -> None:
    assert len(pipeline_result) == 2
    assert pipeline_result[0]["patterns_found"] == pipeline_result[1]["patterns_found"]


@then("the command exits with an error")
def command_exits_with_error(pipeline_exit_code: int) -> None:
    assert pipeline_exit_code != 0


@then(parsers.parse('the output contains "{text}"'))
def output_contains(pipeline_result: str, text: str) -> None:
    assert text in pipeline_result
