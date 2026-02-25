"""TDD tests for labclaw ablation CLI command and related CLI coverage."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from labclaw.cli import _ablation_cmd, main


def _write_csv(path: Path, rows: list[dict]) -> None:
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


@pytest.fixture()
def data_dir(tmp_path: Path) -> Path:
    d = tmp_path / "data"
    d.mkdir()
    rows = [{"x": str(i), "y": str(i * 2), "speed": str(i * 0.5)} for i in range(20)]
    _write_csv(d / "session.csv", rows)
    return d


# ---------------------------------------------------------------------------
# main() dispatches to ablation
# ---------------------------------------------------------------------------


class TestMainAblationDispatch:
    def test_ablation_dispatches(self, data_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        with (
            patch.object(
                sys, "argv", ["labclaw", "ablation", "--data-dir", str(data_dir), "--n-cycles", "2"]
            ),
            patch("labclaw.cli._ablation_cmd") as mock_cmd,
        ):
            main()
        mock_cmd.assert_called_once()


# ---------------------------------------------------------------------------
# _ablation_cmd: help flag
# ---------------------------------------------------------------------------


class TestAblationHelp:
    def test_help_short(self, capsys: pytest.CaptureFixture[str]) -> None:
        _ablation_cmd(["-h"])
        out = capsys.readouterr().out
        assert "Usage: labclaw ablation" in out

    def test_help_long(self, capsys: pytest.CaptureFixture[str]) -> None:
        _ablation_cmd(["--help"])
        out = capsys.readouterr().out
        assert "--data-dir" in out
        assert "--n-cycles" in out
        assert "--seed" in out


# ---------------------------------------------------------------------------
# _ablation_cmd: error cases
# ---------------------------------------------------------------------------


class TestAblationErrors:
    def test_no_args_exits(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc:
            _ablation_cmd([])
        assert exc.value.code == 1
        err = capsys.readouterr().err
        assert "--data-dir is required" in err

    def test_no_data_dir_flag_exits(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc:
            _ablation_cmd(["--n-cycles", "3"])
        assert exc.value.code == 1
        err = capsys.readouterr().err
        assert "--data-dir is required" in err

    def test_nonexistent_data_dir_exits(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        nonexistent = tmp_path / "does_not_exist"
        with pytest.raises(SystemExit) as exc:
            _ablation_cmd(["--data-dir", str(nonexistent)])
        assert exc.value.code == 1
        err = capsys.readouterr().err
        assert "does not exist" in err

    def test_empty_data_dir_exits(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        with pytest.raises(SystemExit) as exc:
            _ablation_cmd(["--data-dir", str(empty)])
        assert exc.value.code == 1
        err = capsys.readouterr().err
        assert "no .csv files" in err


# ---------------------------------------------------------------------------
# _ablation_cmd: happy path
# ---------------------------------------------------------------------------


class TestAblationHappyPath:
    def test_runs_and_prints_json(
        self, data_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _ablation_cmd(["--data-dir", str(data_dir), "--n-cycles", "2"])
        out = capsys.readouterr().out
        result = json.loads(out)
        assert "full" in result
        assert "no_evolution" in result
        assert "comparison" in result
        assert result["full"]["n_cycles"] == 2
        assert result["no_evolution"]["n_cycles"] == 2

    def test_custom_n_cycles(
        self, data_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _ablation_cmd(["--data-dir", str(data_dir), "--n-cycles", "3"])
        out = capsys.readouterr().out
        result = json.loads(out)
        assert result["full"]["n_cycles"] == 3

    def test_custom_seed(
        self, data_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _ablation_cmd(["--data-dir", str(data_dir), "--n-cycles", "2", "--seed", "99"])
        out = capsys.readouterr().out
        result = json.loads(out)
        # Just checks it ran without error and produced valid JSON
        assert "full" in result

    def test_comparison_includes_p_value(
        self, data_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _ablation_cmd(["--data-dir", str(data_dir), "--n-cycles", "2"])
        out = capsys.readouterr().out
        result = json.loads(out)
        comparison = result["comparison"]
        assert "p_value" in comparison
        assert "significant" in comparison
        assert "full_mean_fitness" in comparison
        assert "ablation_mean_fitness" in comparison

    def test_skips_unknown_arg(
        self, data_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Unknown flags are silently skipped."""
        _ablation_cmd(["--data-dir", str(data_dir), "--n-cycles", "2", "--unknown-flag"])
        out = capsys.readouterr().out
        result = json.loads(out)
        assert "full" in result

    def test_stat_test_exception_yields_none_p_value(
        self, data_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """When StatisticalValidator raises, p_value/significant should be None."""
        from labclaw.validation.statistics import StatisticalValidator

        with patch.object(
            StatisticalValidator,
            "run_test",
            side_effect=ValueError("no variance"),
        ):
            _ablation_cmd(["--data-dir", str(data_dir), "--n-cycles", "2"])
        out = capsys.readouterr().out
        result = json.loads(out)
        assert result["comparison"]["p_value"] is None
        assert result["comparison"]["significant"] is None
