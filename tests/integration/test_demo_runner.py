"""Integration tests for DemoRunner — end-to-end demo pipeline."""

from __future__ import annotations

from pathlib import Path

import pytest

from labclaw.demo.runner import _DOMAIN_FILES, _SAMPLE_DATA_DIR, DemoRunner

# ---------------------------------------------------------------------------
# Sample data files exist
# ---------------------------------------------------------------------------


class TestSampleData:
    def test_sample_data_dir_exists(self) -> None:
        assert _SAMPLE_DATA_DIR.is_dir()

    @pytest.mark.parametrize("domain", list(_DOMAIN_FILES))
    def test_sample_csv_exists(self, domain: str) -> None:
        path = _SAMPLE_DATA_DIR / _DOMAIN_FILES[domain]
        assert path.is_file(), f"Missing sample data: {path}"


# ---------------------------------------------------------------------------
# DemoRunner
# ---------------------------------------------------------------------------


class TestDemoRunner:
    def test_generic_domain(self, capsys: pytest.CaptureFixture[str]) -> None:
        runner = DemoRunner("generic")
        runner.run()
        captured = capsys.readouterr()
        assert "Demo Complete" in captured.out

    def test_neuroscience_domain(self, capsys: pytest.CaptureFixture[str]) -> None:
        runner = DemoRunner("neuroscience")
        runner.run()
        captured = capsys.readouterr()
        assert "Demo Complete" in captured.out

    def test_chemistry_domain(self, capsys: pytest.CaptureFixture[str]) -> None:
        runner = DemoRunner("chemistry")
        runner.run()
        captured = capsys.readouterr()
        assert "Demo Complete" in captured.out

    def test_keep_preserves_workspace(self) -> None:
        runner = DemoRunner("generic", keep=True)
        runner.run()
        # After run, _root should still exist because keep=True
        assert runner._root is not None
        root = Path(runner._root)
        assert root.exists()
        # Clean up manually
        import shutil
        shutil.rmtree(root, ignore_errors=True)

    def test_invalid_domain_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown domain"):
            DemoRunner("invalid_domain")

    def test_workspace_cleaned_without_keep(self) -> None:
        runner = DemoRunner("generic", keep=False)
        runner.run()
        # After run with keep=False, the tmpdir should be cleaned up
        assert runner._root is not None
        assert not Path(runner._root).exists()
