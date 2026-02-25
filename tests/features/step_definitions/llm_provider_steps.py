"""BDD step definitions for LLM providers (L5 Persona).

Tests AnthropicProvider, OpenAIProvider, LocalProvider, and LLMConfig.
Uses mock patterns — no real API calls are made.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

import pytest
from pytest_bdd import given, parsers, then, when

from labclaw.llm.provider import LLMConfig, LLMProvider

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_async(coro: Any) -> Any:
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class _MockProvider:
    """Mock LLM provider for protocol-compliance tests."""

    def __init__(self, response: str = "") -> None:
        self._response = response
        self._model = "mock-model"

    @property
    def model_name(self) -> str:
        return self._model

    async def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        return self._response

    async def complete_structured(
        self,
        prompt: str,
        *,
        system: str = "",
        response_model: type,
        temperature: float = 0.7,
    ) -> Any:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Given steps
# ---------------------------------------------------------------------------


@given(
    parsers.parse('a mock LLM provider returning "{response}"'),
    target_fixture="mock_provider",
)
def mock_llm_provider(response: str) -> _MockProvider:
    return _MockProvider(response=response)


@given("a mock LLM provider with empty response", target_fixture="mock_provider")
def mock_llm_provider_empty() -> _MockProvider:
    return _MockProvider(response="")


# ---------------------------------------------------------------------------
# When steps — Anthropic provider
# ---------------------------------------------------------------------------


@when(
    parsers.parse('I create an Anthropic provider with api_key "{api_key}"'),
    target_fixture="anthropic_provider",
)
def create_anthropic_provider_with_key(api_key: str) -> Any:
    from labclaw.llm.providers.anthropic import AnthropicProvider

    return AnthropicProvider(api_key=api_key)


@when(
    parsers.parse('I create an Anthropic provider with model "{model}" and api_key "{api_key}"'),
    target_fixture="anthropic_provider",
)
def create_anthropic_provider_with_model(model: str, api_key: str) -> Any:
    from labclaw.llm.providers.anthropic import AnthropicProvider

    return AnthropicProvider(model=model, api_key=api_key)


@when(
    "I try to create an Anthropic provider without an API key",
    target_fixture="provider_error",
)
def try_create_anthropic_no_key() -> Exception | None:
    from labclaw.llm.providers.anthropic import AnthropicProvider

    # Remove env var if set so the provider cannot fall back to it
    saved = os.environ.pop("ANTHROPIC_API_KEY", None)
    try:
        AnthropicProvider()
        return None
    except ValueError as exc:
        return exc
    finally:
        if saved is not None:
            os.environ["ANTHROPIC_API_KEY"] = saved


# ---------------------------------------------------------------------------
# When steps — OpenAI provider
# ---------------------------------------------------------------------------


@when(
    parsers.parse('I create an OpenAI provider with api_key "{api_key}"'),
    target_fixture="openai_provider",
)
def create_openai_provider_with_key(api_key: str) -> Any:
    from labclaw.llm.providers.openai import OpenAIProvider

    return OpenAIProvider(api_key=api_key)


@when(
    parsers.parse('I create an OpenAI provider with model "{model}" and api_key "{api_key}"'),
    target_fixture="openai_provider",
)
def create_openai_provider_with_model(model: str, api_key: str) -> Any:
    from labclaw.llm.providers.openai import OpenAIProvider

    return OpenAIProvider(model=model, api_key=api_key)


@when(
    "I try to create an OpenAI provider without an API key",
    target_fixture="provider_error",
)
def try_create_openai_no_key() -> Exception | None:
    from labclaw.llm.providers.openai import OpenAIProvider

    saved = os.environ.pop("OPENAI_API_KEY", None)
    try:
        OpenAIProvider()
        return None
    except ValueError as exc:
        return exc
    finally:
        if saved is not None:
            os.environ["OPENAI_API_KEY"] = saved


# ---------------------------------------------------------------------------
# When steps — Local provider
# ---------------------------------------------------------------------------


@when(
    "I create a local provider",
    target_fixture="local_provider",
)
def create_local_provider_default() -> Any:
    from labclaw.llm.providers.local import LocalProvider

    return LocalProvider()


@when(
    parsers.parse('I create a local provider with model "{model}" and url "{url}"'),
    target_fixture="local_provider",
)
def create_local_provider_custom(model: str, url: str) -> Any:
    from labclaw.llm.providers.local import LocalProvider

    return LocalProvider(model=model, base_url=url)


# ---------------------------------------------------------------------------
# When steps — completion
# ---------------------------------------------------------------------------


@when(
    parsers.parse('I call complete with prompt "{prompt}"'),
    target_fixture="completion_result",
)
def call_complete(mock_provider: _MockProvider, prompt: str) -> str:
    return _run_async(mock_provider.complete(prompt))


@when(
    parsers.parse('I call complete with prompt "{prompt}" and system "{system}"'),
    target_fixture="completion_result",
)
def call_complete_with_system(mock_provider: _MockProvider, prompt: str, system: str) -> str:
    return _run_async(mock_provider.complete(prompt, system=system))


@when("I call complete with an empty prompt", target_fixture="completion_result")
def call_complete_empty_prompt(mock_provider: _MockProvider) -> str:
    return _run_async(mock_provider.complete(""))


# ---------------------------------------------------------------------------
# When steps — LLMConfig
# ---------------------------------------------------------------------------


@when(
    "I create a default LLMConfig",
    target_fixture="llm_config",
)
def create_default_llm_config() -> LLMConfig:
    return LLMConfig()


@when(
    parsers.parse('I create an LLMConfig with provider "{provider}" and model "{model}"'),
    target_fixture="llm_config",
)
def create_custom_llm_config(provider: str, model: str) -> LLMConfig:
    return LLMConfig(provider=provider, model=model)


# ---------------------------------------------------------------------------
# Then steps — Anthropic provider
# ---------------------------------------------------------------------------


@then(parsers.parse('the provider model name is "{model_name}"'))
def check_anthropic_model_name(anthropic_provider: Any, model_name: str) -> None:
    assert anthropic_provider.model_name == model_name, (
        f"Expected model {model_name!r}, got {anthropic_provider.model_name!r}"
    )


@then("a ValueError is raised for missing API key")
def check_value_error_for_api_key(provider_error: Exception | None) -> None:
    assert isinstance(provider_error, ValueError), (
        f"Expected ValueError, got {type(provider_error)}"
    )


# ---------------------------------------------------------------------------
# Then steps — OpenAI provider
# ---------------------------------------------------------------------------


@then(parsers.parse('the openai provider model name is "{model_name}"'))
def check_openai_model_name(openai_provider: Any, model_name: str) -> None:
    assert openai_provider.model_name == model_name, (
        f"Expected model {model_name!r}, got {openai_provider.model_name!r}"
    )


# ---------------------------------------------------------------------------
# Then steps — Local provider
# ---------------------------------------------------------------------------


@then(parsers.parse('the local provider model name is "{model_name}"'))
def check_local_model_name(local_provider: Any, model_name: str) -> None:
    assert local_provider.model_name == model_name, (
        f"Expected model {model_name!r}, got {local_provider.model_name!r}"
    )


@then(parsers.parse('the local provider base_url is "{base_url}"'))
def check_local_base_url(local_provider: Any, base_url: str) -> None:
    assert local_provider._base_url == base_url.rstrip("/"), (
        f"Expected base_url {base_url!r}, got {local_provider._base_url!r}"
    )


# ---------------------------------------------------------------------------
# Then steps — completion
# ---------------------------------------------------------------------------


@then(parsers.parse('the completion result is "{expected}"'))
def check_completion_result(completion_result: str, expected: str) -> None:
    assert completion_result == expected, (
        f"Expected completion {expected!r}, got {completion_result!r}"
    )


@then("the empty completion result is empty")
def check_empty_completion_result(completion_result: str) -> None:
    assert completion_result == "", f"Expected empty string, got {completion_result!r}"


# ---------------------------------------------------------------------------
# Then steps — LLMConfig
# ---------------------------------------------------------------------------


@then(parsers.parse('the config provider is "{provider}"'))
def check_config_provider(llm_config: LLMConfig, provider: str) -> None:
    assert llm_config.provider == provider, (
        f"Expected provider {provider!r}, got {llm_config.provider!r}"
    )


@then(parsers.parse('the config model is "{model}"'))
def check_config_model(llm_config: LLMConfig, model: str) -> None:
    assert llm_config.model == model, (
        f"Expected model {model!r}, got {llm_config.model!r}"
    )


@then(parsers.parse("the config temperature is {temp:f}"))
def check_config_temperature(llm_config: LLMConfig, temp: float) -> None:
    assert llm_config.temperature == pytest.approx(temp), (
        f"Expected temperature {temp}, got {llm_config.temperature}"
    )


# ---------------------------------------------------------------------------
# Then steps — protocol
# ---------------------------------------------------------------------------


@then("the provider satisfies the LLMProvider protocol")
def check_provider_protocol(mock_provider: _MockProvider) -> None:
    assert isinstance(mock_provider, LLMProvider), (
        f"Expected {type(mock_provider)} to satisfy LLMProvider protocol"
    )
