"""OpenAI-compatible provider."""

from __future__ import annotations

import json
import logging
import os

from openai import AsyncOpenAI
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class OpenAIProvider:
    """LLM provider backed by the OpenAI Chat Completions API."""

    def __init__(
        self,
        model: str = "gpt-4o",
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise ValueError("OPENAI_API_KEY not set and no api_key provided")
        self._model = model
        self._client = AsyncOpenAI(api_key=key, base_url=base_url)

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
        """Generate a plain-text completion."""
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        resp = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content or ""

    async def complete_structured(
        self,
        prompt: str,
        *,
        system: str = "",
        response_model: type[BaseModel],
        temperature: float = 0.7,
    ) -> BaseModel:
        """Generate a structured response via function calling."""
        schema = response_model.model_json_schema()
        func_name = response_model.__name__
        tools = [
            {
                "type": "function",
                "function": {
                    "name": func_name,
                    "description": f"Return a {func_name} object.",
                    "parameters": schema,
                },
            }
        ]
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        resp = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=temperature,
            tools=tools,
            tool_choice={"type": "function", "function": {"name": func_name}},
        )
        call = resp.choices[0].message.tool_calls[0]
        return response_model.model_validate(json.loads(call.function.arguments))
