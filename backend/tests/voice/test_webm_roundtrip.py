"""Round-trip for the EXACT audio the kiosk produces: a Chromium `MediaRecorder`
WebM/Opus clip (`audio/webm;codecs=opus`, `new MediaRecorder(stream)` with no
options). The fixture `kiosk-sample.webm` was recorded once in Chromium — a
developer test voice saying a neutral work phrase (§9: not profiled-person data,
just synthetic test audio). This guards the S10 top-risk: that a REAL browser
clip decodes and transcribes on the production path (until now only WAV had been
exercised end-to-end).

- `test_chromium_webm_opus_decodes`: PyAV only — cheap, runs in CI wherever `av`
  is installed. This is the risk that mattered (does the container/codec decode?).
- `test_chromium_webm_transcribes_on_production_path`: the full SpeechToText path;
  SKIPS unless the configured Whisper model is already available locally (never
  downloads), mirroring `test_voice_live.py`'s requires_voice convention."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "kiosk-sample.webm"


def _av_available() -> bool:
    try:
        import av  # noqa: F401

        return True
    except Exception:
        return False


requires_av = pytest.mark.skipif(not _av_available(), reason="PyAV (av) non installato")


def _stt_model_available() -> bool:
    # True only if faster-whisper AND the configured model are already local.
    # Uses download_model(local_files_only=True) — a cache lookup that raises
    # rather than downloading, and (unlike constructing WhisperModel) does NOT
    # load the model into memory at collection time.
    try:
        import os

        from faster_whisper import download_model

        from bussola.voice import config

        if os.path.isdir(config.STT_MODEL):
            return True
        download_model(config.STT_MODEL, local_files_only=True)
        return True
    except Exception:
        return False


requires_stt_model = pytest.mark.skipif(
    not _stt_model_available(), reason="modello STT non disponibile localmente (nessun download)"
)


@requires_av
def test_chromium_webm_opus_decodes() -> None:
    import av

    data = FIXTURE.read_bytes()
    assert data[:4] == b"\x1a\x45\xdf\xa3"  # EBML/Matroska magic -> a real WebM container
    with av.open(io.BytesIO(data)) as container:
        stream = next(s for s in container.streams if s.type == "audio")
        assert stream.codec_context.name == "opus"  # the codec Chromium's MediaRecorder emits
        samples = sum(frame.samples for frame in container.decode(stream))
    # >= ~1s of 48 kHz audio (the fixture is ~6.6s): a real decode, and a floor
    # that a truncated/garbled clip would fail rather than squeak past on >0.
    assert samples >= 48_000


@requires_stt_model
def test_chromium_webm_transcribes_on_production_path() -> None:
    # Exactly what the /kiosk/voice/transcribe endpoint does: raw WebM bytes ->
    # SpeechToText (faster-whisper) -> text. The recorded phrase was about a
    # kitchen-helper job ("aiuto cuoco in una mensa").
    from bussola.voice.stt import SpeechToText

    text = SpeechToText().transcribe(FIXTURE.read_bytes(), "it").text.lower()
    assert "cuoco" in text or "mensa" in text
