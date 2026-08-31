"""Focused post-install verifier for MaryV2 13.2 Experience Evolution."""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mary.character import CharacterSourcebook
from mary.experience import build_experience_snapshot

required = [
    ROOT / "mary" / "experience" / "projector.py",
    ROOT / "mobile_web" / "experience.js",
    ROOT / "mobile_web" / "experience.css",
    ROOT / "desktop" / "src" / "experience-v2.css",
    ROOT / "desktop" / "src" / "ui" / "experienceLayer.js",
    ROOT / "character_sources" / "active" / "mary_lived_world_beta.jsonl",
    ROOT / "character_sources" / "active" / "mary_interaction_policy_beta.jsonl",
]

missing = [str(p.relative_to(ROOT)) for p in required if not p.exists()]
assert not missing, f"missing Experience Evolution files: {missing}"

book = CharacterSourcebook.from_environment(root=ROOT)
snapshot = book.snapshot()
assert snapshot.get("enabled") is True, snapshot
assert int(snapshot.get("records", 0)) >= 189, snapshot
assert int(snapshot.get("sources", 0)) >= 7, snapshot
assert not snapshot.get("errors"), snapshot.get("errors")

sample = build_experience_snapshot(
    {
        "core": {"architecture": "13.2", "ok": True},
        "live": {"character": {"status": "thinking", "mood": "neutral", "memory_count": 12}},
        "relationship": {"label": "Established", "score": 68},
    },
    {"provider": "groq", "model": "openai/gpt-oss-20b", "lane": "social_instant"},
)
assert sample["identity_owner"] == "mary_core"
assert sample["authority"] == "presentation_projection_only"
assert sample["theme"]["name"] == "focused"
assert sample["provider"] == "groq"
assert sample["provider"] != sample["identity_owner"]

for name, expected in (("mary_lived_world_beta.jsonl", 18), ("mary_interaction_policy_beta.jsonl", 5)):
    path = ROOT / "character_sources" / "active" / name
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == expected, (name, len(rows), expected)

print("EXPERIENCE EVOLUTION PASS")
print("character_records:", snapshot.get("records"))
print("character_sources:", snapshot.get("sources"))
print("character_hash:", snapshot.get("sourcebook_hash"))
print("experience_authority:", sample["authority"])
print("identity_owner:", sample["identity_owner"])
