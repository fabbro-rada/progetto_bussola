"""Voice tunables, from environment with safe defaults.

STT runs on CPU by default so the 8 GB GPU stays fully with the LLM
(STATO_TECNICO §5); `device`/`compute_type` are env-overridable to `cuda`
when VRAM allows. The Piper voice map intentionally omits Arabic: Arabic TTS
falls back to text until a permissive, adequate voice is validated (§8)."""

from __future__ import annotations

import os
from pathlib import Path

from bussola.env import load_project_dotenv

load_project_dotenv()

STT_MODEL = os.environ.get("BUSSOLA_STT_MODEL", "large-v3-turbo")
STT_DEVICE = os.environ.get("BUSSOLA_STT_DEVICE", "cpu")
STT_COMPUTE_TYPE = os.environ.get("BUSSOLA_STT_COMPUTE_TYPE", "int8")

# Piper voices live at <repo-root>/models/voice (top-level shared runtime assets,
# where scripts/fetch-voice-models.sh puts them). The backend runs with CWD=
# backend/ (uvicorn does `cd backend`; pytest runs there too), so a CWD-relative
# default silently missed the models and broke read-aloud (§1). Anchor the default
# to the repo root instead — this file is <repo>/backend/src/bussola/voice/config.py,
# so parents[4] == <repo>. Overridable via BUSSOLA_VOICE_MODEL_DIR in production.
_REPO_ROOT = Path(__file__).resolve().parents[4]
VOICE_MODEL_DIR = os.environ.get("BUSSOLA_VOICE_MODEL_DIR", str(_REPO_ROOT / "models" / "voice"))

# language -> Piper voice model filename (resolved under VOICE_MODEL_DIR).
# Only permissively-licensed voices (§3). Arabic is intentionally absent
# (text fallback) until validated on the pilot (§8).
PIPER_VOICES: dict[str, str] = {
    "it": os.environ.get("BUSSOLA_PIPER_VOICE_IT", "it_IT-paola-medium.onnx"),
    # ljspeech, not lessac: lessac's Blizzard-2013 dataset is research-only
    # (non-permissive, §3). ljspeech is LJ Speech (public domain), trained
    # from scratch. Verified 2026-07-28 (STATO_TECNICO §14).
    "en": os.environ.get("BUSSOLA_PIPER_VOICE_EN", "en_US-ljspeech-medium.onnx"),
    "fr": os.environ.get("BUSSOLA_PIPER_VOICE_FR", "fr_FR-siwis-medium.onnx"),
    "es": os.environ.get("BUSSOLA_PIPER_VOICE_ES", "es_ES-davefx-medium.onnx"),
}
