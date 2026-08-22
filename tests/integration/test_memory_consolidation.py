"""Integration tests for selective semantic-memory consolidation."""

from mary.memory.manager import MemoryManager


def test_relationship_history_is_candidate_but_not_promoted_to_semantic():
    memory = MemoryManager()

    memory.remember_event(
        "Unbe is Mary's creator.",
        importance=1.0,
        event_type="relationship",
    )

    candidates = memory.consolidation.consolidate()
    assert len(candidates) == 1

    review = memory.consolidation.review_candidate(candidates[0])
    assert review["promotable"] is False
    assert review["classification"] == "relationship_owned"
    assert memory.consolidation.promote(candidates[0]) is False
    assert memory.semantic.count() == 0


def test_unimportant_memory_is_not_a_candidate():
    memory = MemoryManager()

    memory.remember_event(
        "Mary briefly noticed something.",
        importance=0.2,
    )

    assert memory.consolidation.consolidate() == []
    assert memory.semantic.count() == 0


def test_generic_high_importance_events_require_review_instead_of_becoming_truth():
    memory = MemoryManager()

    memory.remember_event("Important memory one.", importance=0.9)
    memory.remember_event("Unimportant memory.", importance=0.1)
    memory.remember_event("Important memory two.", importance=0.8)

    candidates = memory.consolidation_candidates()
    assert len(candidates) == 2
    assert all(item["review"]["classification"] == "review_required" for item in candidates)

    promoted = memory.consolidate()
    assert promoted == 0
    assert memory.semantic.count() == 0


def test_explicit_semantic_structure_can_promote_from_nested_episode_metadata():
    memory = MemoryManager()

    memory.remember_event(
        "The creator's favorite color is blue.",
        importance=0.9,
        metadata={
            "subject": "creator",
            "predicate": "favorite_color",
            "value": "blue",
            "confidence": 1.0,
            "owner": "creator",
        },
    )

    candidates = memory.consolidation_candidates()
    assert len(candidates) == 1
    assert candidates[0]["review"]["classification"] == "explicit_semantic"

    assert memory.consolidate() == 1
    assert memory.semantic.count() == 1
    fact = memory.semantic.all()[0]
    assert (fact["subject"], fact["predicate"], fact["value"]) == (
        "creator",
        "favorite_color",
        "blue",
    )


def test_obvious_test_probe_is_never_promoted_even_when_important():
    memory = MemoryManager()
    memory.remember_event(
        "the persistence probe phrase is cobalt lantern",
        importance=1.0,
        source="verify_memory_restart",
    )

    candidates = memory.consolidation_candidates()
    assert len(candidates) == 1
    assert candidates[0]["review"]["classification"] == "blocked_test_probe"
    assert memory.consolidate() == 0
    assert memory.semantic.count() == 0


def test_legacy_unstructured_promotion_remains_explicitly_available():
    memory = MemoryManager()
    memory.remember_event("Imported legacy note.", importance=0.9)
    candidate = memory.consolidation.consolidate()[0]

    assert memory.consolidation.promote(candidate) is False
    assert memory.consolidation.promote(candidate, allow_unstructured=True) is True
    assert memory.semantic.count() == 1
