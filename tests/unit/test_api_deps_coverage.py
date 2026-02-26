"""Coverage tests for src/labclaw/api/deps.py — LLM provider and hypothesis generator paths."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from starlette.requests import Request

import labclaw.api.deps as deps

# ---------------------------------------------------------------------------
# Helpers: always reset singletons between tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_deps():
    """Clear all lru_cache singletons before and after every test."""
    deps.reset_all()
    yield
    deps.reset_all()


# ---------------------------------------------------------------------------
# get_llm_provider — Lines 85-89 (API key set, provider created successfully)
# ---------------------------------------------------------------------------


class TestGetLlmProviderWithKey:
    def test_returns_provider_when_api_key_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When env var has a value, _factory is called and returns a provider."""
        mock_provider = MagicMock()
        mock_provider.model_name = "test-model"

        mock_cfg = MagicMock()
        mock_cfg.llm.api_key_env = "TEST_LLM_KEY"
        mock_cfg.llm.provider = "anthropic"
        mock_cfg.llm.model = "claude-test"

        monkeypatch.setenv("TEST_LLM_KEY", "sk-test-key-123")

        with (
            patch("labclaw.config.load_config", return_value=mock_cfg),
            patch("labclaw.llm.get_llm_provider", return_value=mock_provider) as mock_factory,
        ):
            result = deps.get_llm_provider()

        assert result is mock_provider
        mock_factory.assert_called_once_with(
            "anthropic", model="claude-test", api_key="sk-test-key-123"
        )

    def test_returns_none_when_no_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When env var is empty, returns None."""
        mock_cfg = MagicMock()
        mock_cfg.llm.api_key_env = "MISSING_LLM_KEY"

        monkeypatch.delenv("MISSING_LLM_KEY", raising=False)

        with patch("labclaw.config.load_config", return_value=mock_cfg):
            result = deps.get_llm_provider()

        assert result is None

    def test_factory_exception_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When _factory raises, provider returns None (Lines 123-125)."""
        mock_cfg = MagicMock()
        mock_cfg.llm.api_key_env = "TEST_LLM_KEY"
        mock_cfg.llm.provider = "bad_provider"
        mock_cfg.llm.model = "model-x"

        monkeypatch.setenv("TEST_LLM_KEY", "some-key")

        with (
            patch("labclaw.config.load_config", return_value=mock_cfg),
            patch("labclaw.llm.get_llm_provider", side_effect=ValueError("bad provider")),
        ):
            result = deps.get_llm_provider()

        assert result is None


# ---------------------------------------------------------------------------
# get_hypothesis_generator — Lines 113-125
# ---------------------------------------------------------------------------


class TestGetHypothesisGenerator:
    def test_returns_llm_generator_when_llm_available(self, tmp_path: Path) -> None:
        """When get_llm_provider() returns a provider, use LLMHypothesisGenerator."""
        from labclaw.discovery.hypothesis import LLMHypothesisGenerator

        mock_provider = MagicMock()
        mock_provider.model_name = "test-model"

        deps.set_memory_root(tmp_path)

        with patch.object(deps, "get_llm_provider", return_value=mock_provider):
            gen = deps.get_hypothesis_generator()

        assert isinstance(gen, LLMHypothesisGenerator)

    def test_returns_base_generator_when_no_llm(self, tmp_path: Path) -> None:
        """When get_llm_provider() returns None, use HypothesisGenerator."""
        from labclaw.discovery.hypothesis import HypothesisGenerator

        deps.set_memory_root(tmp_path)

        with patch.object(deps, "get_llm_provider", return_value=None):
            gen = deps.get_hypothesis_generator()

        assert isinstance(gen, HypothesisGenerator)


def _request(
    path: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    client: tuple[str, int] = ("127.0.0.1", 12345),
) -> Request:
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [
            (k.lower().encode("latin-1"), v.encode("latin-1")) for k, v in (headers or {}).items()
        ],
        "client": client,
        "server": ("testserver", 80),
        "scheme": "http",
    }
    return Request(scope)


class TestSecurityHelpersCoverage:
    def test_get_latest_patterns_non_empty(self) -> None:
        from labclaw.discovery.mining import MiningConfig

        rows = [{"x": float(i), "y": float(i * 2)} for i in range(1, 12)]
        deps.get_pattern_miner().mine(rows, MiningConfig(min_sessions=3))
        assert len(deps.get_latest_patterns()) > 0

    def test_extract_presented_token_supports_x_api_key(self) -> None:
        req = _request("/api/events/", headers={"X-API-Key": "abc123"})
        assert deps._extract_presented_token(req) == "abc123"

    def test_extract_presented_token_returns_none_when_missing(self) -> None:
        req = _request("/api/events/")
        assert deps._extract_presented_token(req) is None

    def test_map_action_from_request_branches(self) -> None:
        assert deps._map_action_from_request(_request("/api/events/", method="GET")) == "read"
        assert (
            deps._map_action_from_request(_request("/api/evolution/run", method="POST"))
            == "execute"
        )
        assert deps._map_action_from_request(_request("/api/events/", method="POST")) == "write"
        assert deps._map_action_from_request(_request("/api/events/", method="PATCH")) == "execute"
        assert deps._map_action_from_request(_request("/api/events/", method="TRACE")) == "read"

    def test_auth_exempt_path_helper(self) -> None:
        assert deps._is_auth_exempt_path("/api/health")

    def test_rate_limit_parsing_and_disabled_paths(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LABCLAW_RATE_LIMIT_ENABLED", "1")
        monkeypatch.setenv("LABCLAW_RATE_LIMIT_PER_MINUTE", "not-an-int")
        deps._apply_rate_limit_or_429(_request("/api/events/"))
        # Exempt path should return early even when limiter is enabled.
        deps._apply_rate_limit_or_429(_request("/api/health"))
        monkeypatch.setenv("LABCLAW_RATE_LIMIT_PER_MINUTE", "0")
        deps._apply_rate_limit_or_429(_request("/api/events/"))

    def test_rate_limit_window_resets(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LABCLAW_RATE_LIMIT_ENABLED", "1")
        monkeypatch.setenv("LABCLAW_RATE_LIMIT_PER_MINUTE", "10")
        with patch.object(deps.time, "monotonic", side_effect=[0.0, 61.0]):
            deps._apply_rate_limit_or_429(_request("/api/events/"))
            deps._apply_rate_limit_or_429(_request("/api/events/"))

    def test_enforce_request_security_non_api_path(self) -> None:
        asyncio.run(deps.enforce_request_security(_request("/not-api")))

    def test_enforce_request_security_exempt_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LABCLAW_RATE_LIMIT_ENABLED", "0")
        asyncio.run(deps.enforce_request_security(_request("/api/health")))
