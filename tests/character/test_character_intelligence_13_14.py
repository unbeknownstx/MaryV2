from __future__ import annotations

from mary.character import CharacterSourcebook


def test_canonical_character_sourcebook_projects_typed_evidence(tmp_path) -> None:
    path = tmp_path / "mary_bible.md"
    path.write_text(
        "# Voice\n[DNA] Mary is direct, playful, and warm with people she trusts.\n\n"
        "# Anti Voice\n[NEG] Mary should not sound like a customer-service script.\n",
        encoding="utf-8",
    )
    book = CharacterSourcebook.from_paths([path])
    selection = book.select("How should Mary sound with someone she trusts?", limit=4)
    view = selection.prompt_view()
    structured = view["structured_evidence"]
    assert structured["semantics"]["projection_only"] is True
    assert structured["semantics"]["memory_owner"] is False
    assert structured["claims"]
    assert all(claim["claim_id"] for claim in structured["claims"])
    assert all(edge["subject"] for edge in structured["edges"])


def test_character_intelligence_does_not_reclassify_fiction_as_memory(tmp_path) -> None:
    path = tmp_path / "unbeknownst_canon.md"
    path.write_text("# Scene\n[FC] Mary grew up with Dave in the fictional story.\n", encoding="utf-8")
    book = CharacterSourcebook.from_paths([path])
    view = book.select("Does Mary remember Dave?", limit=3).prompt_view()
    claims = view["structured_evidence"]["claims"]
    assert claims
    assert claims[0]["authority_tier"] == "fictional_reference"
    assert claims[0]["boundary"] == "fictional_reference_not_ai_memory"


def test_intelligent_sourcebook_snapshot_preserves_authority_boundary() -> None:
    book = CharacterSourcebook.empty()
    snapshot = book.snapshot()
    assert snapshot["structured_character_intelligence"] is True
    assert snapshot["external_graph_required"] is False
    assert snapshot["semantics"]["ai_lived_memory_owner"] is False
