"""Voice domain errors."""

from __future__ import annotations


class VoiceUnavailable(Exception):
    """STT could not produce a transcription; the caller falls back to text."""
