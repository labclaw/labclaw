"""Tests for LiteLLM multi-model routing provider."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from labclaw.llm import get_llm_provider
from labclaw.llm.providers.litellm_provider import LiteLLMProvider


class DummyResponse(BaseModel):
    answer: str
    score: float = 0.0


class TestLiteLLMProviderInit:
    def test_default_model(self) -> None:
        p = LiteLLMProvider()
        assert p.model_name == "gpt-4o"

    def test_custom_model(self) -> None:
        p = LiteLLMProvider(model="claude-sonnet-4-6")
        assert p.model_name == "claude-sonnet-4-6"

    def test_fallback_models(self) -> None:
        p = LiteLLMProvider(fallback_models=["gpt-4o-mini", "claude-haiku-4-5"])
        assert p._fallback_models == ["gpt-4o-mini", "claude-haiku-4-5"]

    def test_no_fallback_defaults_empty(self) -> None:
        p = LiteLLMProvider()
        assert p._fallback_models == []

    def test_custom_timeout_and_retries(self) -> None:
        p = LiteLLMProvider(timeout=60, num_retries=5)
        assert p._timeout == 60
        assert p._num_retries == 5

    def test_api_key_stored(self) -> None:
        p = LiteLLMProvider(api_key="test-key-123")
        assert p._api_key == "test-key-123"


class TestLiteLLMProviderFactory:
    def test_get_litellm_provider(self) -> None:
        p = get_llm_provider("litellm", model="gpt-4o")
        assert isinstance(p, LiteLLMProvider)
        assert p.model_name == "gpt-4o"


class TestLiteLLMProviderComplete:
    @pytest.mark.asyncio
    async def test_complete_basic(self) -> None:
        p = LiteLLMProvider(model="gpt-4o")

        mock_msg = MagicMock()
        mock_msg.content = "Hello from LiteLLM"
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_response):
            result = await p.complete("Say hello")
        assert result == "Hello from LiteLLM"

    @pytest.mark.asyncio
    async def test_complete_with_system(self) -> None:
        p = LiteLLMProvider()

        mock_msg = MagicMock()
        mock_msg.content = "system reply"
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_response) as m:
            result = await p.complete("Hi", system="Be brief")
        assert result == "system reply"
        call_kwargs = m.call_args[1]
        assert call_kwargs["messages"][0] == {"role": "system", "content": "Be brief"}
        assert call_kwargs["messages"][1] == {"role": "user", "content": "Hi"}

    @pytest.mark.asyncio
    async def test_complete_without_system(self) -> None:
        p = LiteLLMProvider()

        mock_msg = MagicMock()
        mock_msg.content = "no sys"
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_response) as m:
            await p.complete("Hi")
        call_kwargs = m.call_args[1]
        assert len(call_kwargs["messages"]) == 1
        assert call_kwargs["messages"][0]["role"] == "user"

    @pytest.mark.asyncio
    async def test_complete_none_content_returns_empty(self) -> None:
        p = LiteLLMProvider()

        mock_msg = MagicMock()
        mock_msg.content = None
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_response):
            result = await p.complete("Hi")
        assert result == ""

    @pytest.mark.asyncio
    async def test_complete_with_fallbacks(self) -> None:
        p = LiteLLMProvider(model="gpt-4o", fallback_models=["gpt-4o-mini"])

        mock_msg = MagicMock()
        mock_msg.content = "fallback reply"
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_response) as m:
            await p.complete("Hi")
        call_kwargs = m.call_args[1]
        assert call_kwargs["fallbacks"] == [{"model": "gpt-4o-mini"}]

    @pytest.mark.asyncio
    async def test_complete_with_api_key(self) -> None:
        p = LiteLLMProvider(api_key="sk-test")

        mock_msg = MagicMock()
        mock_msg.content = "keyed"
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_response) as m:
            await p.complete("Hi")
        call_kwargs = m.call_args[1]
        assert call_kwargs["api_key"] == "sk-test"

    @pytest.mark.asyncio
    async def test_complete_timeout_propagated(self) -> None:
        p = LiteLLMProvider(timeout=120)

        mock_msg = MagicMock()
        mock_msg.content = "ok"
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_response) as m:
            await p.complete("Hi")
        assert m.call_args[1]["timeout"] == 120

    @pytest.mark.asyncio
    async def test_complete_raises_on_api_error(self) -> None:
        p = LiteLLMProvider()

        with patch("litellm.acompletion", new_callable=AsyncMock, side_effect=Exception("timeout")):
            with pytest.raises(Exception, match="timeout"):
                await p.complete("Hi")


class TestLiteLLMProviderCompleteStructured:
    @pytest.mark.asyncio
    async def test_structured_basic(self) -> None:
        p = LiteLLMProvider()

        mock_msg = MagicMock()
        mock_msg.content = json.dumps({"answer": "42", "score": 0.9})
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_response):
            result = await p.complete_structured("test", response_model=DummyResponse)
        assert isinstance(result, DummyResponse)
        assert result.answer == "42"
        assert result.score == pytest.approx(0.9)

    @pytest.mark.asyncio
    async def test_structured_strips_fences(self) -> None:
        p = LiteLLMProvider()

        mock_msg = MagicMock()
        mock_msg.content = '```json\n{"answer": "fenced", "score": 1.0}\n```'
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_response):
            result = await p.complete_structured("test", response_model=DummyResponse)
        assert isinstance(result, DummyResponse)
        assert result.answer == "fenced"

    @pytest.mark.asyncio
    async def test_structured_with_system(self) -> None:
        p = LiteLLMProvider()

        mock_msg = MagicMock()
        mock_msg.content = json.dumps({"answer": "sys", "score": 0.5})
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_response) as m:
            await p.complete_structured("test", system="Be nice", response_model=DummyResponse)
        sys_msg = m.call_args[1]["messages"][0]["content"]
        assert "Be nice" in sys_msg
        assert "json" in sys_msg.lower() or "schema" in sys_msg.lower()

    @pytest.mark.asyncio
    async def test_structured_json_mode_enabled(self) -> None:
        p = LiteLLMProvider()

        mock_msg = MagicMock()
        mock_msg.content = json.dumps({"answer": "json", "score": 0.0})
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_response) as m:
            await p.complete_structured("test", response_model=DummyResponse)
        assert m.call_args[1]["response_format"] == {"type": "json_object"}

    @pytest.mark.asyncio
    async def test_structured_with_api_key(self) -> None:
        p = LiteLLMProvider(api_key="sk-structured-key")

        mock_msg = MagicMock()
        mock_msg.content = json.dumps({"answer": "keyed", "score": 0.5})
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_response) as m:
            await p.complete_structured("test", response_model=DummyResponse)
        assert m.call_args[1]["api_key"] == "sk-structured-key"

    @pytest.mark.asyncio
    async def test_structured_with_fallbacks(self) -> None:
        p = LiteLLMProvider(model="gpt-4o", fallback_models=["gpt-4o-mini"])

        mock_msg = MagicMock()
        mock_msg.content = json.dumps({"answer": "fb", "score": 0.5})
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_response) as m:
            await p.complete_structured("test", response_model=DummyResponse)
        assert m.call_args[1]["fallbacks"] == [{"model": "gpt-4o-mini"}]

    @pytest.mark.asyncio
    async def test_structured_none_content_returns_defaults(self) -> None:
        p = LiteLLMProvider()

        mock_msg = MagicMock()
        mock_msg.content = None
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_response):
            # Empty JSON {} should fail validation since 'answer' is required
            with pytest.raises(Exception):
                await p.complete_structured("test", response_model=DummyResponse)
