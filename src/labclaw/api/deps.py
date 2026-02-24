"""Shared FastAPI dependencies — singleton instances for dependency injection.

Each dependency is a ``lru_cache``-wrapped factory so that every request
shares the same in-memory state (registry, chronicle, etc.).
"""

from __future__ import annotations

import logging
import os
import threading
from functools import lru_cache
from pathlib import Path

from labclaw.core.events import event_registry
from labclaw.discovery.hypothesis import HypothesisGenerator, LLMHypothesisGenerator
from labclaw.discovery.mining import PatternMiner
from labclaw.edge.session_chronicle import SessionChronicle
from labclaw.evolution.engine import EvolutionEngine
from labclaw.hardware.registry import DeviceRegistry
from labclaw.llm.provider import LLMProvider
from labclaw.memory.markdown import TierABackend

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configurable root for Tier A memory
# ---------------------------------------------------------------------------

_memory_root: Path | None = None
_memory_root_lock = threading.Lock()
_data_dir: Path | None = None
_data_dir_lock = threading.Lock()


def set_memory_root(root: Path) -> None:
    """Override the memory root (call before first request, e.g. in tests)."""
    global _memory_root  # noqa: PLW0603
    with _memory_root_lock:
        _memory_root = root
        get_tier_a_backend.cache_clear()
        get_session_chronicle.cache_clear()


def _default_memory_root() -> Path:
    if _memory_root is not None:
        return _memory_root
    return Path("lab")


def set_data_dir(path: Path) -> None:
    """Override the data directory used by session recording validation."""
    global _data_dir  # noqa: PLW0603
    with _data_dir_lock:
        _data_dir = path.resolve()


# ---------------------------------------------------------------------------
# Singleton factories
# ---------------------------------------------------------------------------

@lru_cache
def get_device_registry() -> DeviceRegistry:
    return DeviceRegistry()


@lru_cache
def get_tier_a_backend() -> TierABackend:
    return TierABackend(root=_default_memory_root())


@lru_cache
def get_session_chronicle() -> SessionChronicle:
    return SessionChronicle(memory=get_tier_a_backend())


@lru_cache
def get_pattern_miner() -> PatternMiner:
    return PatternMiner()


@lru_cache
def get_hypothesis_generator() -> HypothesisGenerator | LLMHypothesisGenerator:
    """Get hypothesis generator. Uses LLM if available, otherwise templates."""
    llm = get_llm_provider()
    if llm is not None:
        logger.info("Using LLM-powered hypothesis generator (%s)", llm.model_name)
        return LLMHypothesisGenerator(llm)
    return HypothesisGenerator()


@lru_cache
def get_evolution_engine() -> EvolutionEngine:
    return EvolutionEngine()


def get_data_dir() -> Path:
    """Return the configured data directory for file validation."""
    with _data_dir_lock:
        if _data_dir is not None:
            return _data_dir
    return Path(os.environ.get("LABCLAW_DATA_DIR", "/opt/labclaw/data"))


def get_event_registry():  # noqa: ANN201
    """Return the global event registry singleton (no caching needed)."""
    return event_registry


@lru_cache
def get_llm_provider() -> LLMProvider | None:
    """Get configured LLM provider. Returns None if no API key available."""
    from labclaw.config import load_config
    from labclaw.llm import get_llm_provider as _factory

    cfg = load_config()
    key = os.environ.get(cfg.llm.api_key_env, "")
    if not key:
        logger.warning("No API key found in %s, LLM provider unavailable", cfg.llm.api_key_env)
        return None
    try:
        return _factory(cfg.llm.provider, model=cfg.llm.model, api_key=key)
    except Exception:
        logger.exception("Failed to create LLM provider %s", cfg.llm.provider)
        return None


def reset_all() -> None:
    """Clear all cached singletons. For testing only."""
    global _memory_root  # noqa: PLW0603
    global _data_dir  # noqa: PLW0603
    with _memory_root_lock:
        _memory_root = None
    with _data_dir_lock:
        _data_dir = None
    for fn in (
        get_device_registry,
        get_tier_a_backend,
        get_session_chronicle,
        get_pattern_miner,
        get_hypothesis_generator,
        get_evolution_engine,
        get_llm_provider,
    ):
        fn.cache_clear()
