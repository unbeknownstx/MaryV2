#!/usr/bin/env bash
set -euo pipefail

# Explicit local specialist lane for Apple Silicon. This does not replace Mary
# Core or change the default cloud-first router. It starts an OpenAI-compatible
# llama.cpp server which Mary can use only when MARY_LLAMA_CPP_ENABLED=true or
# an explicit provider override selects llama_cpp.

HOST="${MARY_LLAMA_CPP_HOST:-127.0.0.1}"
PORT="${MARY_LLAMA_CPP_PORT:-8080}"
MODEL_REF="${MARY_LLAMA_CPP_HF_MODEL:-ggml-org/Qwen3-1.7B-GGUF:Q4_K_M}"

if command -v llama-server >/dev/null 2>&1; then
  exec llama-server -hf "$MODEL_REF" --host "$HOST" --port "$PORT"
fi
if command -v llama >/dev/null 2>&1; then
  exec llama serve -hf "$MODEL_REF" --host "$HOST" --port "$PORT"
fi

cat >&2 <<'EOF'
llama.cpp was not found.
On a current macOS install, one supported option is:
  brew install llama.cpp
Then rerun this script.
EOF
exit 2
