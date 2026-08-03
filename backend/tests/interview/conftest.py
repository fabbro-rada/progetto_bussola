from __future__ import annotations

import pytest


_OUTPUT_MARKER = "[assistant reply]"  # only ScopeGuard.check_output uses this prefix
_DEFAULT_OUTPUT_ALLOW = '{"allow": true, "category": null, "reason": "ok"}'


class FakeJsonLlmClient:
    """Deterministic LLM double for constrained extraction + text calls.

    The outbound scope guard (`ScopeGuard.check_output`) is recognised by the
    ``[assistant reply]`` prefix its user message carries and handled on a
    SEPARATE channel: it defaults to ALLOW, is recorded in ``output_calls``
    rather than ``calls``, and never consumes the ``text_responses`` queue. That
    way the many interview tests written before the outbound guard need no extra
    scripting and keep their positional ``calls`` indices. A test that exercises
    a rejected/allowed output queues explicit decisions via ``output_responses``.
    """

    def __init__(
        self,
        json_responses: list[dict] | None = None,
        text_responses: list[str] | None = None,
        output_responses: list[str] | None = None,
    ) -> None:
        self._json = list(json_responses or [])
        self._text = list(text_responses or [])
        self._output = list(output_responses or [])
        self.calls: list[dict] = []
        self.output_calls: list[dict] = []

    def chat_json(self, messages, *, json_schema, temperature=0.0, max_tokens=None) -> dict:
        self.calls.append({"kind": "json", "messages": messages})
        if not self._json:
            raise AssertionError("FakeJsonLlmClient: no more json responses")
        return self._json.pop(0)

    def chat(self, messages, *, temperature=0.0, max_tokens=None) -> str:
        user = messages[-1]["content"] if messages else ""
        if user.startswith(_OUTPUT_MARKER):
            self.output_calls.append({"kind": "text", "messages": messages})
            return self._output.pop(0) if self._output else _DEFAULT_OUTPUT_ALLOW
        self.calls.append({"kind": "text", "messages": messages})
        if not self._text:
            raise AssertionError("FakeJsonLlmClient: no more text responses")
        return self._text.pop(0)


@pytest.fixture
def make_fake_json_llm():
    def _make(json_responses=None, text_responses=None, output_responses=None) -> FakeJsonLlmClient:
        return FakeJsonLlmClient(json_responses, text_responses, output_responses)

    return _make
