"""Install narrow Beta2 memory-boundary retrieval hotfix."""
from __future__ import annotations

from pathlib import Path
import py_compile
import shutil
import tempfile

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "mary" / "character" / "sourcebook.py"
BETA_MARKER = "# CHARACTER_RETRIEVAL_BETA_2026_08_31"
HOTFIX_MARKER = "# CHARACTER_RETRIEVAL_BETA2_MEMORY_BOUNDARY_2026_08_31"
BACKUP_DIR = Path(tempfile.gettempdir()) / "MaryV2_patch_backups"
BACKUP = BACKUP_DIR / "sourcebook.py.pre_character_retrieval_beta2"

if not TARGET.exists():
    raise SystemExit(f"Missing target: {TARGET}")

text = TARGET.read_text(encoding="utf-8")

if HOTFIX_MARKER in text:
    print("Beta2 memory-boundary hotfix already installed.")
    raise SystemExit(0)

if BETA_MARKER not in text:
    raise SystemExit("Retrieval Beta is not installed; no change made.")

needle = '            if memory_boundary_context:\n                boundary_evidence = body_tokens.intersection(\n'
replacement = '            if memory_boundary_context:\n                # CHARACTER_RETRIEVAL_BETA2_MEMORY_BOUNDARY_2026_08_31\n                # Memory/autobiography boundary queries need explicit AI, FC,\n                # or NEG evidence. Generic DNA-only Dave adjacency is noise.\n                if not (\n                    record.is_ai_mary\n                    or record.is_fictional_canon\n                    or record.is_negative_example\n                ):\n                    continue\n\n                boundary_evidence = body_tokens.intersection(\n'

if needle not in text:
    raise SystemExit("Expected Beta block not found; no change made.")

BACKUP_DIR.mkdir(parents=True, exist_ok=True)
shutil.copy2(TARGET, BACKUP)

TARGET.write_text(text.replace(needle, replacement, 1), encoding="utf-8")

try:
    py_compile.compile(str(TARGET), doraise=True)
except Exception:
    shutil.copy2(BACKUP, TARGET)
    raise

print("Installed Beta2 memory-boundary hotfix.")
print("Target:", TARGET)
print("Backup:", BACKUP)
print("Compile check: PASS")
