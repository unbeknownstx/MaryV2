"""
MaryV2 - Memory Consolidation Tests

Tests the process of identifying important memories and
promoting them into semantic memory.
"""

from mary.memory.manager import MemoryManager


def test_important_episodic_memory_becomes_consolidation_candidate():
    memory = MemoryManager()

    episode = memory.remember_event(
        "Mary learned something important about her own memory.",
        importance=0.9,
        event_type="learning",
    )

    assert episode is not None

    candidates = memory.consolidation.consolidate()

    assert len(candidates) == 1

    candidate = candidates[0]

    assert candidate["type"] == "consolidation_candidate"
    assert candidate["content"] == (
        "Mary learned something important about her own memory."
    )


def test_unimportant_memory_is_not_consolidated():
    memory = MemoryManager()

    memory.remember_event(
        "Mary briefly checked something.",
        importance=0.2,
    )

    candidates = memory.consolidation.consolidate()

    assert candidates == []


def test_consolidation_candidate_contains_source_memory():
    memory = MemoryManager()

    episode = memory.remember_event(
        "Mary discovered an important fact.",
        importance=0.9,
    )

    candidates = memory.consolidation.consolidate()

    assert len(candidates) == 1

    candidate = candidates[0]

    assert candidate["source_memory_id"] == episode.id


def test_consolidation_count_matches_candidates():
    memory = MemoryManager()

    memory.remember_event(
        "Important memory one.",
        importance=0.9,
    )

    memory.remember_event(
        "Unimportant memory.",
        importance=0.2,
    )

    memory.remember_event(
        "Important memory two.",
        importance=0.8,
    )

    assert memory.consolidation.count_candidates() == 2