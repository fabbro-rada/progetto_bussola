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
    # True only if faster-whisper AND the configured model are already local:
    # local_files_only=True checks the cache and raises rather than downloading.
    try:
        from faster_whisper import WhisperModel

        from bussola.voice import config

        WhisperModel(
            config.STT_MODEL,
            device=config.STT_DEVICE,
            compute_type=config.STT_COMPUTE_TYPE,
            local_files_only=True,
        )
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
    container = av.open(io.BytesIO(data))
    stream = next(s for s in container.streams if s.type == "audio")
    assert stream.codec_context.name == "opus"  # the codec Chromium's MediaRecorder emits
    samples = sum(frame.samples for frame in container.decode(stream))
    container.close()
    assert samples > 0  # decoded to real PCM, not an empty/garbled stream


@requires_stt_model
def test_chromium_webm_transcribes_on_production_path() -> None:
    # Exactly what the /kiosk/voice/transcribe endpoint does: raw WebM bytes ->
    # SpeechToText (faster-whisper) -> text. The recorded phrase was about a
    # kitchen-helper job ("aiuto cuoco in una mensa").
    from bussola.voice.stt import SpeechToText

    text = SpeechToText().transcribe(FIXTURE.read_bytes(), "it").text.lower()
    assert "cuoco" in text or "mensa" in text
