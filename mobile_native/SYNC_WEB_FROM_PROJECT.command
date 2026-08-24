#!/bin/bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
rm -rf "$HERE/MaryMobile/www"
mkdir -p "$HERE/MaryMobile/www"
cp -a "$ROOT/mobile_web/." "$HERE/MaryMobile/www/"
echo "Mary mobile web bundle synced into the native Xcode project."
