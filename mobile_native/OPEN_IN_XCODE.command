#!/bin/bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
if ! command -v open >/dev/null 2>&1; then
  echo "This launcher is for macOS."
  exit 1
fi
open "$HERE/MaryMobile.xcodeproj"
echo "Opened MaryMobile.xcodeproj in Xcode. Choose your Personal Team, select your iPhone, then press Run."
