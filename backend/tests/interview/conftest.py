from __future__ import annotations

import pytest


class FakeJsonLlmClient:
    """Deterministic LLM double for constrained extraction + text calls."""

    def __init__(
        self, json_responses: list[dict] | None = None, text_responses: list[str] | None = None
    ) -> None:
        self._json = list(json_responses or [])
        self._text = list(text_responses or [])
        self.calls: list[dict] = []

    def chat_json(self, messages, *, json_schema, temperature=0.0, max_tokens=None) -> dict:
        self.calls.append({"kind": "json", "messages": messages})
        if not self._json:
            raise AssertionError("FakeJsonLlmClient: no more json responses")
        return self._json.pop(0)

    def chat(self, messages, *, temperature=0.0, max_tokens=None) -> str:
        self.calls.append({"kind": "text", "messages": messages})
        if not self._text:
            raise AssertionError("FakeJsonLlmClient: no more text responses")
        return self._text.pop(0)


@pytest.fixture
def make_fake_json_llm():
    def _make(json_responses=None, text_responses=None) -> FakeJsonLlmClient:
        return FakeJsonLlmClient(json_responses, text_responses)

    return _make
