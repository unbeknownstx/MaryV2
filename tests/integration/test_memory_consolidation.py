"""
MaryV2 - Memory Consolidation Integration Tests

Tests the complete path from experience to durable memory.
"""

from mary.memory.manager import MemoryManager


def test_important_memory_can_be_consolidated_and_promoted():
    memory = MemoryManager()

    memory.remember_event(
        "Unbe is Mary's creator.",
        importance=1.0,
        event_type="relationship",
    )

    candidates = memory.consolidation.consolidate()

    assert len(candidates) == 1

    promoted = memory.consolidation.promote(
        candidates[0]
    )

    assert promoted is True

    assert memory.semantic.count() == 1


def test_unimportant_memory_is_not_promoted():
    memory = MemoryManager()

    memory.remember_event(
        "Mary briefly noticed something.",
        importance=0.2,
    )

    candidates = memory.consolidation.consolidate()

    assert candidates == []

    assert memory.semantic.count() == 0


def test_consolidation_and_promotion_count():
    memory = MemoryManager()

    memory.remember_event(
        "Important memory one.",
        importance=0.9,
    )

    memory.remember_event(
        "Unimportant memory.",
        importance=0.1,
    )

    memory.remember_event(
        "Important memory two.",
        importance=0.8,
    )

    promoted = memory.consolidate()

    assert promoted == 2

    assert memory.semantic.count() == 2
