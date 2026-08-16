"""
Tests for MaryV2 Semantic Memory.
"""

from mary.memory.semantic import SemanticMemory


def test_semantic_memory_starts_empty():
    semantic = SemanticMemory()

    assert semantic.count() == 0
    assert semantic.all() == []


def test_semantic_memory_can_add_fact():
    semantic = SemanticMemory()

    memory = semantic.add(
        subject="creator",
        predicate="likes",
        value="anime",
    )

    assert memory["id"] == "semantic_1"
    assert memory["subject"] == "creator"
    assert memory["predicate"] == "likes"
    assert memory["value"] == "anime"
    assert memory["confidence"] == 1.0
    assert memory["source"] is None
    assert "created_at" in memory
    assert "updated_at" in memory

    assert semantic.count() == 1


def test_semantic_memory_prevents_exact_duplicates():
    semantic = SemanticMemory()

    first = semantic.add(
        subject="creator",
        predicate="likes",
        value="anime",
        confidence=0.5,
    )

    second = semantic.add(
        subject="creator",
        predicate="likes",
        value="anime",
        confidence=0.9,
    )

    assert semantic.count() == 1
    assert first["id"] == second["id"]
    assert second["confidence"] == 0.9


def test_semantic_memory_duplicate_updates_source():
    semantic = SemanticMemory()

    first = semantic.add(
        subject="creator",
        predicate="likes",
        value="anime",
        source="conversation",
    )

    second = semantic.add(
        subject="creator",
        predicate="likes",
        value="anime",
        source="user",
    )

    assert semantic.count() == 1
    assert first["id"] == second["id"]
    assert second["source"] == "user"


def test_semantic_memory_find():
    semantic = SemanticMemory()

    semantic.add(
        subject="creator",
        predicate="likes",
        value="anime",
    )

    semantic.add(
        subject="creator",
        predicate="dislikes",
        value="shrimp",
    )

    results = semantic.find(
        subject="creator",
        predicate="likes",
    )

    assert len(results) == 1
    assert results[0]["value"] == "anime"


def test_semantic_memory_find_is_case_insensitive():
    semantic = SemanticMemory()

    semantic.add(
        subject="Creator",
        predicate="Likes",
        value="anime",
    )

    results = semantic.find(
        subject="creator",
        predicate="likes",
    )

    assert len(results) == 1
    assert results[0]["value"] == "anime"


def test_semantic_memory_search_positive_preference():
    semantic = SemanticMemory()

    semantic.add(
        subject="creator",
        predicate="likes",
        value="anime",
    )

    semantic.add(
        subject="creator",
        predicate="dislikes",
        value="shrimp",
    )

    results = semantic.search(
        "what does the creator like?"
    )

    assert results
    assert results[0]["predicate"] == "likes"
    assert results[0]["value"] == "anime"
    assert results[0]["score"] > 0


def test_semantic_memory_search_negative_preference():
    semantic = SemanticMemory()

    semantic.add(
        subject="creator",
        predicate="likes",
        value="anime",
    )

    semantic.add(
        subject="creator",
        predicate="dislikes",
        value="shrimp",
    )

    results = semantic.search(
        "what don't I like?"
    )

    assert results
    assert results[0]["predicate"] == "dislikes"
    assert results[0]["value"] == "shrimp"


def test_semantic_memory_search_value():
    semantic = SemanticMemory()

    semantic.add(
        subject="creator",
        predicate="likes",
        value="anime",
    )

    results = semantic.search(
        "anime"
    )

    assert results
    assert results[0]["value"] == "anime"
    assert results[0]["score"] > 0


def test_semantic_memory_search_respects_limit():
    semantic = SemanticMemory()

    semantic.add(
        subject="creator",
        predicate="likes",
        value="anime",
    )

    semantic.add(
        subject="creator",
        predicate="likes",
        value="manga",
    )

    semantic.add(
        subject="creator",
        predicate="likes",
        value="games",
    )

    results = semantic.search(
        "what does the creator like?",
        limit=2,
    )

    assert len(results) <= 2


def test_semantic_memory_empty_search_returns_empty():
    semantic = SemanticMemory()

    semantic.add(
        subject="creator",
        predicate="likes",
        value="anime",
    )

    assert semantic.search("") == []
    assert semantic.search("   ") == []


def test_semantic_memory_zero_limit_returns_empty():
    semantic = SemanticMemory()

    semantic.add(
        subject="creator",
        predicate="likes",
        value="anime",
    )

    assert semantic.search(
        "anime",
        limit=0,
    ) == []


def test_semantic_memory_retrieve_aliases_search():
    semantic = SemanticMemory()

    semantic.add(
        subject="creator",
        predicate="likes",
        value="anime",
    )

    search_results = semantic.search(
        "anime"
    )

    retrieve_results = semantic.retrieve(
        "anime"
    )

    assert retrieve_results == search_results


