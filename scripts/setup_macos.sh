#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

SKIP_FULL_SUITE=0
SKIP_RELEASE_GATE=0
for arg in "$@"; do
  case "$arg" in
    --skip-full-suite) SKIP_FULL_SUITE=1 ;;
    --skip-release-gate) SKIP_RELEASE_GATE=1 ;;
    *) echo "Unknown setup option: $arg" >&2; exit 2 ;;
  esac
done

step() { printf '[%s/10] %s\n' "$1" "$2"; }

run_isolated_python_stage() {
  local stage="$1"; shift
  local safe_stage
  safe_stage="$(printf '%s' "$stage" | tr -c 'A-Za-z0-9_-' '-')"
  local isolation
  isolation="$(mktemp -d "${TMPDIR:-/tmp}/maryv2-setup-$safe_stage-XXXXXX")"
  mkdir -p "$isolation/state" "$isolation/pytest"
  local rc=0
  env MARY_DATA_DIR="$isolation/state" \
      MARY_ENV_FILE="$isolation/no-live-config" \
      MARY_RESERVOIR_STORAGE="memory" \
      PYTEST_DEBUG_TEMPROOT="$isolation/pytest" \
      PYTEST_ADDOPTS="-p no:cacheprovider" \
      "$PYTHON" "$@" || rc=$?
  rm -rf -- "$isolation"
  return "$rc"
}

python_is_macos_desktop_compatible() {
  "$1" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if (3, 10) <= sys.version_info[:2] < (3, 14) else 1)
PY
}

select_bootstrap_python() {
  local candidate
  for candidate in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" >/dev/null 2>&1 && python_is_macos_desktop_compatible "$candidate"; then
      command -v "$candidate"
      return 0
    fi
  done
  return 1
}

echo "============================================================"
echo "MARYV2 MACOS SETUP + VERIFICATION"
echo "============================================================"
echo "Root: $ROOT"

command -v sw_vers >/dev/null 2>&1 || { echo "This setup script requires macOS." >&2; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "Node.js/npm is required for the desktop UI." >&2; exit 1; }
command -v node >/dev/null 2>&1 || { echo "Node.js is required for the desktop UI." >&2; exit 1; }

MACOS_VERSION="$(sw_vers -productVersion)"
BOOTSTRAP_PYTHON="$(select_bootstrap_python || true)"
if [[ -z "$BOOTSTRAP_PYTHON" ]]; then
  cat >&2 <<'EOF'
Mary Desktop on macOS requires Python 3.10 through 3.13.
The physical Monterey-compatible Qt/PySide build does not support Python 3.14.
Install Python 3.13 (recommended), then rerun this script.
EOF
  exit 1
fi

NODE_VERSION="$(node -p 'process.versions.node')"
"$BOOTSTRAP_PYTHON" - "$MACOS_VERSION" "$NODE_VERSION" <<'PY'
import sys

mac = tuple(int(part) for part in sys.argv[1].split(".")[:2])
node = tuple(int(part) for part in sys.argv[2].split(".")[:3])

vite_ok = (node[0] == 20 and node >= (20, 19, 0)) or (node[0] >= 22 and node >= (22, 12, 0))
if not vite_ok:
    raise SystemExit(
        f"Node {sys.argv[2]} is too old for the MaryV2 Vite 8 desktop. "
        "Use Node 22.12+ (Node 22 LTS is recommended)."
    )
if mac < (13, 5) and node[0] >= 24:
    raise SystemExit(
        f"Node {sys.argv[2]} is not the supported binary line for macOS {sys.argv[1]}. "
        "Use Node 22 LTS on Monterey/Ventura-era Macs."
    )
PY

echo "Host: macOS $MACOS_VERSION"
echo "Bootstrap Python: $($BOOTSTRAP_PYTHON -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')"
echo "Node: $NODE_VERSION"

step 1 "Python environment"
if [[ ! -x .venv/bin/python ]]; then
  "$BOOTSTRAP_PYTHON" -m venv .venv
fi
PYTHON="$ROOT/.venv/bin/python"
if ! python_is_macos_desktop_compatible "$PYTHON"; then
  cat >&2 <<EOF
Existing $ROOT/.venv is not compatible with the Monterey-capable Mary Desktop runtime.
It must use Python 3.10 through 3.13. The selected host interpreter is:
  $BOOTSTRAP_PYTHON
Rename or remove .venv, then rerun scripts/setup_macos.sh so it can be recreated safely.
EOF
  exit 2
fi
"$PYTHON" - <<'PY'
import sys
print("  Python:", sys.version.split()[0])
PY
echo "  PASS: virtual environment"

step 2 "Python dependencies"
"$PYTHON" -m pip install --upgrade pip
"$PYTHON" -m pip install -r requirements.txt
"$PYTHON" -m pip install -r requirements-desktop.txt
"$PYTHON" - <<'PY'
import PySide6
from PySide6 import QtCore, QtGui, QtWidgets
print(f"  Qt/PySide: {PySide6.__version__}")
assert QtCore and QtGui and QtWidgets
PY
echo "  PASS: Python dependencies"

step 3 "Private environment template"
if [[ ! -f .env && -f .env.example ]]; then
  cp .env.example .env
  echo "  Created .env from .env.example; add only the provider keys you actually use."
else
  echo "  Existing .env preserved."
fi

step 4 "Frontend install / syntax / production build"
(cd desktop && npm ci && npm run check && npm run build)
echo "  PASS: frontend production build"

step 5 "Repository structure / one-Mary convergence"
run_isolated_python_stage "step-5-structure" -m scripts.verify_repository_structure
run_isolated_python_stage "step-5-convergence" -m scripts.verify_maryv2_convergence

step 6 "Character / conversation regressions"
run_isolated_python_stage "step-6-character-runtime" -m scripts.verify_character_runtime_12_12
run_isolated_python_stage "step-6-natural-conversation" -m scripts.verify_natural_conversation_12_12_2

step 7 "Full deterministic suite"
if [[ "$SKIP_FULL_SUITE" == "0" ]]; then
  run_isolated_python_stage "step-7-full-suite" -m pytest -q
else
  echo "  SKIPPED by request"
fi

step 8 "Deterministic/offline release gate"
if [[ "$SKIP_RELEASE_GATE" == "0" ]]; then
  run_isolated_python_stage "step-8-release-gate" -m scripts.run_release_verification --offline
else
  echo "  SKIPPED by request"
fi

step 9 "Standalone/build readiness"
run_isolated_python_stage "step-9-standalone" -m scripts.verify_standalone_readiness

step 10 "Local capability node status"
echo "  Canonical home node launcher: scripts/launch_home_node_macos.sh"
echo "  Optional logon agent: scripts/install_macos_node_agent.sh"
echo "  Readiness: .venv/bin/python -m scripts.platform_readiness --strict"

echo "MARYV2 READY"
echo "Terminal: .venv/bin/python -m scripts.run_mary"
echo "Desktop:  bash scripts/launch_macos.sh"
echo "Home node: bash scripts/launch_home_node_macos.sh"
