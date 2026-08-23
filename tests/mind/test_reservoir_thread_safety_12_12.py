from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from mary.mind.reservoir import CognitiveReservoir, ReservoirRecord


def test_reservoir_can_be_read_from_desktop_worker_threads(tmp_path):
    reservoir = CognitiveReservoir(tmp_path / "reservoir.sqlite3")
    reservoir.upsert(
        ReservoirRecord(
            record_id="creator:favorite_color",
            kind="creator_preference",
            subject="creator",
            predicate="favorite_color",
            content="The creator's favorite color is blue.",
            source="test",
            authority="creator_explicit",
            confidence=1.0,
        )
    )

    def read_once(_):
        return reservoir.search("favorite color", limit=2)[0].content

    with ThreadPoolExecutor(max_workers=4) as pool:
        values = list(pool.map(read_once, range(12)))

    assert values == ["The creator's favorite color is blue."] * 12
    reservoir.close()
