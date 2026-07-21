import httpx
import pytest

from bussola.llm.client import HttpxLlmClient, LlmUnavailable


def test_chat_posts_to_openai_endpoint_and_parses_content():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        return httpx.Response(200, json={"choices": [{"message": {"content": "ciao"}}]})

    client = HttpxLlmClient(
        base_url="http://test", model="m", transport=httpx.MockTransport(handler)
    )
    assert client.chat([{"role": "user", "content": "hi"}]) == "ciao"


def test_timeout_raises_llm_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("boom", request=request)

    client = HttpxLlmClient(
        base_url="http://test", model="m", transport=httpx.MockTransport(handler)
    )
    with pytest.raises(LlmUnavailable):
        client.chat([{"role": "user", "content": "hi"}])
