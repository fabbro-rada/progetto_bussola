import pytest

from bussola.voice.errors import VoiceUnavailable
from bussola.voice.models import Transcription
from bussola.voice.stt import SpeechToText


class FakeStt:
    def __init__(self, *, text: str = "", raises: bool = False) -> None:
        self._text = text
        self._raises = raises
        self.calls: list[tuple[bytes, str]] = []

    def transcribe(self, audio: bytes, language: str) -> str:
        self.calls.append((audio, language))
        if self._raises:
            raise RuntimeError("engine down")
        return self._text


def test_transcribe_returns_transcription():
    engine = FakeStt(text="so cucinare")
    result = SpeechToText(engine=engine).transcribe(b"AUDIO", "it")
    assert isinstance(result, Transcription)
    assert result.text == "so cucinare"
    assert result.language == "it"


def test_language_hint_is_propagated_to_engine():
    engine = FakeStt(text="hello")
    SpeechToText(engine=engine).transcribe(b"AUDIO", "en")
    assert engine.calls == [(b"AUDIO", "en")]


def test_engine_failure_raises_voice_unavailable():
    with pytest.raises(VoiceUnavailable):
        SpeechToText(engine=FakeStt(raises=True)).transcribe(b"AUDIO", "it")


def test_engine_construction_failure_raises_voice_unavailable(monkeypatch):
    class RaisingEngine:
        def __init__(self) -> None:
            raise RuntimeError("model load failed")

    monkeypatch.setattr("bussola.voice.stt._FasterWhisperEngine", RaisingEngine)
    with pytest.raises(VoiceUnavailable):
        SpeechToText().transcribe(b"AUDIO", "it")
