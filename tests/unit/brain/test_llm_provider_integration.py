"""Tests for brain LLM provider integration."""

from __future__ import annotations

import os
from unittest.mock import patch

from labclaw.brain import _create_llm_provider


class TestCreateLLMProvider:
    """Tests for _create_llm_provider function."""

    def test_fireworks_provider_created(self) -> None:
        """Test Fireworks provider is created when FIREWORKS_API_KEY is set."""
        with patch.dict(os.environ, {"FIREWORKS_API_KEY": "fw-test-key"}):
            provider = _create_llm_provider()

        assert provider is not None
        assert provider._api_key == "fw-test-key"
        assert provider._base_url == "https://api.fireworks.ai/inference/v1"

    def test_openai_provider_fallback(self) -> None:
        """Test OpenAI provider is created when only OPENAI_API_KEY is set."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "oa-test-key"}, clear=True):
            provider = _create_llm_provider()

        assert provider is not None
        assert provider._api_key == "oa-test-key"
        assert provider._base_url is None

    def test_fireworks_priority_over_openai(self) -> None:
        """Test Fireworks takes priority when both keys are set."""
        with patch.dict(
            os.environ,
            {"FIREWORKS_API_KEY": "fw-key", "OPENAI_API_KEY": "oa-key"},
        ):
            provider = _create_llm_provider()

        assert provider is not None
        assert provider._api_key == "fw-key"
        assert provider._base_url == "https://api.fireworks.ai/inference/v1"

    def test_no_provider_when_no_keys(self) -> None:
        """Test None is returned when no API keys are set."""
        with patch.dict(os.environ, {}, clear=True):
            provider = _create_llm_provider()

        assert provider is None

    def test_fireworks_init_failure_handled(self) -> None:
        """Test that Fireworks init failure is handled gracefully."""
        with patch.dict(os.environ, {"FIREWORKS_API_KEY": "fw-key"}):
            with patch(
                "labclaw.llm.providers.openai_provider.FireworksProvider",
                side_effect=ImportError("openai not installed"),
            ):
                provider = _create_llm_provider()

        assert provider is None

    def test_openai_init_failure_handled(self) -> None:
        """Test that OpenAI init failure is handled gracefully."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "oa-key"}, clear=True):
            with patch(
                "labclaw.llm.providers.openai_provider.OpenAIProvider",
                side_effect=ImportError("openai not installed"),
            ):
                provider = _create_llm_provider()

        assert provider is None
