import time

import pytest
from fastapi.testclient import TestClient

from bussola.api.app import create_app
from bussola.api.kiosk import config
from bussola.api.kiosk.routers import voice as voice_router
from bussola.voice.errors import VoiceUnavailable
from bussola.voice.models import Transcription

TOKEN = "secret-kiosk"


class FakeStt:
    def __init__(self, *, text="", raises=False, delay=0.0):
        self._text, self._raises, self._delay = text, raises, delay

    def transcribe(self, audio: bytes, language: str) -> Transcription:
        if self._delay:
            time.sleep(self._delay)
        if self._raises:
            raise VoiceUnavailable("down")
        return Transcription(text=self._text, language=language)


class FakeTts:
    def __init__(self, *, audio=b"WAV", delay=0.0):
        self._audio, self._delay = audio, delay

    def synthesize(self, text: str, language: str) -> bytes | None:
        if self._delay:
            time.sleep(self._delay)
        return self._audio


@pytest.fixture(autouse=True)
def _token(monkeypatch):
    monkeypatch.setattr(config, "KIOSK_TOKEN", TOKEN)


def _client() -> TestClient:
    return TestClient(create_app())


def _h() -> dict:
    return {"X-Kiosk-Token": TOKEN}


def test_transcribe_returns_text(monkeypatch):
    monkeypatch.setattr(voice_router, "_stt", lambda: FakeStt(text="so cucinare"))
    r = _client().post(
        "/kiosk/voice/transcribe",
        data={"language": "it"},
        files={"audio": ("a.wav", b"AUDIO", "audio/wav")},
        headers=_h(),
    )
    assert r.status_code == 200 and r.json()["text"] == "so cucinare"


def test_transcribe_unavailable_is_503(monkeypatch):
    monkeypatch.setattr(voice_router, "_stt", lambda: FakeStt(raises=True))
    r = _client().post(
        "/kiosk/voice/transcribe",
        data={"language": "it"},
        files={"audio": ("a.wav", b"AUDIO", "audio/wav")},
        headers=_h(),
    )
    assert r.status_code == 503


def test_transcribe_timeout_is_503(monkeypatch):
    monkeypatch.setattr(config, "VOICE_TIMEOUT", 0.1)
    monkeypatch.setattr(voice_router, "_stt", lambda: FakeStt(text="x", delay=1.0))
    r = _client().post(
        "/kiosk/voice/transcribe",
        data={"language": "it"},
        files={"audio": ("a.wav", b"AUDIO", "audio/wav")},
        headers=_h(),
    )
    assert r.status_code == 503


def test_synthesize_returns_audio(monkeypatch):
    monkeypatch.setattr(voice_router, "_tts", lambda: FakeTts(audio=b"WAVDATA"))
    r = _client().post(
        "/kiosk/voice/synthesize", json={"text": "ciao", "language": "it"}, headers=_h()
    )
    assert r.status_code == 200 and r.content == b"WAVDATA"


def test_synthesize_none_is_204(monkeypatch):
    monkeypatch.setattr(voice_router, "_tts", lambda: FakeTts(audio=None))
    r = _client().post(
        "/kiosk/voice/synthesize", json={"text": "مرحبا", "language": "ar"}, headers=_h()
    )
    assert r.status_code == 204


def test_synthesize_timeout_is_204(monkeypatch):
    monkeypatch.setattr(config, "VOICE_TIMEOUT", 0.1)
    monkeypatch.setattr(voice_router, "_tts", lambda: FakeTts(audio=b"WAV", delay=1.0))
    r = _client().post(
        "/kiosk/voice/synthesize", json={"text": "ciao", "language": "it"}, headers=_h()
    )
    assert r.status_code == 204


def test_transcribe_requires_token(monkeypatch):
    r = _client().post(
        "/kiosk/voice/transcribe",
        data={"language": "it"},
        files={"audio": ("a.wav", b"AUDIO", "audio/wav")},
    )
    assert r.status_code == 401