def test_semantic_memory_get_by_id():
    semantic = SemanticMemory()

    memory = semantic.add(
        subject="mary",
        predicate="likes",
        value="music",
    )

    result = semantic.get(
        memory["id"]
    )

    assert result is memory


def test_semantic_memory_get_missing_id_returns_none():
    semantic = SemanticMemory()

    assert semantic.get(
        "semantic_999"
    ) is None


def test_semantic_memory_update():
    semantic = SemanticMemory()

    memory = semantic.add(
        subject="creator",
        predicate="likes",
        value="anime",
    )

    updated = semantic.update(
        memory["id"],
        value="manga",
        confidence=0.8,
    )

    assert updated is not None
    assert updated["value"] == "manga"
    assert updated["confidence"] == 0.8


def test_semantic_memory_update_ignores_unknown_fields():
    semantic = SemanticMemory()

    memory = semantic.add(
        subject="creator",
        predicate="likes",
        value="anime",
    )

    updated = semantic.update(
        memory["id"],
        invalid_field="should not exist",
    )

    assert updated is not None
    assert "invalid_field" not in updated


def test_semantic_memory_update_missing_id_returns_none():
    semantic = SemanticMemory()

    result = semantic.update(
        "semantic_999",
        value="anything",
    )

    assert result is None


def test_semantic_memory_remove():
    semantic = SemanticMemory()

    memory = semantic.add(
        subject="creator",
        predicate="likes",
        value="anime",
    )

    removed = semantic.remove(
        memory["id"]
    )

    assert removed is True
    assert semantic.count() == 0
    assert semantic.get(
        memory["id"]
    ) is None


def test_semantic_memory_remove_missing_id_returns_false():
    semantic = SemanticMemory()

    assert semantic.remove(
        "semantic_999"
    ) is False


def test_semantic_memory_clear():
    semantic = SemanticMemory()

    semantic.add(
        subject="creator",
        predicate="likes",
        value="anime",
    )

    semantic.add(
        subject="creator",
        predicate="dislikes",
        value="shrimp",
    )

    semantic.clear()

    assert semantic.count() == 0
    assert semantic.all() == []


def test_semantic_memory_all_returns_copy():
    semantic = SemanticMemory()

    semantic.add(
        subject="creator",
        predicate="likes",
        value="anime",
    )

    memories = semantic.all()

    memories.clear()

    assert semantic.count() == 1


def test_semantic_memory_confidence_is_clamped_high():
    semantic = SemanticMemory()

    memory = semantic.add(
        subject="mary",
        predicate="knows",
        value="something",
        confidence=10.0,
    )

    assert memory["confidence"] == 1.0


def test_semantic_memory_confidence_is_clamped_low():
    semantic = SemanticMemory()

    memory = semantic.add(
        subject="mary",
        predicate="knows",
        value="something",
        confidence=-10.0,
    )

    assert memory["confidence"] == 0.0


def test_semantic_memory_invalid_confidence_defaults_to_one():
    semantic = SemanticMemory()

    memory = semantic.add(
        subject="mary",
        predicate="knows",
        value="something",
        confidence="invalid",
    )

    assert memory["confidence"] == 1.0


def test_semantic_memory_rejects_empty_subject():
    semantic = SemanticMemory()

    try:
        semantic.add(
            subject="",
            predicate="likes",
            value="anime",
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Expected ValueError for empty subject."
        )


def test_semantic_memory_rejects_whitespace_subject():
    semantic = SemanticMemory()

    try:
        semantic.add(
            subject="   ",
            predicate="likes",
            value="anime",
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Expected ValueError for whitespace-only subject."
        )


def test_semantic_memory_rejects_empty_predicate():
    semantic = SemanticMemory()

    try:
        semantic.add(
            subject="creator",
            predicate="",
            value="anime",
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Expected ValueError for empty predicate."
        )


def test_semantic_memory_rejects_whitespace_predicate():
    semantic = SemanticMemory()

    try:
        semantic.add(
            subject="creator",
            predicate="   ",
            value="anime",
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Expected ValueError for whitespace-only predicate."
        )


def test_semantic_memory_generates_sequential_ids():
    semantic = SemanticMemory()

    first = semantic.add(
        subject="creator",
        predicate="likes",
        value="anime",
    )

    second = semantic.add(
        subject="creator",
        predicate="likes",
        value="manga",
    )

    third = semantic.add(
        subject="creator",
        predicate="likes",
        value="games",
    )

    assert first["id"] == "semantic_1"
    assert second["id"] == "semantic_2"
    assert third["id"] == "semantic_3"