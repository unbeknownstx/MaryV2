#!/usr/bin/env bash
set -euo pipefail

LABEL="com.unbeknownstx.maryv2.home-node"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

if [[ -f "$PLIST" ]]; then
  /usr/bin/launchctl bootout "gui/$UID" "$PLIST" >/dev/null 2>&1 || true
  rm -f -- "$PLIST"
  echo "Removed MaryV2 macOS LaunchAgent: $LABEL"
else
  /usr/bin/launchctl bootout "gui/$UID/$LABEL" >/dev/null 2>&1 || true
  echo "No MaryV2 macOS home-node LaunchAgent is installed."
fi
