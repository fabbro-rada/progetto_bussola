"""Speech-to-Text service. The degradation contract lives here: ANY engine
failure becomes `VoiceUnavailable`, so the caller falls back to text (§3/§7.1).
The real faster-whisper engine imports the library lazily, so this module and
its unit tests do not require faster-whisper to be installed."""

from __future__ import annotations

import io
from typing import Protocol

from bussola.voice import config
from bussola.voice.errors import VoiceUnavailable
from bussola.voice.models import Transcription


class SttEngine(Protocol):
    def transcribe(self, audio: bytes, language: str) -> str: ...


class SpeechToText:
    def __init__(self, engine: SttEngine | None = None) -> None:
        self._engine = engine

    def _get_engine(self) -> SttEngine:
        if self._engine is None:
            self._engine = _FasterWhisperEngine()
        return self._engine

    def transcribe(self, audio: bytes, language: str) -> Transcription:
        try:
            text = self._get_engine().transcribe(audio, language)
        except Exception as exc:  # degradation net: voice never blocks (§3)
            raise VoiceUnavailable(str(exc)) from exc
        return Transcription(text=text, language=language)


class _FasterWhisperEngine:
    """Real STT engine (faster-whisper, CTranslate2). Imported lazily.

    NOTE: verify the transcribe signature against the installed faster-whisper
    version; the `requires_voice` round-trip test (Task 4) is the check."""

    def __init__(self) -> None:
        from faster_whisper import WhisperModel

        self._model = WhisperModel(
            config.STT_MODEL, device=config.STT_DEVICE, compute_type=config.STT_COMPUTE_TYPE
        )

    def transcribe(self, audio: bytes, language: str) -> str:
        segments, _info = self._model.transcribe(io.BytesIO(audio), language=language)
        return "".join(segment.text for segment in segments).strip()
