"""TDD tests for labclaw pipeline CLI command."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from labclaw.cli import main


def _write_csv(path: Path, rows: list[dict]) -> None:
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    d = tmp_path / "data"
    d.mkdir()
    rows = [{"x": str(i), "y": str(i * 2), "speed": str(i * 0.5)} for i in range(20)]
    _write_csv(d / "session.csv", rows)
    return d


# ---------------------------------------------------------------------------
# Happy-path: runs one cycle and prints valid JSON
# ---------------------------------------------------------------------------


def test_pipeline_once_runs_and_prints_json(
    data_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    memory = tmp_path / "memory"
    with patch.object(
        sys,
        "argv",
        [
            "labclaw",
            "pipeline",
            "--once",
            "--data-dir",
            str(data_dir),
            "--memory-root",
            str(memory),
        ],
    ):
        main()
    out = capsys.readouterr().out
    result = json.loads(out)
    assert result["success"] is True
    assert len(result["steps_completed"]) >= 3


def test_pipeline_once_without_memory_root(
    data_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """--memory-root is optional; omitting it runs fine."""
    with patch.object(
        sys,
        "argv",
        [
            "labclaw",
            "pipeline",
            "--once",
            "--data-dir",
            str(data_dir),
        ],
    ):
        main()
    out = capsys.readouterr().out
    result = json.loads(out)
    assert result["success"] is True


# ---------------------------------------------------------------------------
# --seed reproducibility
# ---------------------------------------------------------------------------


def test_pipeline_once_with_seed(
    data_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
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
                str(data_dir),
                "--memory-root",
                str(mem),
                "--seed",
                "42",
            ],
        ):
            main()
        out = capsys.readouterr().out
        results.append(json.loads(out))
    assert results[0]["patterns_found"] == results[1]["patterns_found"]


# ---------------------------------------------------------------------------
# Error paths: missing / empty --data-dir
# ---------------------------------------------------------------------------


def test_pipeline_no_data_dir_prints_usage(capsys: pytest.CaptureFixture[str]) -> None:
    with patch.object(sys, "argv", ["labclaw", "pipeline"]):
        with pytest.raises(SystemExit):
            main()


def test_pipeline_args_but_no_data_dir_flag(capsys: pytest.CaptureFixture[str]) -> None:
    """--once present but --data-dir omitted: data_dir stays None, must exit with error."""
    with patch.object(sys, "argv", ["labclaw", "pipeline", "--once"]):
        with pytest.raises(SystemExit) as exc_info:
            main()
    assert exc_info.value.code == 1
    err = capsys.readouterr().err
    assert "--data-dir" in err


def test_pipeline_empty_data_dir(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    with patch.object(
        sys,
        "argv",
        [
            "labclaw",
            "pipeline",
            "--once",
            "--data-dir",
            str(empty),
        ],
    ):
        with pytest.raises(SystemExit):
            main()


def test_pipeline_nonexistent_data_dir(tmp_path: Path) -> None:
    """A data-dir path that does not exist should exit with error."""
    with patch.object(
        sys,
        "argv",
        [
            "labclaw",
            "pipeline",
            "--once",
            "--data-dir",
            str(tmp_path / "does_not_exist"),
        ],
    ):
        with pytest.raises(SystemExit):
            main()


# ---------------------------------------------------------------------------
# --help
# ---------------------------------------------------------------------------


def test_pipeline_help(capsys: pytest.CaptureFixture[str]) -> None:
    with patch.object(sys, "argv", ["labclaw", "pipeline", "--help"]):
        main()
    out = capsys.readouterr().out
    assert "data-dir" in out


# ---------------------------------------------------------------------------
# Multiple CSV files are combined
# ---------------------------------------------------------------------------


def test_pipeline_combines_multiple_csvs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    d = tmp_path / "multi"
    d.mkdir()
    rows_a = [{"x": str(i), "y": str(i)} for i in range(10)]
    rows_b = [{"x": str(i + 10), "y": str(i + 10)} for i in range(10)]
    _write_csv(d / "a.csv", rows_a)
    _write_csv(d / "b.csv", rows_b)

    with patch.object(
        sys,
        "argv",
        [
            "labclaw",
            "pipeline",
            "--once",
            "--data-dir",
            str(d),
        ],
    ):
        main()
    out = capsys.readouterr().out
    result = json.loads(out)
    assert result["success"] is True


# ---------------------------------------------------------------------------
# main() dispatches "pipeline" to _pipeline_cmd
# ---------------------------------------------------------------------------


def test_main_dispatches_pipeline_cmd() -> None:
    import labclaw.cli as cli_mod

    with (
        patch.object(sys, "argv", ["labclaw", "pipeline", "--once"]),
        patch.object(cli_mod, "_pipeline_cmd") as mock_pipeline,
    ):
        cli_mod.main()

    mock_pipeline.assert_called_once_with(["--once"])
