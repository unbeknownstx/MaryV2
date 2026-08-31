"""Remove obsolete pre-CharacterSourcebook Alpha integration leftovers."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

obsolete_files = (
    ROOT / "runtime" / "character_authority.py",
    ROOT / "tests" / "test_character_authority.py",
    ROOT / "scripts" / "check_mary_character_authority.py",
)

renames = (
    (
        ROOT / "scripts" / "verify_character_sourcebook_retrieval_beta2.py",
        ROOT / "scripts" / "check_character_sourcebook_retrieval_beta2.py",
    ),
)

print("=== Mary Character Authority cleanup ===")

for src, dst in renames:
    if src.exists():
        if dst.exists():
            src.unlink()
            print("Removed duplicate temporary verifier:", src.relative_to(ROOT))
        else:
            src.replace(dst)
            print("Renamed temporary verifier:", src.relative_to(ROOT), "->", dst.relative_to(ROOT))
    elif dst.exists():
        print("Verifier already renamed:", dst.relative_to(ROOT))
    else:
        print("Temporary verifier not present; nothing to rename.")

for path in obsolete_files:
    if not path.exists():
        print("Already absent:", path.relative_to(ROOT))
        continue

    text = path.read_text(encoding="utf-8", errors="ignore")
    if path.name == "character_authority.py" and "MaryCharacterAuthority" not in text:
        raise SystemExit(f"Refusing to delete unexpected file: {path}")
    if path.name == "test_character_authority.py" and "MaryCharacterAuthority" not in text:
        raise SystemExit(f"Refusing to delete unexpected test: {path}")

    path.unlink()
    print("Removed obsolete Alpha file:", path.relative_to(ROOT))

for cache_root, prefix in (
    (ROOT / "runtime" / "__pycache__", "character_authority."),
    (ROOT / "tests" / "__pycache__", "test_character_authority."),
):
    if cache_root.exists():
        for item in cache_root.iterdir():
            if item.is_file() and item.name.startswith(prefix):
                item.unlink()
                print("Removed generated cache:", item.relative_to(ROOT))
        try:
            cache_root.rmdir()
        except OSError:
            pass

runtime_dir = ROOT / "runtime"
if runtime_dir.exists():
    try:
        runtime_dir.rmdir()
        print("Removed now-empty obsolete runtime/ directory.")
    except OSError:
        print("runtime/ contains other files; preserved directory.")

print("Cleanup complete.")
