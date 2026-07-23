"""Thin client for a local OpenAI-compatible LLM server (llama-server).

Talks only to the local server; no external API. Timeouts/transport errors
surface as `LlmUnavailable` so callers can degrade gracefully (text-first).
"""

from __future__ import annotations

import json
from typing import Any, Protocol

import httpx

from bussola.llm import config


class LlmUnavailable(RuntimeError):
    """The local LLM server could not be reached in time."""


class LlmClient(Protocol):
    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> str: ...

    def chat_json(
        self,
        messages: list[dict[str, str]],
        *,
        json_schema: dict[str, Any],
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> dict[str, Any]: ...


class HttpxLlmClient:
    def __init__(
        self,
        base_url: str = config.BASE_URL,
        model: str = config.MODEL,
        timeout: float = config.TIMEOUT,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._model = model
        self._client = httpx.Client(base_url=base_url, timeout=timeout, transport=transport)

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> str:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        try:
            response = self._client.post("/v1/chat/completions", json=payload)
            response.raise_for_status()
        except httpx.TransportError as exc:
            raise LlmUnavailable(str(exc)) from exc
        data = response.json()
        content: str = data["choices"][0]["message"]["content"]
        return content

    def chat_json(
        self,
        messages: list[dict[str, str]],
        *,
        json_schema: dict[str, Any],
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        """Chat with a JSON-schema-constrained response; returns the parsed object."""
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "extraction", "schema": json_schema, "strict": True},
            },
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        try:
            response = self._client.post("/v1/chat/completions", json=payload)
            response.raise_for_status()
        except httpx.TransportError as exc:
            raise LlmUnavailable(str(exc)) from exc
        data = response.json()
        content: str = data["choices"][0]["message"]["content"]
        parsed: dict[str, Any] = json.loads(content)
        return parsed
