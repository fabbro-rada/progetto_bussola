"""Kiosk API tunables, from environment with safe defaults."""

from __future__ import annotations

import os

from bussola.env import load_project_dotenv

load_project_dotenv()

# Pre-shared device token; empty = not configured = deny all (fail closed).
KIOSK_TOKEN = os.environ.get("BUSSOLA_KIOSK_TOKEN", "")
VOICE_TIMEOUT = float(os.environ.get("BUSSOLA_VOICE_TIMEOUT", "10.0"))
SESSION_TTL = int(os.environ.get("BUSSOLA_KIOSK_SESSION_TTL", "1800"))  # 30 min
# Cap on a dictation upload (§3 prevenzione dell'uso scorretto): a legitimate
# spoken answer is a few seconds of audio (~1-2 MB); 10 MB leaves ample room
# while bounding what a single request can buffer into memory.
MAX_AUDIO_BYTES = int(os.environ.get("BUSSOLA_MAX_AUDIO_BYTES", str(10 * 1024 * 1024)))
# Cap on text handed to the TTS (the questions/summaries read aloud are short);
# mirrors the scope guard's input ceiling so nothing unbounded reaches synthesis.
MAX_TTS_CHARS = int(os.environ.get("BUSSOLA_MAX_TTS_CHARS", "2000"))
