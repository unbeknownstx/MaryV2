#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "============================================================"
echo "MARYV2 MACOS STANDALONE BUILD"
echo "============================================================"

PYTHON="$ROOT/.venv/bin/python"

if [[ ! -x "$PYTHON" ]]; then
  echo "MaryV2 .venv was not found. Create/activate the project environment first." >&2
  exit 1
fi

unset MARY_RUN_LIVE_TESTS || true
unset MARY_RUN_OPENAI_TESTS || true

echo "[1/6] Desktop frontend dependencies + build"
pushd desktop >/dev/null
npm ci
npm run build
popd >/dev/null

echo "[2/6] Deterministic release verification"
"$PYTHON" -m scripts.run_release_verification --offline

echo "[3/6] Build dependency"
"$PYTHON" -m pip install -r requirements-build.txt

echo "[4/6] PyInstaller application bundle"
"$PYTHON" -m PyInstaller --noconfirm --clean MaryV2.spec

APP="$ROOT/dist/MaryV2.app"

if [[ ! -d "$APP" ]]; then
  echo "Expected application bundle was not produced: $APP" >&2
  exit 1
fi

echo "[5/6] Local ad-hoc signing"

if command -v codesign >/dev/null 2>&1; then
  codesign --force --deep --sign - "$APP"
else
  echo "codesign not found; skipping local ad-hoc signing."
fi

echo "[6/6] Result"
echo "PASS  $APP"
echo "Mary's writable data defaults to ~/Library/Application Support/MaryV2/data when frozen."
echo "Set MARY_PORTABLE=1 to keep data in a data folder beside the executable."
echo "Packaged Mary reads .env from ~/Library/Application Support/MaryV2/.env by default."
echo "Set MARY_ENV_FILE to override that location."