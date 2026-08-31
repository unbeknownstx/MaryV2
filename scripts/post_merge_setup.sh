#!/usr/bin/env bash
set -euo pipefail

# Replit retains this project's installed environment across task merges.
# Validate merged Python sources without touching user state or prompting.
python -m compileall -q mary scripts