"""LLM provider abstraction layer."""

from __future__ import annotations

from labclaw.llm.provider import LLMConfig, LLMProvider
from labclaw.llm.providers.anthropic import AnthropicProvider
from labclaw.llm.providers.litellm_provider import LiteLLMProvider
from labclaw.llm.providers.local import LocalProvider
from labclaw.llm.providers.openai import OpenAIProvider

__all__ = [
    "AnthropicProvider",
    "LLMConfig",
    "LLMProvider",
    "LiteLLMProvider",
    "LocalProvider",
    "OpenAIProvider",
    "get_llm_provider",
]

_PROVIDERS: dict[str, type] = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
    "local": LocalProvider,
    "litellm": LiteLLMProvider,
}


def get_llm_provider(provider_name: str, **kwargs: object) -> LLMProvider:
    """Instantiate an LLM provider by name.

    Args:
        provider_name: One of 'anthropic', 'openai', 'local'.
        **kwargs: Forwarded to the provider constructor (model, api_key, etc.).

    Returns:
        An object satisfying the LLMProvider protocol.
    """
    cls = _PROVIDERS.get(provider_name)
    if cls is None:
        raise ValueError(
            f"Unknown LLM provider {provider_name!r}. Available: {', '.join(_PROVIDERS)}"
        )
    return cls(**kwargs)
