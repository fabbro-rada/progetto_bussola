"""Text-to-Speech service. Absence of audio is a NORMAL fallback, not an error:
a language with no configured voice (Arabic by default, §8) or any engine
failure yields `None`, so the caller shows text (§3/§7.1). The real Piper engine
imports the library lazily, so this module and its unit tests do not require
piper-tts to be installed."""

from __future__ import annotations

import io
import re
import wave
from typing import Protocol

from bussola.voice import config

# Emoji / pictographic symbols a TTS voice would otherwise read aloud (Piper
# speaks e.g. "smiling face"). We strip only the pictographic Unicode blocks —
# never letters or marks — so Arabic and accented Latin text stay intact. This
# is a safety net: the interview prompts also instruct the LLM to avoid emoji.
_EMOJI_RE = re.compile(
    "["
    "\U0001f300-\U0001faff"  # symbols & pictographs, emoticons, transport, extended-A
    "\U0001f1e6-\U0001f1ff"  # regional indicators (flags)
    "\U00002600-\U000027bf"  # miscellaneous symbols + dingbats
    "\U00002300-\U000023ff"  # miscellaneous technical (⌛ ⏳ …)
    "\U00002b00-\U00002bff"  # miscellaneous symbols and arrows (★ … )
    "\U0000fe00-\U0000fe0f"  # variation selectors
    "\U0000200d"  # zero-width joiner
    "]"
)


def strip_emoji(text: str) -> str:
    """Remove emoji/pictographs and collapse the whitespace they leave behind,
    so read-aloud text never speaks an emoji's name."""
    return re.sub(r" {2,}", " ", _EMOJI_RE.sub("", text)).strip()


class TtsEngine(Protocol):
    def synthesize(self, text: str, voice_model: str) -> bytes: ...


class TextToSpeech:
    def __init__(
        self, engine: TtsEngine | None = None, voices: dict[str, str] | None = None
    ) -> None:
        self._engine = engine
        self._voices = voices if voices is not None else config.PIPER_VOICES

    def _get_engine(self) -> TtsEngine:
        if self._engine is None:
            self._engine = _PiperEngine()
        return self._engine

    def synthesize(self, text: str, language: str) -> bytes | None:
        voice_model = self._voices.get(language)
        if voice_model is None:
            return None  # no voice for this language (e.g. Arabic) -> text fallback
        spoken = strip_emoji(text)  # never read an emoji's name aloud
        try:
            return self._get_engine().synthesize(spoken, voice_model)
        except Exception:  # TTS failure -> text fallback, never blocks (§3)
            return None


class _PiperEngine:
    """Real TTS engine (Piper). Imported lazily; loaded voices are cached.

    NOTE: verify the synthesize signature against the installed piper-tts
    version; the `requires_voice` round-trip test (Task 4) is the check."""

    def __init__(self) -> None:
        self._loaded: dict[str, object] = {}

    def synthesize(self, text: str, voice_model: str) -> bytes:
        voice = self._load(voice_model)
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            # piper-tts >= 1.5: synthesize_wav writes into a wave.Wave_write and
            # sets the WAV format itself (synthesize() now returns AudioChunks).
            voice.synthesize_wav(text, wav_file)  # type: ignore[attr-defined]
        return buffer.getvalue()

    def _load(self, voice_model: str) -> object:
        if voice_model not in self._loaded:
            import os

            from piper import PiperVoice

            self._loaded[voice_model] = PiperVoice.load(
                os.path.join(config.VOICE_MODEL_DIR, voice_model)
            )
        return self._loaded[voice_model]
