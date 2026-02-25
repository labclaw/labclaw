"""Unit tests for the 'labclaw memory' CLI command and coverage gaps."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from labclaw.cli import _memory_cmd, main

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_csv(path: Path, rows: list[dict]) -> None:
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    d = tmp_path / "data"
    d.mkdir()
    rows = [{"x": str(i), "y": str(i * 2)} for i in range(20)]
    _write_csv(d / "session.csv", rows)
    return d


# ---------------------------------------------------------------------------
# main() dispatch to memory command
# ---------------------------------------------------------------------------


class TestMainMemoryDispatch:
    def test_memory_dispatches(self, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
        with patch.object(sys, "argv", ["labclaw", "memory", "--help"]):
            _memory_cmd(["--help"])
        out = capsys.readouterr().out
        assert "memory" in out.lower() or "subcommand" in out.lower()

    def test_main_calls_memory_cmd(self, tmp_path: Path) -> None:
        called = []

        def fake_memory_cmd(args: list) -> None:
            called.append(args)

        with patch("labclaw.cli._memory_cmd", side_effect=fake_memory_cmd):
            with patch.object(sys, "argv", ["labclaw", "memory", "stats"]):
                main()

        assert called == [["stats"]]


# ---------------------------------------------------------------------------
# _memory_cmd — help / no args
# ---------------------------------------------------------------------------


class TestMemoryCmdHelp:
    def test_help_flag(self, capsys: pytest.CaptureFixture[str]) -> None:
        _memory_cmd(["--help"])
        out = capsys.readouterr().out
        assert "query" in out
        assert "stats" in out

    def test_no_args_exits(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc:
            _memory_cmd([])
        assert exc.value.code == 1
        out = capsys.readouterr().out
        assert "subcommand" in out.lower() or "query" in out.lower()


# ---------------------------------------------------------------------------
# _memory_cmd — query subcommand
# ---------------------------------------------------------------------------


class TestMemoryCmdQuery:
    def test_query_empty_memory(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        memory_root = tmp_path / "mem"
        _memory_cmd(["query", "anything", "--memory-root", str(memory_root)])
        out = capsys.readouterr().out
        result = json.loads(out)
        assert isinstance(result, list)

    def test_query_with_findings(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        import asyncio

        from labclaw.memory.session_memory import SessionMemoryManager

        memory_root = tmp_path / "mem"
        mgr = SessionMemoryManager(memory_root)
        asyncio.run(mgr.init())
        asyncio.run(mgr.store_finding({"description": "speed finding", "finding_id": "f1"}))

        _memory_cmd(["query", "speed", "--memory-root", str(memory_root)])
        out = capsys.readouterr().out
        result = json.loads(out)
        assert len(result) == 1

    def test_query_with_db(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        import asyncio

        from labclaw.memory.session_memory import SessionMemoryManager

        memory_root = tmp_path / "mem"
        db_path = tmp_path / "t.db"
        mgr = SessionMemoryManager(memory_root, db_path)
        asyncio.run(mgr.init())
        asyncio.run(mgr.store_finding({"description": "db finding", "finding_id": "d1"}))
        asyncio.run(mgr._tier_b.close())

        _memory_cmd(["query", "", "--memory-root", str(memory_root), "--db", str(db_path)])
        out = capsys.readouterr().out
        result = json.loads(out)
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# _memory_cmd — stats subcommand
# ---------------------------------------------------------------------------


class TestMemoryCmdStats:
    def test_stats_empty(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        memory_root = tmp_path / "mem"
        _memory_cmd(["stats", "--memory-root", str(memory_root)])
        out = capsys.readouterr().out
        result = json.loads(out)
        assert result["finding_count"] == 0
        assert result["retrieval_rate"] == 1.0

    def test_stats_with_findings(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        import asyncio

        from labclaw.memory.session_memory import SessionMemoryManager

        memory_root = tmp_path / "mem"
        mgr = SessionMemoryManager(memory_root)
        asyncio.run(mgr.init())
        asyncio.run(mgr.store_finding({"description": "finding A", "finding_id": "a"}))
        asyncio.run(mgr.store_finding({"description": "finding B", "finding_id": "b"}))

        _memory_cmd(["stats", "--memory-root", str(memory_root)])
        out = capsys.readouterr().out
        result = json.loads(out)
        assert result["finding_count"] == 2


# ---------------------------------------------------------------------------
# _memory_cmd — unknown subcommand
# ---------------------------------------------------------------------------


class TestMemoryCmdUnknown:
    def test_unknown_subcommand_exits(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        memory_root = tmp_path / "mem"
        with pytest.raises(SystemExit) as exc:
            _memory_cmd(["badcmd", "--memory-root", str(memory_root)])
        assert exc.value.code == 1
        err = capsys.readouterr().err
        assert "badcmd" in err

    def test_memory_cmd_unknown_extra_flag_is_skipped(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Unknown flags at position > 1 are silently skipped (line 496)."""
        memory_root = tmp_path / "mem"
        # "stats" subcommand with an unknown flag after --memory-root
        _memory_cmd(["stats", "--memory-root", str(memory_root), "--unknown-flag"])
        out = capsys.readouterr().out
        result = json.loads(out)
        assert "finding_count" in result


# ---------------------------------------------------------------------------
# CLI line 52 — ablation dispatch
# ---------------------------------------------------------------------------


class TestMainAblationDispatch:
    def test_main_dispatches_to_ablation(self) -> None:
        called = []

        def fake_ablation(args: list) -> None:
            called.append(args)

        with patch("labclaw.cli._ablation_cmd", side_effect=fake_ablation):
            with patch.object(sys, "argv", ["labclaw", "ablation", "--help"]):
                main()

        assert called == [["--help"]]


# ---------------------------------------------------------------------------
# _pipeline_cmd coverage: --max-llm-calls argument (lines 296-297)
# ---------------------------------------------------------------------------


class TestPipelineCmdMaxLlmCalls:
    def test_max_llm_calls_arg(
        self, data_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with patch.object(
            sys,
            "argv",
            [
                "labclaw",
                "pipeline",
                "--once",
                "--data-dir",
                str(data_dir),
                "--max-llm-calls",
                "5",
            ],
        ):
            main()
        out = capsys.readouterr().out
        result = json.loads(out)
        assert "cycle_id" in result
