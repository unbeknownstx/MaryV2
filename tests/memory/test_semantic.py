"""
Tests for MaryV2 Semantic Memory.
"""

from mary.memory.semantic import SemanticMemory


def test_semantic_memory_can_be_created():
    memory = SemanticMemory(
        content="The sky is blue.",
    )

    assert memory.content == "The sky is blue."
    assert memory.id.startswith("semantic_")
    assert memory.source == "learned"
    assert memory.importance == 0.5
    assert memory.metadata == {}


def test_semantic_memory_accepts_custom_values():
    memory = SemanticMemory(
        content="Unbe is Mary's creator.",
        importance=0.9,
        source="conversation",
        metadata={
            "category": "relationship",
        },
    )

    assert memory.content == "Unbe is Mary's creator."
    assert memory.importance == 0.9
    assert memory.source == "conversation"
    assert memory.metadata["category"] == "relationship"


def test_semantic_memory_ids_are_unique():
    memory_one = SemanticMemory(
        content="First fact.",
    )

    memory_two = SemanticMemory(
        content="Second fact.",
    )

    assert memory_one.id != memory_two.id


def test_semantic_memory_has_timestamp():
    memory = SemanticMemory(
        content="Mary has semantic memory.",
    )

    assert memory.timestamp is not None


def test_semantic_memory_metadata_is_not_shared():
    memory_one = SemanticMemory(
        content="First fact.",
    )

    memory_two = SemanticMemory(
        content="Second fact.",
    )

    memory_one.metadata["test"] = True

    assert "test" not in memory_two.metadata