"""TDD tests for labclaw reproduce CLI command."""

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
# --help
# ---------------------------------------------------------------------------


def test_reproduce_help(capsys: pytest.CaptureFixture[str]) -> None:
    """--help prints usage and exits 0."""
    with patch.object(sys, "argv", ["labclaw", "reproduce", "--help"]):
        main()
    out = capsys.readouterr().out
    assert "data-dir" in out
    assert "seed" in out


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


def test_reproduce_no_args_exits() -> None:
    """No args → exits with error."""
    with patch.object(sys, "argv", ["labclaw", "reproduce"]):
        with pytest.raises(SystemExit) as exc_info:
            main()
    assert exc_info.value.code == 1


def test_reproduce_missing_data_dir_exits(capsys: pytest.CaptureFixture[str]) -> None:
    """Args present but --data-dir omitted → exits with error."""
    with patch.object(sys, "argv", ["labclaw", "reproduce", "--seed", "42"]):
        with pytest.raises(SystemExit) as exc_info:
            main()
    assert exc_info.value.code == 1
    err = capsys.readouterr().err
    assert "--data-dir" in err


def test_reproduce_nonexistent_dir_exits(tmp_path: Path) -> None:
    """Non-existent --data-dir → exits with error."""
    with patch.object(
        sys,
        "argv",
        [
            "labclaw",
            "reproduce",
            "--data-dir",
            str(tmp_path / "no_such_dir"),
            "--seed",
            "42",
        ],
    ):
        with pytest.raises(SystemExit):
            main()


def test_reproduce_empty_dir_exits(tmp_path: Path) -> None:
    """Empty directory (no CSV files) → exits with error."""
    empty = tmp_path / "empty"
    empty.mkdir()
    with patch.object(
        sys,
        "argv",
        [
            "labclaw",
            "reproduce",
            "--data-dir",
            str(empty),
            "--seed",
            "42",
        ],
    ):
        with pytest.raises(SystemExit):
            main()


# ---------------------------------------------------------------------------
# Happy path: reproducible=True
# ---------------------------------------------------------------------------


def test_reproduce_runs_successfully(data_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """With synthetic CSV data and fixed seed, pipeline is reproducible."""
    with patch.object(
        sys,
        "argv",
        [
            "labclaw",
            "reproduce",
            "--data-dir",
            str(data_dir),
            "--seed",
            "42",
        ],
    ):
        main()
    out = capsys.readouterr().out
    result = json.loads(out)
    assert result["reproducible"] is True
    assert result["diff"] is None
    assert "run1" in result
    assert "run2" in result
    assert result["run1"]["success"] is True
    assert result["run2"]["success"] is True


def test_reproduce_with_memory_root(
    data_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """--memory-root is optional and accepted without error."""
    memory = tmp_path / "memory"
    with patch.object(
        sys,
        "argv",
        [
            "labclaw",
            "reproduce",
            "--data-dir",
            str(data_dir),
            "--seed",
            "42",
            "--memory-root",
            str(memory),
        ],
    ):
        main()
    out = capsys.readouterr().out
    result = json.loads(out)
    assert result["reproducible"] is True


# ---------------------------------------------------------------------------
# Non-reproducible path: diff is reported and exit code is 1
# ---------------------------------------------------------------------------


def test_reproduce_not_reproducible_exits_1(
    data_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """When results differ, diff is reported and exit code is 1."""
    import labclaw.cli as cli_mod
    from labclaw.orchestrator.loop import CycleResult

    # Two different results — patterns_found differs
    result_a = CycleResult(patterns_found=1, hypotheses_generated=0, success=True, findings=["a"])
    result_b = CycleResult(patterns_found=2, hypotheses_generated=0, success=True, findings=["b"])

    # Patch asyncio.run in cli module to return alternating results
    call_count = {"n": 0}

    def fake_run(coro):
        call_count["n"] += 1
        # Close the coroutine to avoid ResourceWarning
        try:
            coro.close()
        except Exception:
            pass
        return result_a if call_count["n"] == 1 else result_b

    with (
        patch.object(
            sys,
            "argv",
            [
                "labclaw",
                "reproduce",
                "--data-dir",
                str(data_dir),
                "--seed",
                "42",
            ],
        ),
        patch.object(cli_mod, "asyncio") as mock_asyncio,
    ):
        mock_asyncio.run.side_effect = fake_run
        with pytest.raises(SystemExit) as exc_info:
            cli_mod.main()

    assert exc_info.value.code == 1
    out = capsys.readouterr().out
    result = json.loads(out)
    assert result["reproducible"] is False
    assert result["diff"] is not None
    assert len(result["diff"]) > 0


# ---------------------------------------------------------------------------
# Unknown args are silently ignored (hits the else: i += 1 branch)
# ---------------------------------------------------------------------------


def test_reproduce_ignores_unknown_args(data_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Unknown args are skipped (else branch) and pipeline still runs."""
    with patch.object(
        sys,
        "argv",
        [
            "labclaw",
            "reproduce",
            "--data-dir",
            str(data_dir),
            "--seed",
            "42",
            "--unknown-flag",  # triggers else: i += 1
        ],
    ):
        main()
    out = capsys.readouterr().out
    result = json.loads(out)
    assert result["reproducible"] is True


# ---------------------------------------------------------------------------
# main() dispatches "reproduce" to _reproduce_cmd
# ---------------------------------------------------------------------------


def test_reproduce_main_dispatches() -> None:
    """main() routes 'reproduce' command to _reproduce_cmd."""
    import labclaw.cli as cli_mod

    with (
        patch.object(sys, "argv", ["labclaw", "reproduce", "--seed", "42"]),
        patch.object(cli_mod, "_reproduce_cmd") as mock_reproduce,
    ):
        cli_mod.main()

    mock_reproduce.assert_called_once_with(["--seed", "42"])
