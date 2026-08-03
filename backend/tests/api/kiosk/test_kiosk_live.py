"""End-to-end kiosk API with the real models (requires_llm + requires_voice) and
Postgres. Drives a short synthetic interview over HTTP and a voice round-trip.
Skips unless llama-server + the voice libs/models are available.

`open_kiosk_conn` is overridden here to bind the Interview session to the
test database (bussola_test) — the real factory connects to the default DB
name; this mirrors `test_followup_start.py`'s `_open_test_conn` override. The
kiosk `/start` endpoint now consumes a one-time `start_code` (Task 5), so a
pseudonym + code are provisioned against the SAME test DB before the request.
Synthetic data only (§9)."""

from __future__ import annotations

import httpx
import psycopg
import pytest
from fastapi.testclient import TestClient

from bussola.api.app import create_app
from bussola.api.kiosk import config
from bussola.api.kiosk.routers import interview as interview_router
from bussola.data import config as db_config
from bussola.data.profiles import create_empty_profile
from bussola.startcode.service import StartCodeService

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

    def _open_test_conn() -> psycopg.Connection:
        return psycopg.connect(db_config.dsn("app", dbname="bussola_test"))

    monkeypatch.setattr(interview_router, "open_kiosk_conn", _open_test_conn)

    # Provision a pseudonym + one-time start_code against the SAME test DB
    # (operator-provisioning stand-in — Task 5 removed anonymous self-start).
    provision_conn = _open_test_conn()
    pseudonym = create_empty_profile(provision_conn)
    provision_conn.commit()
    start_code = StartCodeService(provision_conn).issue(pseudonym)
    provision_conn.commit()
    provision_conn.close()

    client = TestClient(create_app())
    h = {"X-Kiosk-Token": TOKEN}

    start = client.post(
        "/kiosk/interview/start", json={"start_code": start_code, "language": "it"}, headers=h
    )
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
