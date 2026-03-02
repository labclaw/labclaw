"""Local Ollama provider via HTTP API."""

from __future__ import annotations

import json
import logging

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class LocalProvider:
    """LLM provider backed by a local Ollama instance."""

    def __init__(
        self,
        model: str = "llama3.2",
        base_url: str = "http://localhost:11434",
    ) -> None:
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(base_url=self._base_url, timeout=120.0)

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
        """Generate a plain-text completion via Ollama /api/generate."""
        payload: dict = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        if system:
            payload["system"] = system
        resp = await self._client.post("/api/generate", json=payload)
        resp.raise_for_status()
        return resp.json()["response"]  # type: ignore[no-any-return]

    async def complete_structured(
        self,
        prompt: str,
        *,
        system: str = "",
        response_model: type[BaseModel],
        temperature: float = 0.7,
    ) -> BaseModel:
        """Generate a structured response by embedding the JSON schema in the prompt."""
        schema = json.dumps(response_model.model_json_schema(), indent=2)
        structured_prompt = (
            f"{prompt}\n\nRespond with ONLY valid JSON matching this schema:\n{schema}"
        )
        sys = system or "You are a helpful assistant that outputs valid JSON only."
        raw = await self.complete(structured_prompt, system=sys, temperature=temperature)
        # Strip markdown fences if present
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
        return response_model.model_validate(json.loads(text))
