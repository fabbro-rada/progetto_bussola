from __future__ import annotations

import pytest


class FakeLlmClient:
    """Deterministic LLM double: returns queued responses in order."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[list[dict[str, str]]] = []

    def chat(self, messages, *, temperature=0.0, max_tokens=None) -> str:
        self.calls.append(messages)
        if not self._responses:
            raise AssertionError("FakeLlmClient: no more scripted responses")
        return self._responses.pop(0)


@pytest.fixture
def make_fake_llm():
    def _make(responses: list[str]) -> FakeLlmClient:
        return FakeLlmClient(responses)

    return _make
