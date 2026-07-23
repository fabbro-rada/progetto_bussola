from __future__ import annotations

import pytest


class FakeJsonLlmClient:
    def __init__(self, json_responses: list[dict] | None = None) -> None:
        self._json = list(json_responses or [])
        self.calls: list[dict] = []

    def chat_json(self, messages, *, json_schema, temperature=0.0, max_tokens=None) -> dict:
        self.calls.append({"messages": messages})
        if not self._json:
            raise AssertionError("FakeJsonLlmClient: no more json responses")
        return self._json.pop(0)


@pytest.fixture
def make_fake_json_llm():
    def _make(json_responses=None) -> FakeJsonLlmClient:
        return FakeJsonLlmClient(json_responses)

    return _make
