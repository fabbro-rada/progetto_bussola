import httpx
import pytest

from bussola.llm.client import HttpxLlmClient, LlmUnavailable


def test_chat_json_sends_schema_and_parses_object():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200, json={"choices": [{"message": {"content": '{"ok": true, "n": 2}'}}]}
        )

    client = HttpxLlmClient(
        base_url="http://test", model="m", transport=httpx.MockTransport(handler)
    )
    schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}}
    out = client.chat_json([{"role": "user", "content": "hi"}], json_schema=schema)
    assert out == {"ok": True, "n": 2}
    assert captured["body"]["response_format"]["type"] == "json_schema"
    assert captured["body"]["response_format"]["json_schema"]["schema"] == schema


def test_chat_json_timeout_raises_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("boom", request=request)

    client = HttpxLlmClient(
        base_url="http://test", model="m", transport=httpx.MockTransport(handler)
    )
    with pytest.raises(LlmUnavailable):
        client.chat_json([{"role": "user", "content": "hi"}], json_schema={"type": "object"})
