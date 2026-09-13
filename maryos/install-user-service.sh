#!/usr/bin/env bash
set -eu

if [ "$(uname -s)" != "Linux" ]; then
  echo "MaryOS user-service installation is Linux-only."
  exit 2
fi

repo_root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
python_bin="$repo_root/.venv/bin/python"
template="$repo_root/maryos/systemd/mary-home-node.service.template"
unit_dir="$HOME/.config/systemd/user"
unit_path="$unit_dir/mary-home-node.service"
env_dir="$HOME/.config/maryv2"
env_path="$env_dir/node.env"

if [ ! -x "$python_bin" ]; then
  echo "Missing MaryV2 virtualenv Python: $python_bin"
  exit 2
fi
if ! command -v systemctl >/dev/null 2>&1; then
  echo "systemctl is unavailable; MaryOS 13.36 expects a systemd Linux host."
  exit 2
fi

mkdir -p "$unit_dir" "$env_dir"
"$python_bin" - "$template" "$unit_path" "$repo_root" "$python_bin" <<'PY'
from pathlib import Path
import sys
template, output, repo, python_bin = map(Path, sys.argv[1:5])
text = template.read_text(encoding="utf-8")
text = text.replace("@REPO@", str(repo)).replace("@PYTHON@", str(python_bin))
output.write_text(text, encoding="utf-8")
PY

if [ ! -e "$env_path" ]; then
  cat > "$env_path" <<'EOF'
# MaryOS local host configuration. Keep secrets out of Git.
# MARY_CORE_URL=https://your-mary-core.example
# MARY_NODE_ID=mary-linux-node
EOF
  chmod 600 "$env_path"
fi

systemctl --user daemon-reload
echo "Installed: $unit_path"
echo "Configure: $env_path"

if [ "${1:-}" = "--enable" ]; then
  systemctl --user enable --now mary-home-node.service
  echo "Enabled and started mary-home-node.service"
else
  echo "Not enabled automatically."
  echo "After interactive validation: $0 --enable"
fi
