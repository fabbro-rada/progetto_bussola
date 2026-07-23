#!/bin/bash
# Download the voice models ONCE: the faster-whisper STT model is fetched on
# first use by the library; here we download the Piper voices. Verify EACH
# voice's license is permissive (§3) before use, and record it in STATO_TECNICO.
set -euo pipefail

VOICE_DIR="${BUSSOLA_VOICE_MODEL_DIR:-models/voice}"
BASE="https://huggingface.co/rhasspy/piper-voices/resolve/main"
mkdir -p "$VOICE_DIR"

# language : relative path on the piper-voices repo (voice .onnx + .onnx.json)
# NOTE: confirm the exact voice + license before committing to it (§3).
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
download "en/en_US/lessac/medium/en_US-lessac-medium" "en_US-lessac-medium"
download "fr/fr_FR/siwis/medium/fr_FR-siwis-medium" "fr_FR-siwis-medium"
download "es/es_ES/davefx/medium/es_ES-davefx-medium" "es_ES-davefx-medium"

echo "Done. Verify each voice's LICENSE (MODEL_CARD) is permissive before use."
