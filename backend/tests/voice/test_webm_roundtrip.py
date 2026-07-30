"""Round-trip of a REAL browser recording through the STT path (top pre-pilot
risk, STATO_TECNICO §14). The kiosk's `MediaRecorder` produces WebM/Opus; every
prior voice test used WAV. This feeds a genuine Chromium recording
(`fixtures/kiosk-sample.webm`: WebM/Matroska + Opus, 48 kHz mono) through the
real `SpeechToText` service — faster-whisper decodes it via `av` internally —
and asserts the work-domain content survives.

Synthetic content (§9): a scripted answer, not a real detained person's data.

Gated on STT only (not the shared `requires_voice`, which also needs Piper TTS):
the model is loaded in a module fixture, so an *unavailable model* skips, while
a *decode/transcription failure* on a loaded model fails loudly — the regression
this test exists to catch.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from bussola.voice.stt import SpeechToText

_FIXTURE = Path(__file__).parent / "fixtures" / "kiosk-sample.webm"


@pytest.fixture(scope="module")
def stt() -> SpeechToText:
    if importlib.util.find_spec("faster_whisper") is None:
        pytest.skip("faster-whisper non installato")
    from bussola.voice.stt import _FasterWhisperEngine

    try:
        engine = _FasterWhisperEngine()  # loads the Whisper model (skip if absent)
    except Exception as exc:  # noqa: BLE001 - any load failure means model unavailable
        pytest.skip(f"modello STT non caricabile: {exc}")
    return SpeechToText(engine=engine)


def test_real_chromium_webm_opus_transcribes(stt: SpeechToText) -> None:
    audio = _FIXTURE.read_bytes()
    # Model availability is handled by the `stt` fixture, so a failure here means
    # the real Chromium WebM/Opus no longer decodes+transcribes — a real regression.
    result = stt.transcribe(audio, "it")
    text = result.text.lower()
    assert "cuoco" in text and "mensa" in text, result.text
    assert result.language == "it"
