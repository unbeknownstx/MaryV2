#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHON="$ROOT/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  echo "MaryV2 .venv was not found. Run scripts/setup_macos.sh first." >&2
  exit 1
fi
exec "$PYTHON" -m scripts.run_desktop
