from mary.memory.temporal_projection import TemporalKnowledgeProjection


def test_new_value_supersedes_previous_current_fact():
    projection = TemporalKnowledgeProjection()
    first = projection.add(subject="creator", predicate="favorite_tool", value="GUI", source="relationship")
    second = projection.add(subject="creator", predicate="favorite_tool", value="CLI", source="relationship")

    current = projection.current(subject="creator", predicate="favorite_tool")
    assert len(current) == 1
    assert current[0]["value"] == "CLI"
    assert second.supersedes == first.fact_id
    assert first.status == "historical"
    assert first.valid_until is not None
    assert second.fact_id in first.contradicted_by


def test_repeated_same_value_strengthens_without_duplicate():
    projection = TemporalKnowledgeProjection()
    first = projection.add(subject="creator", predicate="likes", value="local-first", source="profile", confidence=0.6)
    second = projection.add(subject="creator", predicate="likes", value="local-first", source="profile", confidence=0.9)

    assert first.fact_id == second.fact_id
    assert len(projection.history(subject="creator", predicate="likes")) == 1
    assert second.confidence == 0.9


def test_projection_is_explicitly_non_authoritative():
    projection = TemporalKnowledgeProjection()
    projection.add(subject="creator", predicate="workflow", value="terminal", source="profile")
    snapshot = projection.snapshot()
    assert snapshot["authority"] == "derived_rebuildable_projection"


def test_rebuild_ignores_malformed_records():
    projection = TemporalKnowledgeProjection()
    projection.rebuild([
        {"subject": "creator", "predicate": "editor", "value": "VS Code", "source": "profile"},
        {"subject": "", "predicate": "broken", "value": "x", "source": "profile"},
        "invalid",
    ])
    assert projection.snapshot()["fact_count"] == 1
