from pathlib import Path

from mary.character import CharacterSourcebook

ROOT = Path(__file__).resolve().parents[2]
ACTIVE = ROOT / "character_sources" / "active"


def _book():
    book = CharacterSourcebook.from_paths([ACTIVE])
    assert book.snapshot()["records"] == 166
    return book


def _headings(query):
    return [r.heading for r in _book().select(query, limit=6).records]


def test_food_theft_first_offense_leads():
    headings = _headings("someone steals food from Mary")
    assert headings[0].startswith("EX-001")
    assert any(h.startswith("EX-002") for h in headings)


def test_real_anger_is_precise():
    headings = _headings("Mary is genuinely angry")
    assert headings == [next(h for h in headings if h.startswith("EMO-001"))]


def test_comfort_stays_in_care_domain():
    headings = _headings("Mary comforts someone she loves")
    assert headings
    assert headings[0].startswith("CARE-001")
    assert "EX-006 — Outclassed by an expert" not in headings
    assert "REL-006 — Relationship" not in headings
    assert any(h.startswith("CARE-004") for h in headings)


def test_dave_memory_boundary_has_core_four():
    headings = _headings("does AI Mary remember growing up with Dave")
    assert any(h.startswith("ID-003") for h in headings)
    assert any("fake fictional autobiography" in h.lower() for h in headings)
    assert any("AI relationship growth boundary" in h for h in headings)
    assert any("Fictional relationship lens — Dave" in h for h in headings)
    assert not any(h.startswith("HUM-002") for h in headings)


def test_bucko_stays_guarded():
    headings = _headings("Mary keeps saying bucko")
    assert any(h.startswith("HUM-007") for h in headings)
    assert any("catchphrase stuffing" in h.lower() for h in headings)


def test_flustered_stays_attraction_specific():
    headings = _headings("Mary likes someone and gets flustered")
    assert headings[0].startswith("EX-034")
    assert not any(h.startswith("EX-026") for h in headings)
    assert any(h.startswith("REL-004") for h in headings)
