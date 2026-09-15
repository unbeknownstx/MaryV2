#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHON="$ROOT/.venv/bin/python"

if [[ ! -x "$PYTHON" ]]; then
  echo "MaryV2 .venv was not found. Run scripts/setup_macos.sh first." >&2
  exit 1
fi

if [[ -z "${MARY_ENV_FILE:-}" && -f "$ROOT/.env" ]]; then
  export MARY_ENV_FILE="$ROOT/.env"
fi

HARDWARE_PROFILE="${MARY_MACOS_HARDWARE_PROFILE:-mac-apple-silicon}"
BENCHMARK_PROFILE="${MARY_NODE_BENCHMARK_PROFILE:-$HOME/.maryv2/node_benchmark_13_11.json}"
EXTRA_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --hardware-profile)
      [[ $# -ge 2 ]] || { echo "--hardware-profile requires a value" >&2; exit 2; }
      HARDWARE_PROFILE="$2"; shift 2 ;;
    --benchmark-profile)
      [[ $# -ge 2 ]] || { echo "--benchmark-profile requires a value" >&2; exit 2; }
      BENCHMARK_PROFILE="$2"; shift 2 ;;
    *) EXTRA_ARGS+=("$1"); shift ;;
  esac
done

if [[ "$HARDWARE_PROFILE" == "mac-apple-silicon" ]]; then
  export OLLAMA_CONTEXT_LENGTH="${OLLAMA_CONTEXT_LENGTH:-4096}"
  export OLLAMA_NUM_PARALLEL="${OLLAMA_NUM_PARALLEL:-1}"
  export OLLAMA_MAX_LOADED_MODELS="${OLLAMA_MAX_LOADED_MODELS:-1}"
fi

START_OLLAMA=1
case "${MARY_NODE_START_OLLAMA:-true}" in
  0|false|FALSE|no|NO|off|OFF) START_OLLAMA=0 ;;
esac

if [[ "$START_OLLAMA" == "1" ]]; then
  OLLAMA_READY=0
  if /usr/bin/curl -fsS --max-time 2 http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    OLLAMA_READY=1
  fi
  if [[ "$OLLAMA_READY" == "0" ]] && command -v ollama >/dev/null 2>&1; then
    mkdir -p "$HOME/.maryv2"
    nohup "$(command -v ollama)" serve >"$HOME/.maryv2/ollama-node.log" 2>&1 &
    sleep 2
  fi
fi

NODE_ARGS=(-m scripts.run_home_node --hardware-profile "$HARDWARE_PROFILE")
if [[ -f "$BENCHMARK_PROFILE" ]]; then
  NODE_ARGS+=(--benchmark-profile "$BENCHMARK_PROFILE")
fi
NODE_ARGS+=("${EXTRA_ARGS[@]}")
exec "$PYTHON" "${NODE_ARGS[@]}"
