"""Configuration loader for LabClaw."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG = Path(__file__).resolve().parent.parent.parent / "configs" / "default.yaml"


class SystemConfig(BaseModel):
    name: str = "labclaw"
    version: str = "0.0.1"
    log_level: str = "INFO"


class GraphConfig(BaseModel):
    backend: str = "sqlite"
    path: str = "data/labclaw.db"


class EventsConfig(BaseModel):
    backend: str = "memory"
    redis_url: str = "redis://localhost:6379"


class APIConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000


class EdgeConfig(BaseModel):
    watch_paths: list[str] = []
    poll_interval_seconds: int = 5


class AgentsConfig(BaseModel):
    default_model: str = "claude-sonnet-4-6"
    max_tool_calls: int = 20


class LLMConfigFallback(BaseModel):
    """Standalone LLM config used when llm package is not yet available."""

    provider: str = "anthropic"
    model: str = "claude-sonnet-4-6"
    api_key_env: str = "ANTHROPIC_API_KEY"
    temperature: float = 0.7
    max_tokens: int = 4096


def _get_llm_config_class() -> type[BaseModel]:
    """Return LLMConfig from llm.provider if available, else fallback."""
    try:
        from labclaw.llm.provider import LLMConfig

        return LLMConfig
    except ImportError:
        return LLMConfigFallback


class LabClawConfig(BaseModel):
    system: SystemConfig = SystemConfig()
    llm: Any = None  # Populated by load_config or default
    graph: GraphConfig = GraphConfig()
    events: EventsConfig = EventsConfig()
    api: APIConfig = APIConfig()
    edge: EdgeConfig = EdgeConfig()
    agents: AgentsConfig = AgentsConfig()

    def model_post_init(self, __context: Any) -> None:
        if self.llm is None:
            cls = _get_llm_config_class()
            self.llm = cls()


def load_config(path: Path | None = None) -> LabClawConfig:
    """Load config from YAML. Falls back to configs/default.yaml."""
    config_path = path or _DEFAULT_CONFIG
    if config_path.exists():
        with open(config_path) as f:
            data = yaml.safe_load(f) or {}
        logger.info("Loaded config from %s", config_path)
        return LabClawConfig.model_validate(data)
    logger.warning("Config file %s not found, using defaults", config_path)
    return LabClawConfig()
