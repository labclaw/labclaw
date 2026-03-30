"""Cover config.py uncovered lines 56-57.

Lines 56-57: load_config finds a file on _SEARCH_PATHS (not explicit path).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from labclaw.config import LabclawConfig, load_config


class TestLoadConfigSearchPath:
    """load_config discovers config from default search paths."""

    def test_loads_from_search_path(self, tmp_path: Path) -> None:
        config_file = tmp_path / "labclaw.yaml"
        config_file.write_text("brain:\n  port: 7777\n")

        with patch("labclaw.config._SEARCH_PATHS", [config_file]):
            cfg = load_config(path=None)

        assert isinstance(cfg, LabclawConfig)
        assert cfg.brain.port == 7777
