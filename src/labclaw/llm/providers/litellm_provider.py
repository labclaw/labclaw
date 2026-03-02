"""LiteLLM multi-model routing provider."""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class LiteLLMProvider:
    """LLM provider backed by LiteLLM for multi-model routing.

    Supports 100+ models through a single interface with automatic
    fallback chains, cost tracking, and rate limiting.
    """

    def __init__(
        self,
        model: str = "gpt-4o",
        *,
        fallback_models: list[str] | None = None,
        timeout: int = 30,
        num_retries: int = 2,
        api_key: str | None = None,
        **kwargs: Any,
    ) -> None:
        self._model = model
        self._fallback_models = fallback_models or []
        self._timeout = timeout
        self._num_retries = num_retries
        self._api_key = api_key
        self._extra_kwargs = kwargs

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
        """Generate a plain-text completion via LiteLLM."""
        import litellm

        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "timeout": self._timeout,
            "num_retries": self._num_retries,
        }
        if self._api_key:
            kwargs["api_key"] = self._api_key
        if self._fallback_models:
            kwargs["fallbacks"] = [{"model": m} for m in self._fallback_models]

        response = await litellm.acompletion(**kwargs)
        return response.choices[0].message.content or ""

    async def complete_structured(
        self,
        prompt: str,
        *,
        system: str = "",
        response_model: type[BaseModel],
        temperature: float = 0.7,
    ) -> BaseModel:
        """Generate a structured response via LiteLLM with JSON mode."""
        import litellm

        schema = response_model.model_json_schema()
        schema_instruction = (
            f"Respond with valid JSON matching this schema:\n{json.dumps(schema, indent=2)}"
        )
        full_system = f"{system}\n\n{schema_instruction}" if system else schema_instruction

        messages: list[dict[str, str]] = [
            {"role": "system", "content": full_system},
            {"role": "user", "content": prompt},
        ]

        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "timeout": self._timeout,
            "num_retries": self._num_retries,
            "response_format": {"type": "json_object"},
        }
        if self._api_key:
            kwargs["api_key"] = self._api_key

        response = await litellm.acompletion(**kwargs)
        text = response.choices[0].message.content or "{}"
        # Strip markdown fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if len(lines) > 2 else text
        return response_model.model_validate(json.loads(text))
