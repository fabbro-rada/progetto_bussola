import pytest
from fastapi.testclient import TestClient

from bussola.api.app import create_app
from bussola.api.kiosk import config
from bussola.api.kiosk.routers import interview as interview_router
from bussola.guardrails.scope import ScopeGuard
from bussola.interview.interview import Interview
from bussola.profile.models import WorkProfile

TOKEN = "secret-kiosk"
ALLOW = '{"allow": true, "category": null, "reason": "ok"}'
COMP = {
    "skills": [{"name": "cooking", "kind": "technical", "evidence": "stated"}],
    "languages": [],
    "digital_literacy": None,
}


class FakeRepo:
    def create_new(self) -> str:
        return "P-kiosk-1"

    def save(self, profile: WorkProfile) -> WorkProfile:
        return profile


class FakeJsonLlm:
    def __init__(self, json_responses=None, text_responses=None):
        self._json = list(json_responses or [])
        self._text = list(text_responses or [])

    def chat(self, messages, *, temperature=0.0, max_tokens=None):
        return self._text.pop(0)

    def chat_json(self, messages, *, json_schema, temperature=0.0, max_tokens=None):
        return self._json.pop(0)


class NoopRedactor:
    def redact(self, text: str, language: str = "it") -> str:
        return text


@pytest.fixture
def client(monkeypatch) -> TestClient:
    monkeypatch.setattr(config, "KIOSK_TOKEN", TOKEN)

    def fake_build(language: str):
        llm = FakeJsonLlm(json_responses=[COMP], text_responses=[ALLOW, "Sai cucinare. Giusto?"])
        itw = Interview(
            llm, ScopeGuard(llm), FakeRepo(), language=language, redactor=NoopRedactor()
        )
        return itw, lambda: None

    monkeypatch.setattr(interview_router, "build_interview", fake_build)
    return TestClient(create_app())


def _h() -> dict:
    return {"X-Kiosk-Token": TOKEN}


def test_start_without_token_is_401():
    # KIOSK_TOKEN defaults to "" here (no fixture) -> require_kiosk denies (fail closed).
    r = TestClient(create_app()).post("/kiosk/interview/start", json={"language": "it"})
    assert r.status_code == 401


def test_start_then_submit_flow(client):
    start = client.post("/kiosk/interview/start", json={"language": "it"}, headers=_h())
    assert start.status_code == 200
    body = start.json()
    assert body["step"]["kind"] == "question"
    token = body["session_token"]

    submit = client.post(
        "/kiosk/interview/submit",
        json={"session_token": token, "answer": "so cucinare"},
        headers=_h(),
    )
    assert submit.status_code == 200
    assert submit.json()["step"]["kind"] == "summary"


def test_submit_unknown_session_is_404(client):
    r = client.post(
        "/kiosk/interview/submit",
        json={"session_token": "nope", "answer": "x"},
        headers=_h(),
    )
    assert r.status_code == 404


def test_start_failure_closes_connection(monkeypatch):
    monkeypatch.setattr(config, "KIOSK_TOKEN", TOKEN)
    evicted = []

    class BoomInterview:
        def start(self):
            raise RuntimeError("db down at start")

    def fake_build(language: str):
        return BoomInterview(), lambda: evicted.append(True)

    monkeypatch.setattr(interview_router, "build_interview", fake_build)
    client = TestClient(
        create_app(), raise_server_exceptions=False
    )  # let the 500 surface as a response
    r = client.post("/kiosk/interview/start", json={"language": "it"}, headers=_h())
    assert r.status_code == 500
    assert evicted == [True]  # on_evict ran -> connection closed, no leak
