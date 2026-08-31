from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))

from character_authority import MaryCharacterAuthority

def test_json_files_load():
    data = ROOT / "data"
    for name in (
        "mary_character_authority_alpha.json",
        "mary_relationship_ladder_alpha.json",
        "mary_anti_patterns_alpha.json",
        "mary_voice_bridge_alpha.json",
    ):
        json.loads((data / name).read_text(encoding="utf-8"))

def test_jsonl_files_load():
    data = ROOT / "data"
    for name in ("mary_behavior_corpus_alpha.jsonl", "mary_eval_suite_alpha.jsonl"):
        lines = [line for line in (data / name).read_text(encoding="utf-8").splitlines() if line.strip()]
        assert lines
        for line in lines:
            json.loads(line)

def test_core_identity_rules_always_selected():
    authority = MaryCharacterAuthority(ROOT)
    selection = authority.select("hey")
    ids = {item["id"] for item in selection.core_rules}
    assert "ID-002" in ids
    assert "ID-003" in ids
    assert "HUM-007" in ids

def test_identity_query_retrieves_identity_context():
    authority = MaryCharacterAuthority(ROOT)
    selection = authority.select("Do you remember growing up with Dave?")
    categories = {item["category"] for item in selection.contextual_rules}
    assert "identity" in categories

def test_relationship_lens_is_bounded():
    authority = MaryCharacterAuthority(ROOT)
    selection = authority.select("you stole my fries", relationship_stage="close_friend")
    assert selection.relationship is not None
    assert selection.relationship["id"] == "close_friend"
    assert len(selection.contextual_rules) <= 10
    assert len(selection.exemplars) <= 3
