from __future__ import annotations

import json
from pathlib import Path

from mary.character import CharacterSourcebook


ROOT = Path(__file__).resolve().parents[2]
ACTIVE = ROOT / "character_sources" / "active"


def _rows(name: str) -> list[dict]:
    return [
        json.loads(line)
        for line in (ACTIVE / name).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_lived_world_beta_is_authored_only_and_bounded():
    rows = _rows("mary_lived_world_beta.jsonl")
    assert len(rows) == 18
    forbidden = ("you can add whatever", "make something up", "idk fill", "you can fill these in")
    joined = "\n".join(row["text"].lower() for row in rows)
    assert not any(token in joined for token in forbidden)
    assert all("DNA" in row["labels"] for row in rows)


def test_interaction_policy_beta_preserves_identity_boundary():
    rows = _rows("mary_interaction_policy_beta.jsonl")
    assert len(rows) == 5
    joined = "\n".join(row["text"].lower() for row in rows)
    assert "shared-history reconstruction" in joined
    assert "mind-reading" in " ".join(row["heading"].lower() for row in rows)
    assert "frontend animation" in joined


def test_full_sourcebook_accepts_beta_sources_without_errors():
    book = CharacterSourcebook.from_environment(root=ROOT)
    snap = book.snapshot()
    assert snap["enabled"] is True
    assert snap["records"] >= 189
    assert snap["sources"] >= 7
    assert snap["errors"] == []
    assert "mary_lived_world_beta.jsonl" in snap["source_names"]
    assert "mary_interaction_policy_beta.jsonl" in snap["source_names"]
