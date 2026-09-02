#!/usr/bin/env bash
set -euo pipefail

# Optional MaryV2 Mac runtime bootstrap.
# Installs no model weights into the repository. All reviewed assets are fetched
# through scripts.fetch_model_candidate into PathConfig().models.

INSTALL_RUNTIMES=0
DOWNLOAD_FAST=0
DOWNLOAD_STT=0
DOWNLOAD_VAD=0
DOWNLOAD_ROLEPLAY=0

for arg in "$@"; do
  case "$arg" in
    --install-runtimes) INSTALL_RUNTIMES=1 ;;
    --download-fast-brain) DOWNLOAD_FAST=1 ;;
    --download-stt) DOWNLOAD_STT=1 ;;
    --download-vad) DOWNLOAD_VAD=1 ;;
    --download-roleplay-lab) DOWNLOAD_ROLEPLAY=1 ;;
    --all)
      INSTALL_RUNTIMES=1; DOWNLOAD_FAST=1; DOWNLOAD_STT=1; DOWNLOAD_VAD=1
      ;;
    -h|--help)
      cat <<'EOF'
MaryV2 Mac character-runtime bootstrap

  --install-runtimes       brew install llama.cpp whisper-cpp
  --download-fast-brain    fetch Qwen3 0.6B Q4_0 (~429 MB)
  --download-stt           fetch whisper.cpp tiny.en Q5_1 (~32 MB)
  --download-vad           fetch Silero VAD (~1.7 MB; hash reported after download)
  --download-roleplay-lab  fetch exact Qwen3 4B base + premade roleplay LoRA (~2.5 GB)
  --all                    install runtimes + small fast-brain/STT/VAD assets

Weights are stored in Mary's local model directory, outside Git.
EOF
      exit 0 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This bootstrap is for macOS." >&2
  exit 2
fi

if [[ $INSTALL_RUNTIMES -eq 1 ]]; then
  if ! command -v brew >/dev/null 2>&1; then
    echo "Homebrew is required for --install-runtimes. Install it explicitly, then rerun." >&2
    exit 2
  fi
  brew list llama.cpp >/dev/null 2>&1 || brew install llama.cpp
  brew list whisper-cpp >/dev/null 2>&1 || brew install whisper-cpp
fi

fetch() {
  python -m scripts.fetch_model_candidate "$1" --download
}

[[ $DOWNLOAD_FAST -eq 1 ]] && fetch qwen3-0.6b-q4-fast-brain
[[ $DOWNLOAD_STT -eq 1 ]] && fetch whispercpp-tiny-en-q5_1
[[ $DOWNLOAD_VAD -eq 1 ]] && fetch sherpa-silero-vad
if [[ $DOWNLOAD_ROLEPLAY -eq 1 ]]; then
  fetch qwen3-4b-heretic-q4km-roleplay-base
  fetch rockerboo-qwen3-4b-roleplay-lora-f16
fi

cat <<'EOF'

Mac runtime bootstrap complete for the selected options.

For local llama.cpp experiments:
  export MARY_LLAMA_CPP_ENABLED=true
  ./scripts/run_llama_cpp_mac.sh

To expose the Mac model to canonical remote Mary Core:
  python -m scripts.node_permissions allow llm.llama_cpp
  python -m scripts.run_capability_node --enroll-only
  python -m scripts.run_capability_node
EOF
