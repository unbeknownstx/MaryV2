"""Repo-root-safe CharacterSourcebook checker."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mary.character import CharacterSourcebook

book = CharacterSourcebook.from_environment(root=ROOT)
snap = book.snapshot()

print("enabled:", snap.get("enabled"))
print("records:", snap.get("records"))
print("sources:", snap.get("sources"))
print("source_names:", snap.get("source_names"))
print("kinds:", snap.get("kinds"))
print("labels:", snap.get("labels"))
print("errors:", snap.get("errors"))
print("hash:", snap.get("sourcebook_hash"))
