"""Tests for labclaw.config."""

from __future__ import annotations

from pathlib import Path

from labclaw.config import (
    BrainConfig,
    LabclawConfig,
    LLMConfig,
    SkillConfig,
    load_config,
)


class TestDefaults:
    """Default config values."""

    def test_brain_defaults(self) -> None:
        cfg = BrainConfig()
        assert cfg.port == 18802
        assert cfg.api_keys_env == "LABCLAW_API_KEYS"
        assert cfg.rate_limit == "60/minute"
        assert cfg.max_request_size == 1_048_576
        assert cfg.max_response_size == 100_000

    def test_skill_defaults(self) -> None:
        cfg = SkillConfig()
        assert cfg.enabled is True
        assert cfg.timeout == 30
        assert cfg.lazy_loading is True

    def test_llm_defaults(self) -> None:
        cfg = LLMConfig()
        assert cfg.provider == "anthropic"
        assert cfg.model == "claude-sonnet-4-6"
        assert cfg.api_key_env == "ANTHROPIC_API_KEY"
        assert cfg.temperature == 0.3
        assert cfg.max_tokens == 4096

    def test_labclaw_config_defaults(self) -> None:
        cfg = LabclawConfig()
        assert cfg.brain.port == 18802
        assert cfg.skills == {}
        assert cfg.llm.provider == "anthropic"


class TestLoadConfig:
    """load_config function."""

    def test_load_from_explicit_path(self, tmp_path: Path) -> None:
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("brain:\n  port: 9999\nllm:\n  model: gpt-4o\n")
        cfg = load_config(yaml_file)
        assert cfg.brain.port == 9999
        assert cfg.llm.model == "gpt-4o"

    def test_load_with_skills(self, tmp_path: Path) -> None:
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("skills:\n  tooluniverse:\n    enabled: true\n    timeout: 60\n")
        cfg = load_config(yaml_file)
        assert "tooluniverse" in cfg.skills
        assert cfg.skills["tooluniverse"].timeout == 60

    def test_fallback_to_defaults_no_file(self) -> None:
        cfg = load_config(Path("/nonexistent/path/config.yaml"))
        assert cfg.brain.port == 18802
        assert cfg.llm.provider == "anthropic"

    def test_fallback_to_defaults_none(self) -> None:
        cfg = load_config(None)
        assert isinstance(cfg, LabclawConfig)

    def test_empty_yaml_returns_defaults(self, tmp_path: Path) -> None:
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("")
        cfg = load_config(yaml_file)
        assert cfg.brain.port == 18802

    def test_partial_yaml_fills_defaults(self, tmp_path: Path) -> None:
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("brain:\n  port: 5555\n")
        cfg = load_config(yaml_file)
        assert cfg.brain.port == 5555
        assert cfg.brain.rate_limit == "60/minute"
        assert cfg.llm.provider == "anthropic"
