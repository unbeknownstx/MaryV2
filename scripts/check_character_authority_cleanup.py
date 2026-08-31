"""Check the post-cleanup CharacterSourcebook integration."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mary.character import CharacterSourcebook

book = CharacterSourcebook.from_environment(root=ROOT)
snap = book.snapshot()

assert snap["enabled"] is True
assert snap["records"] == 166
assert snap["sources"] == 5
assert snap["errors"] == []

assert not (ROOT / "runtime" / "character_authority.py").exists()
assert not (ROOT / "tests" / "test_character_authority.py").exists()
assert not (ROOT / "scripts" / "verify_character_sourcebook_retrieval_beta2.py").exists()

print("enabled:", snap["enabled"])
print("records:", snap["records"])
print("sources:", snap["sources"])
print("errors:", snap["errors"])
print("Character Authority cleanup verification: PASS")
