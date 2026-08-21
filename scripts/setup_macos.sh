#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

command -v python3 >/dev/null 2>&1 || {
  echo "python3 is required." >&2
  exit 1
}

command -v npm >/dev/null 2>&1 || {
  echo "Node.js/npm is required for the desktop UI." >&2
  exit 1
}

if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
fi

PYTHON="$ROOT/.venv/bin/python"

"$PYTHON" -m pip install --upgrade pip
"$PYTHON" -m pip install -r requirements.txt
"$PYTHON" -m pip install -r requirements-desktop.txt

if [[ ! -f .env && -f .env.example ]]; then
  cp .env.example .env
  echo "Created .env from .env.example. Add only the provider keys you actually use."
else
  echo "Existing .env preserved."
fi

pushd desktop >/dev/null
npm ci
npm run build
popd >/dev/null

"$PYTHON" -m scripts.run_release_verification --offline

echo "Setup complete. Launch Mary with:"
echo "  .venv/bin/python -m scripts.run_desktop"