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

echo "============================================================"
echo "MARYV2 MACOS SETUP + VERIFICATION"
echo "============================================================"
echo "Root: $ROOT"

command -v python3 >/dev/null 2>&1 || { echo "python3 is required." >&2; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "Node.js/npm is required for the desktop UI." >&2; exit 1; }

step 1 "Python environment"
if [[ ! -x .venv/bin/python ]]; then python3 -m venv .venv; fi
PYTHON="$ROOT/.venv/bin/python"
"$PYTHON" - <<'PY'
import sys
if sys.version_info < (3, 10):
    raise SystemExit("Python 3.10+ is required.")
PY
echo "  PASS: virtual environment"

step 2 "Python dependencies"
"$PYTHON" -m pip install --upgrade pip
"$PYTHON" -m pip install -r requirements.txt
"$PYTHON" -m pip install -r requirements-desktop.txt
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
