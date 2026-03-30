"""Tests for OpenAI-compatible provider including Fireworks AI."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from labclaw.llm.providers.openai_provider import FireworksProvider, OpenAIProvider


class TestOpenAIProvider:
    """Tests for OpenAIProvider."""

    def test_init_with_api_key(self) -> None:
        """Test initialization with explicit API key."""
        provider = OpenAIProvider(api_key="test-key", model="gpt-4")
        assert provider._api_key == "test-key"
        assert provider._model == "gpt-4"
        assert provider._base_url is None
        assert provider._client is None

    def test_init_with_env_var(self) -> None:
        """Test initialization from environment variable."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "env-key"}):
            provider = OpenAIProvider()
            assert provider._api_key == "env-key"

    def test_init_no_key(self) -> None:
        """Test initialization with no API key."""
        with patch.dict(os.environ, {}, clear=True):
            provider = OpenAIProvider()
            assert provider._api_key == ""

    def test_model_name_property(self) -> None:
        """Test model_name property returns correct value."""
        provider = OpenAIProvider(model="test-model")
        assert provider.model_name == "test-model"

    @pytest.mark.asyncio
    async def test_complete_success(self) -> None:
        """Test successful completion."""
        provider = OpenAIProvider(api_key="test-key")

        # Mock the client and response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Test response"))]

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch.object(provider, "_get_client", return_value=mock_client):
            result = await provider.complete(
                "Hello", system="Be helpful", temperature=0.5, max_tokens=100
            )

        assert result == "Test response"
        mock_client.chat.completions.create.assert_called_once_with(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Be helpful"},
                {"role": "user", "content": "Hello"},
            ],
            temperature=0.5,
            max_tokens=100,
        )

    @pytest.mark.asyncio
    async def test_complete_no_system(self) -> None:
        """Test completion without system prompt."""
        provider = OpenAIProvider(api_key="test-key")

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Response"))]

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch.object(provider, "_get_client", return_value=mock_client):
            result = await provider.complete("Hello")

        assert result == "Response"
        mock_client.chat.completions.create.assert_called_once_with(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Hello"}],
            temperature=0.7,
            max_tokens=2048,
        )

    @pytest.mark.asyncio
    async def test_complete_empty_response(self) -> None:
        """Test handling of empty response content."""
        provider = OpenAIProvider(api_key="test-key")

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content=None))]

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch.object(provider, "_get_client", return_value=mock_client):
            result = await provider.complete("Hello")

        assert result == ""

    @pytest.mark.asyncio
    async def test_get_client_lazy_init_no_base_url(self) -> None:
        """Test lazy initialization of client without base_url."""
        provider = OpenAIProvider(api_key="test-key")

        assert provider._client is None
        assert provider._base_url is None

        with patch("labclaw.llm.providers.openai_provider.AsyncOpenAI") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            client = await provider._get_client()

            assert provider._client is client
            mock_client_class.assert_called_once_with(api_key="test-key")

    @pytest.mark.asyncio
    async def test_get_client_lazy_init(self) -> None:
        """Test lazy initialization of client."""
        provider = OpenAIProvider(api_key="test-key", base_url="https://api.example.com")

        assert provider._client is None

        client = await provider._get_client()

        assert provider._client is client
        assert client is not None

        # Second call should return same client
        client2 = await provider._get_client()
        assert client2 is client

    @pytest.mark.asyncio
    async def test_complete_structured_success(self) -> None:
        """Test successful structured completion."""
        from pydantic import BaseModel

        class TestResponse(BaseModel):
            answer: str
            confidence: float

        provider = OpenAIProvider(api_key="test-key")

        mock_parsed = TestResponse(answer="Test", confidence=0.95)
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(parsed=mock_parsed))]

        mock_client = AsyncMock()
        mock_client.beta.chat.completions.parse = AsyncMock(return_value=mock_response)

        with patch.object(provider, "_get_client", return_value=mock_client):
            result = await provider.complete_structured(
                "Test prompt",
                system="Be helpful",
                response_model=TestResponse,
                temperature=0.5,
            )

        assert result == mock_parsed
        assert result.answer == "Test"
        assert result.confidence == 0.95
        mock_client.beta.chat.completions.parse.assert_called_once()

    @pytest.mark.asyncio
    async def test_complete_structured_no_system(self) -> None:
        """Test structured completion without system prompt."""
        from pydantic import BaseModel

        class SimpleResponse(BaseModel):
            value: int

        provider = OpenAIProvider(api_key="test-key")

        mock_parsed = SimpleResponse(value=42)
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(parsed=mock_parsed))]

        mock_client = AsyncMock()
        mock_client.beta.chat.completions.parse = AsyncMock(return_value=mock_response)

        with patch.object(provider, "_get_client", return_value=mock_client):
            result = await provider.complete_structured(
                "Test",
                response_model=SimpleResponse,
            )

        assert result.value == 42
        call_args = mock_client.beta.chat.completions.parse.call_args
        assert call_args.kwargs["temperature"] == 0.7


class TestFireworksProvider:
    """Tests for FireworksProvider."""

    def test_init_with_api_key(self) -> None:
        """Test initialization with explicit API key."""
        provider = FireworksProvider(api_key="fw-key")
        assert provider._api_key == "fw-key"
        assert provider._base_url == "https://api.fireworks.ai/inference/v1"
        assert provider._model == "accounts/fireworks/models/kimi-k2p5"

    def test_init_with_env_var(self) -> None:
        """Test initialization from FIREWORKS_API_KEY environment variable."""
        with patch.dict(os.environ, {"FIREWORKS_API_KEY": "fw-env-key"}):
            provider = FireworksProvider()
            assert provider._api_key == "fw-env-key"

    def test_init_custom_model(self) -> None:
        """Test initialization with custom model."""
        provider = FireworksProvider(api_key="key", model="accounts/fireworks/models/deepseek-v3")
        assert provider._model == "accounts/fireworks/models/deepseek-v3"

    def test_inherits_openai_provider(self) -> None:
        """Test FireworksProvider inherits from OpenAIProvider."""
        assert issubclass(FireworksProvider, OpenAIProvider)


class TestProviderIntegration:
    """Integration-style tests for provider behavior."""

    @pytest.mark.asyncio
    async def test_fireworks_provider_complete(self) -> None:
        """Test Fireworks provider can complete (mocked)."""
        provider = FireworksProvider(api_key="test-key")

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Fireworks response"))]

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch.object(provider, "_get_client", return_value=mock_client):
            result = await provider.complete("Test prompt", temperature=0.3, max_tokens=50)

        assert result == "Fireworks response"
        mock_client.chat.completions.create.assert_called_once()
        call_args = mock_client.chat.completions.create.call_args
        assert call_args.kwargs["model"] == "accounts/fireworks/models/kimi-k2p5"
        assert call_args.kwargs["temperature"] == 0.3
        assert call_args.kwargs["max_tokens"] == 50
