"""Unit tests — export CLI command."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch


def _call_export(args: list[str]) -> int:
    from labclaw.cli import _export_cmd

    try:
        _export_cmd(args)
        return 0
    except SystemExit as exc:
        return exc.code or 0


# ---------------------------------------------------------------------------
# Help / no args
# ---------------------------------------------------------------------------


def test_export_help_exits_zero() -> None:
    code = _call_export(["--help"])
    assert code == 0


def test_export_no_args_exits_one() -> None:
    code = _call_export([])
    assert code == 1


# ---------------------------------------------------------------------------
# Missing required --output
# ---------------------------------------------------------------------------


def test_export_missing_output_exits_nonzero(tmp_path: Path) -> None:
    code = _call_export(["--format", "json", "--session", "s1"])
    assert code != 0


# ---------------------------------------------------------------------------
# Unsupported format
# ---------------------------------------------------------------------------


def test_export_bad_format_exits_nonzero(tmp_path: Path) -> None:
    out = str(tmp_path / "out.csv")
    code = _call_export(["--format", "csv", "--session", "s1", "--output", out])
    assert code != 0


# ---------------------------------------------------------------------------
# JSON export via CLI
# ---------------------------------------------------------------------------


def test_export_json_creates_file(tmp_path: Path, capsys) -> None:
    out = tmp_path / "out.json"
    code = _call_export(["--format", "json", "--session", "sess-test", "--output", str(out)])
    assert code == 0
    assert out.exists()
    captured = capsys.readouterr()
    assert "Exported" in captured.out


# ---------------------------------------------------------------------------
# NWB export via CLI falls back to JSON when pynwb absent
# ---------------------------------------------------------------------------


def test_export_nwb_format_fallback(tmp_path: Path, capsys) -> None:
    out = tmp_path / "out.nwb"
    with patch.dict(sys.modules, {"pynwb": None}):
        code = _call_export(["--format", "nwb", "--session", "sess-nwb", "--output", str(out)])
    assert code == 0
    captured = capsys.readouterr()
    assert "Exported" in captured.out


# ---------------------------------------------------------------------------
# Unknown arg is silently skipped (else branch: i += 1)
# ---------------------------------------------------------------------------


def test_export_unknown_arg_is_skipped(tmp_path: Path) -> None:
    """Unrecognised tokens are silently skipped (the else: i += 1 branch)."""
    out = tmp_path / "out.json"
    # --bogus is an unknown arg; it should be skipped, not cause an error.
    code = _call_export(["--bogus", "--format", "json", "--session", "s1", "--output", str(out)])
    assert code == 0
    assert out.exists()


# ---------------------------------------------------------------------------
# CLI via main() dispatch
# ---------------------------------------------------------------------------


def test_main_dispatches_export(tmp_path: Path) -> None:
    out = str(tmp_path / "via_main.json")
    with patch.object(
        sys,
        "argv",
        ["labclaw", "export", "--format", "json", "--session", "x", "--output", out],
    ):
        from labclaw.cli import main

        main()
    assert Path(out).exists()
