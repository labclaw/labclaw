"""Configuration loading for labclaw."""

from __future__ import annotations

import logging
from pathlib import Path

import yaml
from pydantic import BaseModel

logger = logging.getLogger(__name__)

_SEARCH_PATHS = [
    Path("labclaw.yaml"),
    Path.home() / ".labclaw" / "config.yaml",
]


class BrainConfig(BaseModel):
    port: int = 18802
    api_keys_env: str = "LABCLAW_API_KEYS"
    rate_limit: str = "60/minute"
    max_request_size: int = 1_048_576
    max_response_size: int = 100_000


class SkillConfig(BaseModel):
    enabled: bool = True
    timeout: int = 30
    lazy_loading: bool = True


class LLMConfig(BaseModel):
    provider: str = "anthropic"
    model: str = "claude-sonnet-4-6"
    api_key_env: str = "ANTHROPIC_API_KEY"
    temperature: float = 0.3
    max_tokens: int = 4096


class LabclawConfig(BaseModel):
    brain: BrainConfig = BrainConfig()
    skills: dict[str, SkillConfig] = {}
    llm: LLMConfig = LLMConfig()


def load_config(path: Path | None = None) -> LabclawConfig:
    """Load config from file or defaults.

    Search: explicit path -> ./labclaw.yaml -> ~/.labclaw/config.yaml -> defaults.
    """
    if path and path.exists():
        return _parse(path)
    for p in _SEARCH_PATHS:
        if p.exists():
            logger.info("Loading config from %s", p)
            return _parse(p)
    logger.debug("No config file found, using defaults")
    return LabclawConfig()


def _parse(path: Path) -> LabclawConfig:
    data = yaml.safe_load(path.read_text()) or {}
    return LabclawConfig(**data)
