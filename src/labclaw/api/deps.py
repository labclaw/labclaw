"""Shared FastAPI dependencies — singleton instances for dependency injection.

Each dependency is a ``lru_cache``-wrapped factory so that every request
shares the same in-memory state (registry, chronicle, etc.).
"""

from __future__ import annotations

import logging
import os
import secrets
import threading
import time
from functools import lru_cache
from pathlib import Path

from fastapi import HTTPException, Request, status

from labclaw.core.events import event_registry
from labclaw.core.governance import GovernanceEngine, SafetyLevel
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
_rate_limit_lock = threading.Lock()
_rate_limit_window: dict[str, tuple[float, int]] = {}
_MAX_RATE_LIMIT_KEYS = 50_000

_AUTH_EXEMPT_PATHS = {"/api/health", "/api/metrics"}
_AUTH_EXEMPT_PREFIXES = ("/docs", "/redoc", "/openapi.json")


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


def get_latest_patterns() -> list:
    """Return patterns from the latest mining run, or an empty list."""
    miner = get_pattern_miner()
    last = getattr(miner, "last_result", None)
    if last is None:
        return []
    return list(last.patterns)


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
def get_governance_engine() -> GovernanceEngine:
    """Return process-wide governance engine used by API request checks."""
    return GovernanceEngine()


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _running_under_pytest() -> bool:
    return "PYTEST_CURRENT_TEST" in os.environ


def _auth_required() -> bool:
    # Secure by default outside tests; tests can override with env.
    return _env_bool("LABCLAW_API_AUTH_REQUIRED", not _running_under_pytest())


def _governance_required() -> bool:
    return _env_bool("LABCLAW_GOVERNANCE_ENFORCE", not _running_under_pytest())


def _rate_limit_enabled() -> bool:
    return _env_bool("LABCLAW_RATE_LIMIT_ENABLED", not _running_under_pytest())


@lru_cache
def _api_tokens() -> tuple[str, ...]:
    raw = os.environ.get("LABCLAW_API_TOKENS") or os.environ.get("LABCLAW_API_TOKEN", "")
    tokens = tuple(tok.strip() for tok in raw.split(",") if tok.strip())
    return tokens


def _extract_presented_token(request: Request) -> str | None:
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        if token:
            return token
    api_key = request.headers.get("x-api-key", "").strip()
    if api_key:
        return api_key
    return None


def _is_auth_exempt_path(path: str) -> bool:
    if path in _AUTH_EXEMPT_PATHS:
        return True
    return path.startswith(_AUTH_EXEMPT_PREFIXES)


def _map_action_from_request(request: Request) -> str:
    method = request.method.upper()
    path = request.url.path
    if method in {"GET", "HEAD", "OPTIONS"}:
        return "read"
    if path.startswith("/api/evolution") or path.startswith("/api/orchestrator"):
        return "execute"
    if method == "POST":
        return "write"
    if method in {"PUT", "PATCH", "DELETE"}:
        return "execute"
    return "read"


def _apply_rate_limit_or_429(request: Request) -> None:
    if not _rate_limit_enabled():
        return
    path = request.url.path
    if _is_auth_exempt_path(path):
        return

    try:
        limit_per_minute = int(os.environ.get("LABCLAW_RATE_LIMIT_PER_MINUTE", "120"))
    except ValueError:
        limit_per_minute = 120
    if limit_per_minute <= 0:
        return

    host = request.client.host if request.client is not None else "unknown"
    key = f"{host}:{path}:{request.method.upper()}"
    now = time.monotonic()

    with _rate_limit_lock:
        start, count = _rate_limit_window.get(key, (now, 0))
        if now - start >= 60:
            start = now
            count = 0
        count += 1
        _rate_limit_window[key] = (start, count)
        if len(_rate_limit_window) > _MAX_RATE_LIMIT_KEYS:
            oldest_key = min(_rate_limit_window, key=lambda k: _rate_limit_window[k][0])
            del _rate_limit_window[oldest_key]

    if count > limit_per_minute:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
        )


async def enforce_request_security(request: Request) -> None:
    """Shared API gate: auth, governance, and request rate limiting."""
    path = request.url.path

    if not path.startswith("/api"):
        return

    _apply_rate_limit_or_429(request)

    if _is_auth_exempt_path(path):
        return

    if _auth_required():
        tokens = _api_tokens()
        if not tokens:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="API authentication is enabled but no API token is configured",
            )
        presented = _extract_presented_token(request)
        if not presented or not any(secrets.compare_digest(presented, t) for t in tokens):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized",
                headers={"WWW-Authenticate": "Bearer"},
            )

    if _governance_required():
        action = _map_action_from_request(request)
        actor = request.headers.get("x-labclaw-actor", "api-client")
        role = request.headers.get(
            "x-labclaw-role",
            os.environ.get("LABCLAW_API_DEFAULT_ROLE", "digital_intern"),
        )
        decision = get_governance_engine().check(
            action=action,
            actor=actor,
            role=role,
            context={"target": path, "method": request.method},
        )
        if (
            not decision.allowed
            or decision.safety_level == SafetyLevel.BLOCKED
            or decision.safety_level == SafetyLevel.REQUIRES_APPROVAL
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=decision.reason or "Forbidden",
            )


@lru_cache
def get_llm_provider() -> LLMProvider | None:
    """Get configured LLM provider. Returns None if no API key available."""
    from labclaw.config import load_config
    from labclaw.llm import get_llm_provider as _factory

    cfg = load_config()
    key = os.environ.get(cfg.llm.api_key_env, "")
    if not key:
        logger.warning("No LLM API key configured; LLM provider unavailable")
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
        get_governance_engine,
        get_llm_provider,
        _api_tokens,
    ):
        fn.cache_clear()
    with _rate_limit_lock:
        _rate_limit_window.clear()
