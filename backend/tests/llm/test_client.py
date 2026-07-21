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


def test_http_error_status_propagates_and_is_not_llm_unavailable():
    """An HTTP error response (e.g. 500) is a server error, not an
    unreachable-server condition: it must propagate as `HTTPStatusError`,
    not be swallowed into `LlmUnavailable`."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    client = HttpxLlmClient(
        base_url="http://test", model="m", transport=httpx.MockTransport(handler)
    )
    with pytest.raises(httpx.HTTPStatusError):
        client.chat([{"role": "user", "content": "hi"}])
