"""Tests for config.py search path loading.

Covers lines 55-57: _parse(p) called when a search-path config file exists.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from labclaw.config import load_config


class TestLoadConfigSearchPath:
    """Cover lines 55-57: config found via search path (not explicit path)."""

    def test_loads_from_home_search_path(self, tmp_path: Path) -> None:
        """When no explicit path, finds config in home search path."""
        config_dir = tmp_path / ".labclaw"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        config_file.write_text("brain:\n  port: 9999\nllm:\n  model: gpt-4o\n")

        search_paths = [
            Path("/nonexistent/labclaw.yaml"),
            config_file,
        ]

        with patch("labclaw.config._SEARCH_PATHS", search_paths):
            cfg = load_config(None)
            assert cfg.brain.port == 9999
            assert cfg.llm.model == "gpt-4o"

    def test_loads_from_cwd_search_path(self, tmp_path: Path) -> None:
        """When labclaw.yaml exists in cwd, loads from it."""
        config_file = tmp_path / "labclaw.yaml"
        config_file.write_text("llm:\n  provider: openai\n")

        search_paths = [
            config_file,
            Path("/nonexistent/.labclaw/config.yaml"),
        ]

        with patch("labclaw.config._SEARCH_PATHS", search_paths):
            cfg = load_config(None)
            assert cfg.llm.provider == "openai"

    def test_first_matching_search_path_wins(self, tmp_path: Path) -> None:
        """First matching search path takes priority."""
        first = tmp_path / "labclaw.yaml"
        first.write_text("brain:\n  port: 1111\n")
        second = tmp_path / ".labclaw" / "config.yaml"
        second.parent.mkdir()
        second.write_text("brain:\n  port: 2222\n")

        search_paths = [first, second]

        with patch("labclaw.config._SEARCH_PATHS", search_paths):
            cfg = load_config(None)
            assert cfg.brain.port == 1111
