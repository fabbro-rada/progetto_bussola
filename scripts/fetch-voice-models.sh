#!/bin/bash
# Download the voice models ONCE, so nothing has to download at request time:
#   1. the Piper TTS voices (curl, below), and
#   2. the faster-whisper STT model (pre-download at the end).
# Left to first-use, the STT model (~1.5 GB) downloads during the first real
# transcription and blows past the voice timeout, so kiosk dictation silently
# fails on a fresh machine — hence the preload here.
# The four Piper voices below had their licences verified on 2026-07-28
# (STATO_TECNICO §14): ljspeech=public-domain, paola=CC0, davefx=CC0,
# siwis=CC-BY-4.0 (attribution). Any NEW/changed voice MUST be re-verified
# permissive (§3) and recorded there.
set -euo pipefail

# Anchor to the repo root so the download lands where the backend reads it
# (bussola.voice.config.VOICE_MODEL_DIR defaults to <repo>/models/voice),
# regardless of the directory this script is invoked from.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VOICE_DIR="${BUSSOLA_VOICE_MODEL_DIR:-$ROOT/models/voice}"
BASE="https://huggingface.co/rhasspy/piper-voices/resolve/main"
mkdir -p "$VOICE_DIR"

# language : relative path on the piper-voices repo (voice .onnx + .onnx.json)
# When ADDING or CHANGING a voice below, re-verify its licence per the header.
download() {
  local rel="$1" name="$2"
  for ext in onnx onnx.json; do
    if [ ! -f "$VOICE_DIR/$name.$ext" ]; then
      echo "Downloading $name.$ext ..."
      curl -L --fail -o "$VOICE_DIR/$name.$ext.part" "$BASE/$rel.$ext"
      mv "$VOICE_DIR/$name.$ext.part" "$VOICE_DIR/$name.$ext"
    fi
  done
}

download "it/it_IT/paola/medium/it_IT-paola-medium" "it_IT-paola-medium"
download "en/en_US/ljspeech/medium/en_US-ljspeech-medium" "en_US-ljspeech-medium"
download "fr/fr_FR/siwis/medium/fr_FR-siwis-medium" "fr_FR-siwis-medium"
download "es/es_ES/davefx/medium/es_ES-davefx-medium" "es_ES-davefx-medium"

echo "Piper voices done. Licences verified & recorded in STATO_TECNICO §14 (2026-07-28)."

# --- STT model (faster-whisper) --------------------------------------------
# Pre-download the speech-to-text model into the HuggingFace cache, using the
# backend venv. device=cpu / compute_type=int8 matches the runtime default
# (STATO_TECNICO §5) and needs no GPU — it only triggers the one-time download.
PY="$ROOT/backend/.venv/bin/python"
if [ ! -x "$PY" ]; then
  echo "STT: backend venv not found at $PY — skipping preload."
  echo "     Set it up first: (cd backend && uv sync --all-extras), then re-run this script."
else
  echo "Pre-downloading the STT model (faster-whisper) — one-time, may take a while ..."
  set +e
  "$PY" - <<'PYEOF'
import sys
try:
    from faster_whisper import WhisperModel
    from bussola.voice import config
except ModuleNotFoundError as exc:
    print(f"STT: '{exc.name}' not installed (backend 'voice' extra) — skipping preload.")
    print("     Install with: (cd backend && uv sync --all-extras)")
    sys.exit(3)
model = config.STT_MODEL
print(f"STT: fetching '{model}' (device=cpu, compute_type=int8) ...")
WhisperModel(model, device="cpu", compute_type="int8")
print(f"STT: model '{model}' ready.")
PYEOF
  rc=$?
  set -e
  if [ "$rc" != 0 ] && [ "$rc" != 3 ]; then
    echo "WARN: STT preload failed (exit $rc) — it will download on first use instead."
  fi
fi

echo "Done."
