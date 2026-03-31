"""OpenAI-compatible provider for Fireworks AI and other OpenAI-format APIs."""

from __future__ import annotations

import os
from typing import Any

from openai import AsyncOpenAI
from pydantic import BaseModel

from labclaw.llm.provider import LLMProvider


class OpenAIProvider(LLMProvider):
    """OpenAI-compatible provider supporting Fireworks AI, OpenAI, and others."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str = "gpt-4o",
    ) -> None:
        """Initialize with API key, optional base_url (for Fireworks), and model."""
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self._base_url = base_url
        self._model = model
        self._client: AsyncOpenAI | None = None

    async def _get_client(self) -> AsyncOpenAI:
        """Lazy initialize the OpenAI client."""
        if self._client is None:
            kwargs: dict[str, Any] = {"api_key": self._api_key}
            if self._base_url:
                kwargs["base_url"] = self._base_url
            self._client = AsyncOpenAI(**kwargs)
        return self._client

    async def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """Complete a prompt using OpenAI-compatible API."""
        client = await self._get_client()
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = await client.chat.completions.create(
            model=self._model,
            messages=messages,  # type: ignore[arg-type]
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""

    async def complete_structured(
        self,
        prompt: str,
        *,
        system: str = "",
        response_model: type[BaseModel],
        temperature: float = 0.7,
    ) -> BaseModel:
        """Complete with structured JSON output."""
        client = await self._get_client()
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = await client.beta.chat.completions.parse(
            model=self._model,
            messages=messages,  # type: ignore[arg-type]
            temperature=temperature,
            response_format=response_model,
        )
        return response.choices[0].message.parsed  # type: ignore[return-value]

    @property
    def model_name(self) -> str:
        """Return the model name."""
        return self._model


class FireworksProvider(OpenAIProvider):
    """Fireworks AI provider using OpenAI-compatible API."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "accounts/fireworks/models/kimi-k2p5",
    ) -> None:
        """Initialize Fireworks AI with OpenAI-compatible API."""
        super().__init__(
            api_key=api_key or os.environ.get("FIREWORKS_API_KEY", ""),
            base_url="https://api.fireworks.ai/inference/v1",
            model=model,
        )
