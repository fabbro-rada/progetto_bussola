"""Kiosk interview endpoints. `/start` now consumes a one-time `start_code`
(Task 5): runs against the real test DB (unlike a fully-faked Interview)
because `StartCodeService.consume` needs a real, atomic UPDATE ... RETURNING
to prove single-use durability, exactly like `test_followup_start.py` for
`/start-followup`. `open_kiosk_conn` is monkeypatched to point at
`bussola_test`, the same pattern `test_followup_start.py` and
`test_kiosk_live.py` use.

`/submit` tests don't need the `/start` contract at all: they inject a
fully-faked `Interview` directly into the `REGISTRY`, so they stay decoupled
from how a session was created."""

from __future__ import annotations

import psycopg
import pytest
from fastapi.testclient import TestClient

from bussola.api.app import create_app
from bussola.api.kiosk import config
from bussola.api.kiosk.deps import REGISTRY
from bussola.api.kiosk.routers import interview as interview_router
from bussola.data import config as db_config
from bussola.data.profiles import create_empty_profile
from bussola.guardrails.scope import ScopeGuard
from bussola.interview.interview import Interview, Step
from bussola.startcode.service import StartCodeService

pytestmark = pytest.mark.usefixtures("db")

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

    def save(self, profile) -> object:
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


def _open_test_conn() -> psycopg.Connection:
    return psycopg.connect(db_config.dsn("app", dbname="bussola_test"))


@pytest.fixture
def kiosk_client(monkeypatch) -> TestClient:
    monkeypatch.setattr(config, "KIOSK_TOKEN", TOKEN)
    monkeypatch.setattr(interview_router, "open_kiosk_conn", _open_test_conn)
    return TestClient(create_app())


def _h() -> dict:
    return {"X-Kiosk-Token": TOKEN}


@pytest.fixture
def issued_start_code(app_conn: psycopg.Connection) -> str:
    # A start_code only ever exists for a pseudonym provisioned ahead of time
    # (Task 3/6): an empty profile is created first, then a code is minted
    # for it (mirrors `issued_token_for_p` in test_followup_start.py).
    pseudonym = create_empty_profile(app_conn)
    app_conn.commit()
    code = StartCodeService(app_conn).issue(pseudonym)
    app_conn.commit()
    return code


def _register_fake_session() -> str:
    """Inject a fully-faked Interview session directly into the REGISTRY,
    bypassing `/start` entirely -- `/submit` tests only care about the
    submit state machine, not about how the session got created."""
    llm = FakeJsonLlm(json_responses=[COMP], text_responses=[ALLOW, "Sai cucinare. Giusto?"])
    itw = Interview(llm, ScopeGuard(llm), FakeRepo(), language="it", redactor=NoopRedactor())
    itw.start()
    return REGISTRY.create(itw, on_evict=lambda: None)


def test_start_without_token_is_401():
    # KIOSK_TOKEN defaults to "" here (no fixture) -> require_kiosk denies (fail closed).
    r = TestClient(create_app()).post(
        "/kiosk/interview/start", json={"start_code": "whatever", "language": "it"}
    )
    assert r.status_code == 401


def test_start_with_valid_start_code_returns_question(
    kiosk_client: TestClient, issued_start_code: str
):
    start = kiosk_client.post(
        "/kiosk/interview/start",
        json={"start_code": issued_start_code, "language": "it"},
        headers=_h(),
    )
    assert start.status_code == 200
    body = start.json()
    assert body["step"]["kind"] == "question"
    assert body["session_token"]
    REGISTRY.discard(body["session_token"])  # close the real conn this session opened


def test_start_with_invalid_start_code_is_401(kiosk_client: TestClient):
    r = kiosk_client.post(
        "/kiosk/interview/start",
        json={"start_code": "not-a-real-code", "language": "it"},
        headers=_h(),
    )
    assert r.status_code == 401


def test_start_with_already_used_start_code_is_401(
    kiosk_client: TestClient, issued_start_code: str
):
    first = kiosk_client.post(
        "/kiosk/interview/start",
        json={"start_code": issued_start_code, "language": "it"},
        headers=_h(),
    )
    assert first.status_code == 200
    REGISTRY.discard(first.json()["session_token"])

    second = kiosk_client.post(
        "/kiosk/interview/start",
        json={"start_code": issued_start_code, "language": "it"},
        headers=_h(),
    )
    assert second.status_code == 401  # single-use: the code is gone after the first consume


def test_submit_advances_a_faked_session(monkeypatch):
    monkeypatch.setattr(config, "KIOSK_TOKEN", TOKEN)
    token = _register_fake_session()
    submit = TestClient(create_app()).post(
        "/kiosk/interview/submit",
        json={"session_token": token, "answer": "so cucinare"},
        headers=_h(),
    )
    assert submit.status_code == 200
    assert submit.json()["step"]["kind"] == "summary"
    REGISTRY.discard(token)


def test_submit_unknown_session_is_404(monkeypatch):
    monkeypatch.setattr(config, "KIOSK_TOKEN", TOKEN)
    client = TestClient(create_app())
    r = client.post(
        "/kiosk/interview/submit",
        json={"session_token": "nope", "answer": "x"},
        headers=_h(),
    )
    assert r.status_code == 404


def test_completed_submit_discards_session_and_closes_conn(monkeypatch):
    monkeypatch.setattr(config, "KIOSK_TOKEN", TOKEN)
    evicted = []

    class CompletingInterview(Interview):
        # Subclasses Interview only so the router's `isinstance(interview,
        # Interview)` guard accepts it; the real constructor (LLM, repo, ...)
        # is deliberately never called.
        def __init__(self) -> None:  # type: ignore[super-init-not-called]
            pass

        def submit(self, answer: str) -> Step:
            return Step("completed", "Abbiamo finito, grazie!")

    token = REGISTRY.create(CompletingInterview(), on_evict=lambda: evicted.append(True))
    client = TestClient(create_app())
    done = client.post(
        "/kiosk/interview/submit", json={"session_token": token, "answer": "sì"}, headers=_h()
    )
    assert done.status_code == 200 and done.json()["step"]["kind"] == "completed"
    assert evicted == [True]  # on_evict ran -> connection closed
    # session is gone: submitting again with the same token -> 404
    again = client.post(
        "/kiosk/interview/submit", json={"session_token": token, "answer": "x"}, headers=_h()
    )
    assert again.status_code == 404


def test_start_failure_closes_connection(monkeypatch, issued_start_code: str):
    monkeypatch.setattr(config, "KIOSK_TOKEN", TOKEN)
    opened: list[psycopg.Connection] = []

    def _open_and_track() -> psycopg.Connection:
        conn = _open_test_conn()
        opened.append(conn)
        return conn

    monkeypatch.setattr(interview_router, "open_kiosk_conn", _open_and_track)

    class BoomInterview:
        def start_on(self, pseudonym: str):
            raise RuntimeError("db down at start")

    monkeypatch.setattr(
        interview_router, "build_kiosk_interview", lambda conn, language: BoomInterview()
    )

    client = TestClient(create_app(), raise_server_exceptions=False)
    r = client.post(
        "/kiosk/interview/start",
        json={"start_code": issued_start_code, "language": "it"},
        headers=_h(),
    )
    assert r.status_code == 500
    assert opened and opened[0].closed  # on_evict-equivalent ran -> connection closed, no leak
