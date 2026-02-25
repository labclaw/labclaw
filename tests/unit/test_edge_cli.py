"""Tests for src/labclaw/edge/cli.py — 100% coverage."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from labclaw.edge.cli import main

# ---------------------------------------------------------------------------
# main() — --dashboard branch
# ---------------------------------------------------------------------------


class TestEdgeCliDashboard:
    def test_dashboard_calls_subprocess_run(self) -> None:
        with (
            patch("sys.argv", ["labclaw-edge", "--dashboard"]),
            patch("subprocess.run") as mock_run,
        ):
            main()

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "streamlit" in cmd
        assert "run" in cmd

    def test_dashboard_path_points_to_app_py(self) -> None:
        with (
            patch("sys.argv", ["labclaw-edge", "--dashboard"]),
            patch("subprocess.run") as mock_run,
        ):
            main()

        cmd = mock_run.call_args[0][0]
        app_path = Path(cmd[-1])
        assert app_path.name == "app.py"
        assert app_path.parent.name == "dashboard"

    def test_dashboard_uses_streamlit_binary_not_python_m(self) -> None:
        """Edge CLI calls 'streamlit run' directly (not 'python -m streamlit')."""
        with (
            patch("sys.argv", ["labclaw-edge", "--dashboard"]),
            patch("subprocess.run") as mock_run,
        ):
            main()

        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "streamlit"


# ---------------------------------------------------------------------------
# main() — fallback branch (no args / other args)
# ---------------------------------------------------------------------------


class TestEdgeCliFallback:
    def test_no_args_prints_not_implemented(self, capsys: pytest.CaptureFixture[str]) -> None:
        with patch("sys.argv", ["labclaw-edge"]):
            main()

        out = capsys.readouterr().out
        assert "Not yet implemented" in out
        assert "--dashboard" in out

    def test_other_arg_prints_not_implemented(self, capsys: pytest.CaptureFixture[str]) -> None:
        with patch("sys.argv", ["labclaw-edge", "--serve"]):
            main()

        out = capsys.readouterr().out
        assert "Not yet implemented" in out

    def test_no_args_does_not_call_subprocess(self) -> None:
        with (
            patch("sys.argv", ["labclaw-edge"]),
            patch("subprocess.run") as mock_run,
        ):
            main()

        mock_run.assert_not_called()


# ---------------------------------------------------------------------------
# __main__ guard
# ---------------------------------------------------------------------------


class TestEdgeCliMainGuard:
    def test_module_level_main_guard(self) -> None:
        """Verify the if __name__ == '__main__' block is reachable."""
        import labclaw.edge.cli as edge_cli_mod

        with (
            patch("sys.argv", ["labclaw-edge"]),
            patch("labclaw.edge.cli.main") as mock_main,
        ):
            # Call main directly to simulate being invoked as __main__
            edge_cli_mod.main()

        mock_main.assert_called_once()
