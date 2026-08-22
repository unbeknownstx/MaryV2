#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "============================================================"
echo "MARYV2 12.8 MACOS ECOSYSTEM BUILD"
echo "============================================================"

PYTHON="$ROOT/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  echo "MaryV2 .venv was not found. Create/activate the project environment first." >&2
  exit 1
fi

unset MARY_RUN_LIVE_TESTS || true
unset MARY_RUN_OPENAI_TESTS || true

echo "[1/9] Desktop + launcher frontend build"
pushd desktop >/dev/null
npm ci
npm run check
npm run build
popd >/dev/null

echo "[2/9] Final build preflight"
"$PYTHON" -m scripts.final_preflight --build-ready

echo "[3/9] Deterministic release verification"
"$PYTHON" -m scripts.run_release_verification --offline

echo "[4/9] Build dependency"
"$PYTHON" -m pip install -r requirements-build.txt

echo "[5/9] Build MaryV2"
"$PYTHON" -m PyInstaller --noconfirm --clean MaryV2.spec

echo "[6/9] Build Mary Launcher"
"$PYTHON" -m PyInstaller --noconfirm --clean MaryLauncher.spec

MARY_APP="$ROOT/dist/MaryV2.app"
LAUNCHER_APP="$ROOT/dist/MaryLauncher.app"
[[ -d "$MARY_APP" ]] || { echo "Missing $MARY_APP" >&2; exit 1; }
[[ -d "$LAUNCHER_APP" ]] || { echo "Missing $LAUNCHER_APP" >&2; exit 1; }

echo "[7/9] Local ad-hoc signing"
if command -v codesign >/dev/null 2>&1; then
  codesign --force --deep --sign - "$MARY_APP"
  codesign --force --deep --sign - "$LAUNCHER_APP"
else
  echo "codesign not found; skipping local ad-hoc signing."
fi

echo "[8/9] Verify state location"
echo "Mary data: ~/Library/Application Support/MaryV2/data"

echo "[9/9] Result"
echo "PASS  $LAUNCHER_APP"
echo "PASS  $MARY_APP"
echo "Packaged Mary reads private config from ~/Library/Application Support/MaryV2/.env by default."
