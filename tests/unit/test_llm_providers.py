"""Tests for LLM provider abstraction layer."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from labclaw.llm import get_llm_provider
from labclaw.llm.provider import LLMConfig
from labclaw.llm.providers.anthropic import AnthropicProvider
from labclaw.llm.providers.local import LocalProvider
from labclaw.llm.providers.openai import OpenAIProvider

# ---------------------------------------------------------------------------
# Test response model
# ---------------------------------------------------------------------------


class DummyResponse(BaseModel):
    answer: str
    score: float = 0.0


# ---------------------------------------------------------------------------
# LLMConfig
# ---------------------------------------------------------------------------


class TestLLMConfig:
    def test_basic_config(self) -> None:
        cfg = LLMConfig(
            provider="anthropic",
            model="claude-sonnet-4-6",
            api_key_env="ANTHROPIC_API_KEY",
        )
        assert cfg.provider == "anthropic"
        assert cfg.temperature == 0.7
        assert cfg.max_tokens == 4096
        assert cfg.fallback_provider is None

    def test_custom_values(self) -> None:
        cfg = LLMConfig(
            provider="openai",
            model="gpt-4o",
            api_key_env="OPENAI_API_KEY",
            temperature=0.3,
            max_tokens=4096,
            fallback_provider="local",
        )
        assert cfg.temperature == 0.3
        assert cfg.max_tokens == 4096
        assert cfg.fallback_provider == "local"


# ---------------------------------------------------------------------------
# get_llm_provider factory
# ---------------------------------------------------------------------------


class TestGetLLMProvider:
    def test_local_provider(self) -> None:
        p = get_llm_provider("local", model="llama3.2")
        assert isinstance(p, LocalProvider)
        assert p.model_name == "llama3.2"

    def test_openai_provider(self) -> None:
        p = get_llm_provider("openai", api_key="test-key")
        assert isinstance(p, OpenAIProvider)

    def test_anthropic_provider(self) -> None:
        p = get_llm_provider("anthropic", api_key="test-key")
        assert isinstance(p, AnthropicProvider)

    def test_unknown_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            get_llm_provider("foo")


# ---------------------------------------------------------------------------
# LocalProvider
# ---------------------------------------------------------------------------


class TestLocalProvider:
    def test_model_name(self) -> None:
        p = LocalProvider(model="custom-model")
        assert p.model_name == "custom-model"

    @pytest.mark.asyncio
    async def test_complete(self) -> None:
        p = LocalProvider(model="llama3.2")
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"response": "Hello world"}

        p._client.post = AsyncMock(return_value=mock_resp)
        result = await p.complete("Say hi")
        assert result == "Hello world"
        p._client.post.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_complete_with_system(self) -> None:
        p = LocalProvider()
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"response": "sys reply"}

        p._client.post = AsyncMock(return_value=mock_resp)
        result = await p.complete("prompt", system="Be helpful")
        assert result == "sys reply"

    @pytest.mark.asyncio
    async def test_complete_structured(self) -> None:
        p = LocalProvider()
        json_str = json.dumps({"answer": "42", "score": 0.9})
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"response": json_str}

        p._client.post = AsyncMock(return_value=mock_resp)
        result = await p.complete_structured("test", response_model=DummyResponse)
        assert isinstance(result, DummyResponse)
        assert result.answer == "42"

    @pytest.mark.asyncio
    async def test_complete_structured_strips_fences(self) -> None:
        p = LocalProvider()
        json_str = '```json\n{"answer": "fenced", "score": 1.0}\n```'
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"response": json_str}

        p._client.post = AsyncMock(return_value=mock_resp)
        result = await p.complete_structured("test", response_model=DummyResponse)
        assert isinstance(result, DummyResponse)
        assert result.answer == "fenced"


# ---------------------------------------------------------------------------
# OpenAIProvider
# ---------------------------------------------------------------------------


class TestOpenAIProvider:
    def test_missing_key_raises(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="OPENAI_API_KEY"):
                OpenAIProvider(api_key=None)

    def test_model_name(self) -> None:
        p = OpenAIProvider(api_key="test-key", model="gpt-4o")
        assert p.model_name == "gpt-4o"

    @pytest.mark.asyncio
    async def test_complete(self) -> None:
        p = OpenAIProvider(api_key="test-key")

        mock_msg = MagicMock()
        mock_msg.content = "Hello from OpenAI"
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        p._client.chat.completions.create = AsyncMock(return_value=mock_response)
        result = await p.complete("Hi")
        assert result == "Hello from OpenAI"

    @pytest.mark.asyncio
    async def test_complete_with_system(self) -> None:
        p = OpenAIProvider(api_key="test-key")

        mock_msg = MagicMock()
        mock_msg.content = "sys response"
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        p._client.chat.completions.create = AsyncMock(return_value=mock_response)
        result = await p.complete("Hi", system="Be nice")
        assert result == "sys response"

    @pytest.mark.asyncio
    async def test_complete_structured(self) -> None:
        p = OpenAIProvider(api_key="test-key")

        mock_func = MagicMock()
        mock_func.arguments = json.dumps({"answer": "OpenAI", "score": 0.5})
        mock_call = MagicMock()
        mock_call.function = mock_func
        mock_msg = MagicMock()
        mock_msg.tool_calls = [mock_call]
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        p._client.chat.completions.create = AsyncMock(return_value=mock_response)
        result = await p.complete_structured("test", response_model=DummyResponse)
        assert isinstance(result, DummyResponse)
        assert result.answer == "OpenAI"


# ---------------------------------------------------------------------------
# AnthropicProvider
# ---------------------------------------------------------------------------


class TestAnthropicProvider:
    def test_missing_key_raises(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
                AnthropicProvider(api_key=None)

    def test_model_name(self) -> None:
        p = AnthropicProvider(api_key="test-key")
        assert p.model_name == "claude-sonnet-4-6"

    @pytest.mark.asyncio
    async def test_complete(self) -> None:
        p = AnthropicProvider(api_key="test-key")

        mock_block = MagicMock()
        mock_block.text = "Hello from Claude"
        mock_msg = MagicMock()
        mock_msg.content = [mock_block]

        p._client.messages.create = AsyncMock(return_value=mock_msg)
        result = await p.complete("Hi")
        assert result == "Hello from Claude"

    @pytest.mark.asyncio
    async def test_complete_structured(self) -> None:
        p = AnthropicProvider(api_key="test-key")

        mock_tool_block = MagicMock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.name = "DummyResponse"
        mock_tool_block.input = {"answer": "Claude", "score": 0.8}
        mock_msg = MagicMock()
        mock_msg.content = [mock_tool_block]

        p._client.messages.create = AsyncMock(return_value=mock_msg)
        result = await p.complete_structured("test", response_model=DummyResponse)
        assert isinstance(result, DummyResponse)
        assert result.answer == "Claude"

    @pytest.mark.asyncio
    async def test_complete_structured_fallback_text(self) -> None:
        p = AnthropicProvider(api_key="test-key")

        mock_text_block = MagicMock()
        mock_text_block.type = "text"
        mock_text_block.text = json.dumps({"answer": "fallback", "score": 0.1})
        mock_msg = MagicMock()
        mock_msg.content = [mock_text_block]

        p._client.messages.create = AsyncMock(return_value=mock_msg)
        result = await p.complete_structured("test", response_model=DummyResponse)
        assert isinstance(result, DummyResponse)
        assert result.answer == "fallback"
