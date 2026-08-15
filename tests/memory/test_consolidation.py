"""
MaryV2 - Consolidation Tests

Verifies that episodic memories can be promoted into
semantic memories correctly and without duplication.
"""

from mary.memory.manager import MemoryManager


def test_preference_memories_promote_to_semantic():
    memory = MemoryManager()

    memory.remember(
        "I don't like shrimp",
        memory_type="episodic",
        importance=0.9,
    )

    memory.remember(
        "that I love anime",
        memory_type="episodic",
        importance=0.9,
    )

    assert memory.episodic.count() == 2
    assert memory.semantic.count() == 0

    promoted = memory.consolidate()

    assert promoted == 2
    assert memory.semantic.count() == 2

    semantic = memory.semantic.all()

    assert {
        (
            item["subject"],
            item["predicate"],
            item["value"],
        )
        for item in semantic
    } == {
        ("creator", "dislikes", "shrimp"),
        ("creator", "likes", "anime"),
    }


def test_consolidation_preserves_confidence():
    memory = MemoryManager()

    memory.remember(
        "I don't like shrimp",
        memory_type="episodic",
        importance=0.9,
    )

    memory.consolidate()

    semantic = memory.semantic.all()

    assert len(semantic) == 1
    assert semantic[0]["confidence"] == 0.9


def test_second_consolidation_does_not_duplicate():
    memory = MemoryManager()

    memory.remember(
        "I don't like shrimp",
        memory_type="episodic",
        importance=0.9,
    )

    memory.remember(
        "that I love anime",
        memory_type="episodic",
        importance=0.9,
    )

    first = memory.consolidate()

    assert first == 2
    assert memory.semantic.count() == 2

    second = memory.consolidate()

    assert second == 0
    assert memory.semantic.count() == 2


def test_consolidation_creates_structured_facts():
    memory = MemoryManager()

    memory.remember(
        "I don't like shrimp",
        memory_type="episodic",
        importance=0.9,
    )

    memory.consolidate()

    semantic = memory.semantic.all()

    fact = semantic[0]

    assert fact["subject"] == "creator"
    assert fact["predicate"] == "dislikes"
    assert fact["value"] == "shrimp"
    assert fact["source"] == "memory_consolidation"


def test_low_importance_memory_is_not_promoted():
    memory = MemoryManager()

    memory.remember(
        "I saw a bird today",
        memory_type="episodic",
        importance=0.1,
    )

    promoted = memory.consolidate()

    assert promoted == 0
    assert memory.semantic.count() == 0


def test_unrelated_memories_do_not_create_duplicate_facts():
    memory = MemoryManager()

    memory.remember(
        "I don't like shrimp",
        memory_type="episodic",
        importance=0.9,
    )

    memory.remember(
        "I don't like shrimp",
        memory_type="episodic",
        importance=0.9,
    )

    promoted = memory.consolidate()

    assert promoted == 1
    assert memory.semantic.count() == 1

    semantic = memory.semantic.all()

    assert semantic[0]["predicate"] == "dislikes"
    assert semantic[0]["value"] == "shrimp"