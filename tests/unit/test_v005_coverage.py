"""Coverage tests for v0.0.5 — First Discovery.

Covers:
- cli.py: --max-llm-calls flag, ablation cmd dispatch, _ablation_cmd body
- discovery/hypothesis.py: new cost guard paths already covered by test_hypothesis_cost_guard.py
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from labclaw.cli import main
from labclaw.discovery.hypothesis import (
    HypothesisInput,
    LLMHypothesisGenerator,
    _LLMHypothesisItem,
    _LLMHypothesisResponse,
)
from labclaw.discovery.mining import PatternRecord

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_csv(path: Path, rows: list[dict]) -> None:
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _make_data_dir(tmp_path: Path, n: int = 20) -> Path:
    d = tmp_path / "data"
    d.mkdir(exist_ok=True)
    rows = [{"x": str(i), "y": str(i * 2), "speed": str(i * 0.5)} for i in range(n)]
    _write_csv(d / "session.csv", rows)
    return d


def _make_llm_provider() -> MagicMock:
    llm = MagicMock()
    llm.complete_structured = AsyncMock(
        return_value=_LLMHypothesisResponse(
            hypotheses=[
                _LLMHypothesisItem(
                    statement="LLM hypothesis",
                    testable=True,
                    confidence=0.8,
                    required_experiments=["exp A"],
                    resource_estimate="1 session",
                )
            ]
        )
    )
    return llm


def _make_pattern() -> PatternRecord:
    return PatternRecord(
        pattern_type="correlation",
        description="Test pattern",
        evidence={"col_a": "speed", "col_b": "distance", "r": 0.9, "p_value": 0.001},
        confidence=0.85,
    )


# ---------------------------------------------------------------------------
# cli.py: --max-llm-calls flag
# ---------------------------------------------------------------------------


def test_pipeline_max_llm_calls_flag(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """--max-llm-calls N is parsed and passed through."""
    data_dir = _make_data_dir(tmp_path)
    with patch.object(sys, "argv", [
        "labclaw", "pipeline", "--once",
        "--data-dir", str(data_dir),
        "--max-llm-calls", "5",
    ]):
        main()
    out = capsys.readouterr().out
    result = json.loads(out)
    assert result["success"] is True


def test_pipeline_max_llm_calls_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """--max-llm-calls 0 forces template fallback."""
    data_dir = _make_data_dir(tmp_path)
    with patch.object(sys, "argv", [
        "labclaw", "pipeline", "--once",
        "--data-dir", str(data_dir),
        "--max-llm-calls", "0",
    ]):
        main()
    out = capsys.readouterr().out
    result = json.loads(out)
    assert result["success"] is True


# ---------------------------------------------------------------------------
# cli.py: ablation command dispatch (covers elif cmd == "ablation" line)
# ---------------------------------------------------------------------------


def test_main_dispatches_ablation_cmd() -> None:
    """'ablation' command dispatches to _ablation_cmd."""
    import labclaw.cli as cli_mod

    with (
        patch.object(sys, "argv", ["labclaw", "ablation", "--help"]),
        patch.object(cli_mod, "_ablation_cmd") as mock_ablation,
    ):
        cli_mod.main()

    mock_ablation.assert_called_once_with(["--help"])


# ---------------------------------------------------------------------------
# cli.py: _ablation_cmd body
# ---------------------------------------------------------------------------


def test_ablation_cmd_help(capsys: pytest.CaptureFixture[str]) -> None:
    """_ablation_cmd --help prints usage."""
    with patch.object(sys, "argv", ["labclaw", "ablation", "--help"]):
        main()
    out = capsys.readouterr().out
    assert "data-dir" in out


def test_ablation_cmd_no_args_exits() -> None:
    """_ablation_cmd with no args exits with error."""
    with patch.object(sys, "argv", ["labclaw", "ablation"]):
        with pytest.raises(SystemExit):
            main()


def test_ablation_cmd_missing_data_dir_flag() -> None:
    """_ablation_cmd with unknown flag (exercises else branch) and no --data-dir exits."""
    with patch.object(sys, "argv", ["labclaw", "ablation", "--unknown-flag", "--n-cycles", "2"]):
        with pytest.raises(SystemExit):
            main()


def test_ablation_cmd_nonexistent_dir(tmp_path: Path) -> None:
    """_ablation_cmd with non-existent data-dir exits."""
    with patch.object(sys, "argv", [
        "labclaw", "ablation",
        "--data-dir", str(tmp_path / "no_such"),
    ]):
        with pytest.raises(SystemExit):
            main()


def test_ablation_cmd_empty_dir(tmp_path: Path) -> None:
    """_ablation_cmd with empty data-dir exits."""
    d = tmp_path / "empty"
    d.mkdir()
    with patch.object(sys, "argv", [
        "labclaw", "ablation", "--data-dir", str(d),
    ]):
        with pytest.raises(SystemExit):
            main()


def test_ablation_cmd_runs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """_ablation_cmd runs with small data and produces JSON output."""
    data_dir = _make_data_dir(tmp_path, n=5)
    with patch.object(sys, "argv", [
        "labclaw", "ablation",
        "--data-dir", str(data_dir),
        "--n-cycles", "1",
        "--seed", "42",
    ]):
        main()
    out = capsys.readouterr().out
    output = json.loads(out)
    assert "full" in output
    assert "no_evolution" in output
    assert "comparison" in output


def test_ablation_cmd_stat_error_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """_ablation_cmd handles ValueError from stat test (p_value=None)."""
    from labclaw.validation.statistics import StatisticalValidator

    data_dir = _make_data_dir(tmp_path, n=5)
    with patch.object(sys, "argv", [
        "labclaw", "ablation",
        "--data-dir", str(data_dir),
        "--n-cycles", "1",
    ]):
        with patch.object(
            StatisticalValidator, "run_test", side_effect=ValueError("no variance")
        ):
            main()
    out = capsys.readouterr().out
    output = json.loads(out)
    assert output["comparison"]["p_value"] is None
    assert output["comparison"]["significant"] is None


# ---------------------------------------------------------------------------
# hypothesis.py: LLMHypothesisGenerator._build_prompt with constraints
# (Ensures the constraints block in _build_prompt is exercised)
# ---------------------------------------------------------------------------


def test_build_prompt_with_constraints() -> None:
    """Constraints in HypothesisInput are included in the prompt."""
    pattern = _make_pattern()
    inp = HypothesisInput(
        patterns=[pattern],
        constraints=["Must use <10 animals", "Session < 2 hours"],
    )
    prompt = LLMHypothesisGenerator._build_prompt(inp)
    assert "Must use <10 animals" in prompt
    assert "Session < 2 hours" in prompt
    assert "Constraints:" in prompt


def test_build_prompt_with_context() -> None:
    """Context string in HypothesisInput is included in the prompt."""
    pattern = _make_pattern()
    inp = HypothesisInput(
        patterns=[pattern],
        context="Neuroscience experiment with running wheel",
    )
    prompt = LLMHypothesisGenerator._build_prompt(inp)
    assert "Neuroscience experiment" in prompt
    assert "Domain context:" in prompt


class TestLLMHypothesisPromptContextFindings:
    """Cover hypothesis.py lines 386-397: context_findings in LLM prompt."""

    def test_build_prompt_with_context_findings(self) -> None:
        from labclaw.discovery.hypothesis import HypothesisInput, LLMHypothesisGenerator
        from labclaw.discovery.mining import PatternRecord

        h_input = HypothesisInput(
            patterns=[
                PatternRecord(
                    pattern_type="correlation",
                    description="speed correlates with distance",
                    columns=["speed", "distance"],
                    strength=0.8,
                    metadata={},
                )
            ],
            context="neuroscience",
            context_findings=[
                {"description": "Past finding about grooming"},
                {"statement": "Speed increases with age"},
                {"finding_id": "f-003"},
            ],
        )

        prompt = LLMHypothesisGenerator._build_prompt(h_input)
        assert "Past findings (3)" in prompt
        assert "Past finding about grooming" in prompt
        assert "Speed increases with age" in prompt
        assert "f-003" in prompt
        assert "Build on these past findings" in prompt
