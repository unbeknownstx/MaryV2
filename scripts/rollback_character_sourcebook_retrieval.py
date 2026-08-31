"""Rollback Mary CharacterSourcebook retrieval tuning Alpha."""
from pathlib import Path
import py_compile
import shutil
import tempfile

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "mary" / "character" / "sourcebook.py"
BACKUP = (
    Path(tempfile.gettempdir())
    / "MaryV2_patch_backups"
    / "sourcebook.py.pre_character_retrieval_alpha"
)

if not BACKUP.exists():
    raise SystemExit(f"Backup not found: {BACKUP}")

shutil.copy2(BACKUP, TARGET)
py_compile.compile(str(TARGET), doraise=True)
print("Restored original CharacterSourcebook.select().")
print("Compile check: PASS")
