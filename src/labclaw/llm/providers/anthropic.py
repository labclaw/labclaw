"""Anthropic Claude provider."""

from __future__ import annotations

import json
import logging
import os

from anthropic import AsyncAnthropic
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class AnthropicProvider:
    """LLM provider backed by the Anthropic Messages API."""

    def __init__(
        self,
        model: str = "claude-sonnet-4-6",
        api_key: str | None = None,
    ) -> None:
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise ValueError("ANTHROPIC_API_KEY not set and no api_key provided")
        self._model = model
        self._client = AsyncAnthropic(api_key=key)

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
        msg = await self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system or "You are a helpful assistant.",
            messages=[{"role": "user", "content": prompt}],
        )
        block = msg.content[0]
        if not hasattr(block, "text"):
            raise ValueError(f"Unexpected content block type: {type(block).__name__}")
        return block.text  # type: ignore[union-attr]

    async def complete_structured(
        self,
        prompt: str,
        *,
        system: str = "",
        response_model: type[BaseModel],
        temperature: float = 0.7,
    ) -> BaseModel:
        """Generate a structured response via tool_use."""
        schema = response_model.model_json_schema()
        tool_name = response_model.__name__
        tools = [
            {
                "name": tool_name,
                "description": f"Return a {tool_name} object.",
                "input_schema": schema,
            }
        ]
        msg = await self._client.messages.create(  # type: ignore[call-overload]
            model=self._model,
            max_tokens=2048,
            temperature=temperature,
            system=system or "You are a helpful assistant.",
            messages=[{"role": "user", "content": prompt}],
            tools=tools,
            tool_choice={"type": "tool", "name": tool_name},
        )
        for block in msg.content:
            if block.type == "tool_use" and block.name == tool_name:
                return response_model.model_validate(block.input)
        # Fallback: try parsing the text content as JSON
        text = msg.content[0].text if msg.content else ""
        return response_model.model_validate(json.loads(text))
