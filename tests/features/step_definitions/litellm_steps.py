"""BDD step definitions for LiteLLM multi-model routing (L2 Infra)."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel
from pytest_bdd import given, parsers, then, when

from labclaw.llm import get_llm_provider
from labclaw.llm.providers.litellm_provider import LiteLLMProvider


def _run_async(coro: Any) -> Any:
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class _DummyResponse(BaseModel):
    answer: str
    score: float = 0.0


def _make_mock_response(content: str) -> MagicMock:
    mock_msg = MagicMock()
    mock_msg.content = content
    mock_choice = MagicMock()
    mock_choice.message = mock_msg
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    return mock_response


# ---------------------------------------------------------------------------
# When — creation
# ---------------------------------------------------------------------------


@when("I create a LiteLLM provider", target_fixture="litellm_provider")
def create_litellm_default() -> LiteLLMProvider:
    return LiteLLMProvider()


@when(
    parsers.parse('I create a LiteLLM provider with model "{model}"'),
    target_fixture="litellm_provider",
)
def create_litellm_with_model(model: str) -> LiteLLMProvider:
    return LiteLLMProvider(model=model)


@when(
    parsers.parse('I request a "{name}" provider from the factory'),
    target_fixture="factory_provider",
)
def request_factory_provider(name: str) -> Any:
    return get_llm_provider(name, model="gpt-4o")


# ---------------------------------------------------------------------------
# Given — mocked LiteLLM
# ---------------------------------------------------------------------------


@given(
    parsers.parse('a mocked LiteLLM returning "{response}"'),
    target_fixture="litellm_ctx",
)
def mocked_litellm_returning(response: str) -> dict[str, Any]:
    return {"provider": LiteLLMProvider(), "response": _make_mock_response(response)}


@given(
    parsers.parse('a mocked LiteLLM with fallback models "{models}"'),
    target_fixture="litellm_ctx",
)
def mocked_litellm_with_fallbacks(models: str) -> dict[str, Any]:
    model_list = [m.strip() for m in models.split(",")]
    return {
        "provider": LiteLLMProvider(fallback_models=model_list),
        "response": _make_mock_response("ok"),
        "mock_ref": None,
    }


@given(
    parsers.parse("a mocked LiteLLM with timeout {timeout:d}"),
    target_fixture="litellm_ctx",
)
def mocked_litellm_with_timeout(timeout: int) -> dict[str, Any]:
    return {
        "provider": LiteLLMProvider(timeout=timeout),
        "response": _make_mock_response("ok"),
    }


@given(
    parsers.parse("a mocked LiteLLM returning structured JSON '{json_str}'"),
    target_fixture="litellm_ctx",
)
def mocked_litellm_structured(json_str: str) -> dict[str, Any]:
    return {"provider": LiteLLMProvider(), "response": _make_mock_response(json_str)}


@given("a mocked LiteLLM that raises an error", target_fixture="litellm_ctx")
def mocked_litellm_error() -> dict[str, Any]:
    return {"provider": LiteLLMProvider(), "error": Exception("API timeout")}


# ---------------------------------------------------------------------------
# When — completion
# ---------------------------------------------------------------------------


@when(
    parsers.parse('I call litellm complete with prompt "{prompt}"'),
    target_fixture="litellm_result",
)
def call_litellm_complete(litellm_ctx: dict[str, Any], prompt: str) -> dict[str, Any]:
    p = litellm_ctx["provider"]
    resp = litellm_ctx["response"]
    with patch("litellm.acompletion", new_callable=AsyncMock, return_value=resp) as m:
        result = _run_async(p.complete(prompt))
    return {"result": result, "mock": m}


@when(
    parsers.parse('I call litellm complete with prompt "{prompt}" and system "{system}"'),
    target_fixture="litellm_result",
)
def call_litellm_complete_with_system(
    litellm_ctx: dict[str, Any], prompt: str, system: str
) -> dict[str, Any]:
    p = litellm_ctx["provider"]
    resp = litellm_ctx["response"]
    with patch("litellm.acompletion", new_callable=AsyncMock, return_value=resp) as m:
        result = _run_async(p.complete(prompt, system=system))
    return {"result": result, "mock": m}


@when("I call litellm complete_structured", target_fixture="litellm_result")
def call_litellm_structured(litellm_ctx: dict[str, Any]) -> dict[str, Any]:
    p = litellm_ctx["provider"]
    resp = litellm_ctx["response"]
    with patch("litellm.acompletion", new_callable=AsyncMock, return_value=resp):
        result = _run_async(p.complete_structured("test", response_model=_DummyResponse))
    return {"result": result}


@when("I call litellm complete expecting an error", target_fixture="litellm_result")
def call_litellm_complete_error(litellm_ctx: dict[str, Any]) -> dict[str, Any]:
    p = litellm_ctx["provider"]
    err = litellm_ctx["error"]
    with patch("litellm.acompletion", new_callable=AsyncMock, side_effect=err):
        try:
            _run_async(p.complete("Hi"))
            return {"error": None}
        except Exception as exc:
            return {"error": exc}


# ---------------------------------------------------------------------------
# Then — assertions
# ---------------------------------------------------------------------------


@then(parsers.parse('the litellm provider model name is "{model}"'))
def check_litellm_model(litellm_provider: LiteLLMProvider, model: str) -> None:
    assert litellm_provider.model_name == model


@then("the returned provider is a LiteLLMProvider")
def check_factory_returns_litellm(factory_provider: Any) -> None:
    assert isinstance(factory_provider, LiteLLMProvider)


@then(parsers.parse('the litellm result is "{expected}"'))
def check_litellm_result(litellm_result: dict[str, Any], expected: str) -> None:
    assert litellm_result["result"] == expected


@then("the litellm call includes fallback models")
def check_fallbacks_present(litellm_result: dict[str, Any]) -> None:
    call_kwargs = litellm_result["mock"].call_args[1]
    assert "fallbacks" in call_kwargs
    assert len(call_kwargs["fallbacks"]) > 0


@then(parsers.parse('the structured result answer is "{answer}"'))
def check_structured_answer(litellm_result: dict[str, Any], answer: str) -> None:
    assert litellm_result["result"].answer == answer


@then(parsers.parse("the structured result score is {score:f}"))
def check_structured_score(litellm_result: dict[str, Any], score: float) -> None:
    assert litellm_result["result"].score == pytest.approx(score)


@then(parsers.parse("the litellm call has timeout {timeout:d}"))
def check_timeout(litellm_result: dict[str, Any], timeout: int) -> None:
    call_kwargs = litellm_result["mock"].call_args[1]
    assert call_kwargs["timeout"] == timeout


@then("a litellm error is raised")
def check_litellm_error(litellm_result: dict[str, Any]) -> None:
    assert litellm_result["error"] is not None
    assert isinstance(litellm_result["error"], Exception)
