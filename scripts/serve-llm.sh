#!/bin/bash
# Download the model (once) and run llama-server on the GPU, OpenAI-compatible.
# Requires a GPU llama-server binary on PATH — Vulkan prebuilt recommended (no CUDA
# toolkit) or a CUDA build. Install steps: README "Installare llama-server".
# The official Qwen2.5-7B-Instruct-GGUF Q4_K_M is split into 2 shards; llama.cpp
# loads a split model when pointed at shard 1 (the other shards must sit alongside).
set -euo pipefail

MODEL_DIR="${MODEL_DIR:-models}"
BASE_URL="https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF/resolve/main"
SHARD1="qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf"
SHARD2="qwen2.5-7b-instruct-q4_k_m-00002-of-00002.gguf"
PORT="${BUSSOLA_LLM_PORT:-8080}"

mkdir -p "$MODEL_DIR"
for shard in "$SHARD1" "$SHARD2"; do
  if [ ! -f "$MODEL_DIR/$shard" ]; then
    echo "Downloading $shard ..."
    curl -L --fail -o "$MODEL_DIR/$shard.part" "$BASE_URL/$shard"
    mv "$MODEL_DIR/$shard.part" "$MODEL_DIR/$shard"
  fi
done

command -v llama-server >/dev/null || {
  echo "llama-server not found on PATH — install it first (see README 'Installare llama-server'; Vulkan prebuilt recommended)" >&2
  exit 1
}

# -ngl 999: offload all layers to GPU; -c 8192: context. Point at shard 1.
exec llama-server \
  --model "$MODEL_DIR/$SHARD1" \
  --host 127.0.0.1 --port "$PORT" \
  -ngl 999 -c 8192 --temp 0
