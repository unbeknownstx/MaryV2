from mary.core.mary import Mary
from mary.runtime.root_authority import MaryRootAuthority


def test_root_authority_encodes_many_surfaces_one_mary_and_context_rule():
    root = MaryRootAuthority()
    snap = root.snapshot()
    assert snap["one_mary_principle"] == "many_surfaces_many_nodes_one_mary"
    assert snap["context_principle"] == "everything_addressable_not_everything_in_prompt"
    assert any(layer["name"] == "authored_character" for layer in snap["layers"])


def test_live_mary_root_authority_and_turnmind_are_connected(monkeypatch, tmp_path):
    source = tmp_path / "mary.md"
    source.write_text("[DNA] Mary does not confuse competence with formality.", encoding="utf-8")
    monkeypatch.setenv("MARY_CHARACTER_SOURCES", str(source))
    mary = Mary()
    assert mary.root_authority.validate(mary) == []
    assert mary.system_contract.validate(mary) == []
