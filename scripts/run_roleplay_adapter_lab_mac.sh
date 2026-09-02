#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEFAULT_MODEL_ROOT="${HOME}/Library/Application Support/MaryV2/models"
MODEL_DIR="${MARY_MODEL_LAB_DIR:-${MARY_MODEL_DIR:-$DEFAULT_MODEL_ROOT}/llm}"
BASE="$MODEL_DIR/p-e-w_Qwen3-4B-Instruct-2507-heretic-Q4_K_M.gguf"
ADAPTER="$MODEL_DIR/qwen3-4b-roleplay-lora-f16.gguf"
HOST="${MARY_LLAMA_CPP_HOST:-127.0.0.1}"
PORT="${MARY_LLAMA_CPP_PORT:-8080}"

if [[ ! -f "$BASE" || ! -f "$ADAPTER" ]]; then
  cat >&2 <<EOF
Adapter Lab assets are not installed. Fetch them explicitly:
  python -m scripts.fetch_model_candidate qwen3-4b-heretic-q4km-roleplay-base --download
  python -m scripts.fetch_model_candidate rockerboo-qwen3-4b-roleplay-lora-f16 --download

Expected:
  $BASE
  $ADAPTER
EOF
  exit 3
fi

SERVER=""
if command -v llama-server >/dev/null 2>&1; then SERVER="llama-server"; fi
if [[ -z "$SERVER" ]]; then
  echo "llama-server not found; install/build llama.cpp first." >&2
  exit 2
fi

# Adapter is loaded but MaryV2 controls per-request scale via
# MARY_LLAMA_CPP_LORA_SCALES. Start low and evaluate instead of assuming the
# adapter defines Mary.
exec "$SERVER" -m "$BASE" --lora "$ADAPTER" --host "$HOST" --port "$PORT"
