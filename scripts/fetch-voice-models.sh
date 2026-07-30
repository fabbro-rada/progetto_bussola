#!/bin/bash
# Download the voice models ONCE: the faster-whisper STT model is fetched on
# first use by the library; here we download the Piper voices. The four voices
# below had their licences verified on 2026-07-28 (STATO_TECNICO §14):
# ljspeech=public-domain, paola=CC0, davefx=CC0, siwis=CC-BY-4.0 (attribution).
# Any NEW/changed voice MUST be re-verified permissive (§3) and recorded there.
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

echo "Done. Voice licences verified & recorded in STATO_TECNICO §14 (2026-07-28)."
