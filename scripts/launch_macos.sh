#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHON="$ROOT/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  echo "MaryV2 .venv was not found. Run scripts/setup_macos.sh first." >&2
  exit 1
fi

# Keep the generated Vite bundle synchronized with the checked-in desktop
# source. Otherwise Qt can keep running an older desktop/dist build after a
# source pull and make a real fix look as though it never landed.
DIST_INDEX="$ROOT/desktop/dist/index.html"
NEEDS_BUILD=0
if [[ ! -f "$DIST_INDEX" ]]; then
  NEEDS_BUILD=1
elif find "$ROOT/desktop/src" "$ROOT/desktop/public" "$ROOT/desktop/index.html" "$ROOT/desktop/vite.config.js" \
    -type f -newer "$DIST_INDEX" -print -quit 2>/dev/null | grep -q .; then
  NEEDS_BUILD=1
fi

if [[ "$NEEDS_BUILD" == "1" ]]; then
  if ! command -v npm >/dev/null 2>&1; then
    echo "Desktop source changed but npm is not available. Install Node/npm or run scripts/setup_macos.sh." >&2
    exit 2
  fi
  echo "MaryV2: rebuilding desktop frontend…"
  (cd "$ROOT/desktop" && npm run build)
fi

exec "$PYTHON" -m scripts.run_desktop
