from __future__ import annotations

from mary.agency.curiosity import CuriositySystem


def test_active_duplicate_curiosity_reuses_existing_record(tmp_path):
    store = CuriositySystem(path=tmp_path / "curiosities.json")
    store.load()

    first = store.add_curiosity(
        "Learn more about Unbe",
        importance=0.7,
        source="conversation",
    )
    second = store.add_curiosity(
        "  learn   more ABOUT unbe  ",
        importance=1.0,
        source="test",
    )

    assert first is second
    assert len(store.get_curiosities()) == 1
    assert first["importance"] == 1.0
    assert first["source"] == "conversation"


def test_resolved_curiosity_allows_later_new_active_cycle(tmp_path):
    store = CuriositySystem(path=tmp_path / "curiosities.json")
    store.load()
    first = store.add_curiosity("Explore a new topic", source="conversation")
    assert first is not None
    assert store.resolve_curiosity(first["id"]) is True

    second = store.add_curiosity("Explore a new topic", source="reflection")

    assert second is not None
    assert second["id"] != first["id"]
    assert len(store.get_curiosities()) == 2
