"""Round-trip TTS -> STT with the real models (requires_voice). Self-contained:
synthesize a known phrase, transcribe the audio back, assert the key words
survive. Skips unless faster-whisper + piper are installed and the models are
present. Synthetic phrases only (§9)."""

from __future__ import annotations

import pytest

from bussola.voice.stt import SpeechToText
from bussola.voice.tts import TextToSpeech


def _voice_available() -> bool:
    try:
        import faster_whisper  # noqa: F401
        import piper  # noqa: F401
    except Exception:
        return False
    from bussola.voice import config

    try:
        return bool(TextToSpeech(voices=config.PIPER_VOICES).synthesize("prova", "it"))
    except Exception:
        return False


requires_voice = pytest.mark.skipif(
    not _voice_available(), reason="modelli voce/librerie non disponibili"
)


@requires_voice
@pytest.mark.parametrize(
    "language,phrase,keyword",
    [
        # Full sentences (representative of real interview answers): a 2-word clip
        # gives the ASR too little signal and mis-transcribes intermittently.
        ("it", "so cucinare e faccio manutenzione di base", "cucin"),
        ("en", "i can cook and do basic maintenance", "cook"),
    ],
)
def test_tts_stt_round_trip(language: str, phrase: str, keyword: str) -> None:
    audio = TextToSpeech().synthesize(phrase, language)
    assert audio is not None  # a configured language must produce audio
    transcription = SpeechToText().transcribe(audio, language)
    assert keyword.lower() in transcription.text.lower()
