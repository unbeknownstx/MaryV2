from __future__ import annotations

from pathlib import Path

from mary.mind.reservoir import CognitiveReservoir, ReservoirRecord


def record(rid: str, *, subject="creator", predicate="favorite_color", content="The creator's favorite color is blue."):
    return ReservoirRecord(
        record_id=rid,
        kind="creator_fact",
        subject=subject,
        predicate=predicate,
        content=content,
        source="test_authoritative",
        authority="creator_explicit",
        confidence=1.0,
        metadata={"value": "blue"},
    )


def test_reservoir_rebuild_search_and_exact_are_local_and_rebuildable(tmp_path: Path):
    path = tmp_path / "reservoir" / "mary.sqlite3"
    reservoir = CognitiveReservoir(path)
    try:
        assert reservoir.rebuild([record("one")]) == 1
        hit = reservoir.exact(subject="creator", predicate="favorite_color")
        assert hit is not None
        assert hit.metadata["value"] == "blue"
        results = reservoir.search("favorite color", limit=5)
        assert results
        assert results[0].authority == "creator_explicit"
        status = reservoir.status()
        assert status["persistent"] is True
        assert status["records"] == 1
        assert status["max_megabytes"] >= 32
    finally:
        reservoir.close()


def test_reservoir_is_derived_and_rebuild_replaces_old_projection():
    reservoir = CognitiveReservoir.in_memory()
    try:
        reservoir.rebuild([record("old")])
        reservoir.rebuild([
            ReservoirRecord(
                record_id="new",
                kind="creator_fact",
                subject="creator",
                predicate="favorite_food",
                content="The creator's favorite food is tacos.",
                source="test_authoritative",
                authority="creator_explicit",
                metadata={"value": "tacos"},
            )
        ])
        assert reservoir.exact(subject="creator", predicate="favorite_color") is None
        assert reservoir.exact(subject="creator", predicate="favorite_food") is not None
    finally:
        reservoir.close()
