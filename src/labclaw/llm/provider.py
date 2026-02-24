"""LLM provider protocol and configuration."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel


class LLMConfig(BaseModel):
    """Configuration for an LLM provider."""

    provider: str = "anthropic"
    model: str = "claude-sonnet-4-6"
    api_key_env: str = "ANTHROPIC_API_KEY"
    temperature: float = 0.7
    max_tokens: int = 4096
    fallback_provider: str | None = None


@runtime_checkable
class LLMProvider(Protocol):
    """Abstract protocol for LLM backends."""

    async def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str: ...

    async def complete_structured(
        self,
        prompt: str,
        *,
        system: str = "",
        response_model: type[BaseModel],
        temperature: float = 0.7,
    ) -> BaseModel: ...

    @property
    def model_name(self) -> str: ...
