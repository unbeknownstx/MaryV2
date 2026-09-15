#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LAUNCHER="$ROOT/scripts/launch_home_node_macos.sh"
PYTHON="$ROOT/.venv/bin/python"
LABEL="com.unbeknownstx.maryv2.home-node"
AGENT_DIR="$HOME/Library/LaunchAgents"
PLIST="$AGENT_DIR/$LABEL.plist"
LOG_DIR="$HOME/Library/Logs/MaryV2"

if [[ ! -x "$PYTHON" ]]; then
  echo "MaryV2 .venv was not found. Run scripts/setup_macos.sh first." >&2
  exit 1
fi
if [[ ! -x "$LAUNCHER" ]]; then
  echo "MaryV2 macOS home-node launcher was not found or is not executable: $LAUNCHER" >&2
  exit 1
fi

mkdir -p "$AGENT_DIR" "$LOG_DIR"

"$PYTHON" - "$PLIST" "$LABEL" "$LAUNCHER" "$LOG_DIR" <<'PY'
from pathlib import Path
import plistlib
import sys

plist = Path(sys.argv[1])
label = sys.argv[2]
launcher = str(Path(sys.argv[3]).resolve())
log_dir = Path(sys.argv[4]).resolve()

payload = {
    "Label": label,
    "ProgramArguments": ["/bin/bash", launcher],
    "RunAtLoad": True,
    "KeepAlive": False,
    "ProcessType": "Background",
    "StandardOutPath": str(log_dir / "home-node.out.log"),
    "StandardErrorPath": str(log_dir / "home-node.err.log"),
}
with plist.open("wb") as handle:
    plistlib.dump(payload, handle, sort_keys=True)
PY

chmod 600 "$PLIST"
/usr/bin/plutil -lint "$PLIST" >/dev/null

/usr/bin/launchctl bootout "gui/$UID" "$PLIST" >/dev/null 2>&1 || true
/usr/bin/launchctl bootstrap "gui/$UID" "$PLIST"

echo "Installed MaryV2 macOS LaunchAgent: $LABEL"
echo "It will start the canonical home capability node for this user at login."
echo "Run it now with:"
echo "  launchctl kickstart -k gui/$UID/$LABEL"
