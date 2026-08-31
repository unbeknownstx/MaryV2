from __future__ import annotations

from pathlib import Path

from mary.character import CharacterSourcebook

ROOT = Path(__file__).resolve().parents[2]
ACTIVE = ROOT / "character_sources" / "active"


def _book() -> CharacterSourcebook:
    book = CharacterSourcebook.from_paths([ACTIVE])
    return book


def _headings(query: str) -> list[str]:
    return [
        record.heading
        for record in _book().select(
            query,
            limit=6,
            max_characters=4200,
        ).records
    ]


def test_food_theft_retrieves_food_theft_evidence():
    headings = _headings("someone steals food from Mary")
    assert any(h.startswith("EX-001") for h in headings)
    assert any(h.startswith("EX-002") for h in headings)


def test_real_anger_retrieves_quiet_anger_rule():
    headings = _headings("Mary is genuinely angry")
    assert headings
    assert headings[0].startswith("EMO-001")


def test_comfort_prefers_care_over_love_anger_collision():
    headings = _headings("Mary comforts someone she loves")
    assert headings
    assert not headings[0].startswith("REL-006")
    assert any(
        h.startswith("CARE-001")
        or h.startswith("CARE-004")
        or h.startswith("EX-024")
        for h in headings[:4]
    )


def test_dave_query_preserves_fictional_ai_memory_boundary():
    headings = _headings("does AI Mary remember growing up with Dave")
    assert any(h.startswith("ID-003") for h in headings)
    assert any("fake fictional autobiography" in h.lower() for h in headings)


def test_bucko_retrieves_rule_and_negative_guard():
    headings = _headings("Mary keeps saying bucko")
    assert any(h.startswith("HUM-007") for h in headings)
    assert any("catchphrase stuffing" in h.lower() for h in headings)


def test_flustered_query_does_not_lead_with_liking_an_idea():
    headings = _headings("Mary likes someone and gets flustered")
    assert headings
    assert not headings[0].startswith("EX-026")
    assert any(
        h.startswith("REL-004")
        or h.startswith("EX-034")
        or h.startswith("EX-017")
        for h in headings[:4]
    )


def test_selection_is_bounded():
    selection = _book().select(
        "Mary keeps saying bucko",
        limit=6,
        max_characters=4200,
    )
    assert 1 <= len(selection.records) <= 6
    prompt_chars = sum(
        len(record.text) + len(record.heading) + 80
        for record in selection.records
    )
    assert prompt_chars <= 4200

