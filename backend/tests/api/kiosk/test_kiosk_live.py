"""End-to-end kiosk API with the real models (requires_llm + requires_voice) and
Postgres. Drives a short synthetic interview over HTTP and a voice round-trip.
Skips unless llama-server + the voice libs/models are available.

`build_interview` is overridden here to bind the Interview to the test database
(bussola_test) — the real factory connects to the default DB name. Synthetic
data only (§9)."""

from __future__ import annotations

import httpx
import psycopg
import pytest
from fastapi.testclient import TestClient

from bussola.api.app import create_app
from bussola.api.kiosk import config
from bussola.api.kiosk.routers import interview as interview_router
from bussola.data import config as db_config
from bussola.data.audit import append_audit
from bussola.guardrails.pii import PiiRedactor
from bussola.guardrails.scope import ScopeGuard
from bussola.interview.interview import Interview
from bussola.data.profiles import ProfileRepository
from bussola.llm.client import HttpxLlmClient

TOKEN = "secret-kiosk"


def _llm_up() -> bool:
    try:
        httpx.get("http://127.0.0.1:8080/health", timeout=3)
        return True
    except Exception:
        return False


def _voice_up() -> bool:
    try:
        import faster_whisper  # noqa: F401
        import piper  # noqa: F401

        from bussola.voice import config as vconfig
        from bussola.voice.tts import TextToSpeech

        return bool(TextToSpeech(voices=vconfig.PIPER_VOICES).synthesize("prova", "it"))
    except Exception:
        return False


requires_stack = pytest.mark.skipif(
    not (_llm_up() and _voice_up()), reason="llama-server o modelli voce non disponibili"
)


@requires_stack
def test_kiosk_interview_and_voice_over_http(monkeypatch, db):
    monkeypatch.setattr(config, "KIOSK_TOKEN", TOKEN)

    def build_on_test_db(language: str):
        conn = psycopg.connect(db_config.dsn("app", dbname="bussola_test"))
        redactor = PiiRedactor()
        llm = HttpxLlmClient()

        def audit(**kwargs: object) -> None:
            append_audit(conn, actor="kiosk", **kwargs)  # type: ignore[arg-type]

        interview = Interview(
            llm,
            ScopeGuard(llm),
            ProfileRepository(conn, redactor, language),
            language=language,
            redactor=redactor,
            audit=audit,
        )
        return interview, conn.close

    monkeypatch.setattr(interview_router, "build_interview", build_on_test_db)

    client = TestClient(create_app())
    h = {"X-Kiosk-Token": TOKEN}

    start = client.post("/kiosk/interview/start", json={"language": "it"}, headers=h)
    assert start.status_code == 200
    token = start.json()["session_token"]
    assert start.json()["step"]["kind"] == "question"

    step = client.post(
        "/kiosk/interview/submit",
        json={"session_token": token, "answer": "So cucinare e parlo italiano."},
        headers=h,
    ).json()["step"]
    assert step["kind"] in ("summary", "refusal", "clarification", "unavailable")

    # voice round-trip through the endpoints
    audio = client.post(
        "/kiosk/voice/synthesize", json={"text": "Sai cucinare?", "language": "it"}, headers=h
    )
    assert audio.status_code == 200 and audio.content
    back = client.post(
        "/kiosk/voice/transcribe",
        data={"language": "it"},
        files={"audio": ("a.wav", audio.content, "audio/wav")},
        headers=h,
    )
    assert back.status_code == 200 and back.json()["text"]
