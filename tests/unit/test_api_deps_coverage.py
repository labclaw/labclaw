"""Coverage tests for src/labclaw/api/deps.py — LLM provider and hypothesis generator paths."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

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
