from __future__ import annotations

from mary.cognition.intent import Intent, IntentType
from mary.core.mary import Mary
from mary.runtime.application import create_application, format_memory_status


def _conversation_intent() -> Intent:
    return Intent(
        intent_type=IntentType.CONVERSATION,
        confidence=1.0,
        source="test",
    )


def test_shared_work_question_routes_to_durable_relationship_recall(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()

    prompts = (
        "what do you remember about what we've been working on together?",
        "remind me what we've actually been building together lately",
    )

    for prompt in prompts:
        intent = mary.cognition.detect_intent(prompt)
        assert intent.intent_type == IntentType.RELATIONSHIP_QUERY
        assert intent.parameters["relationship_query_type"] == "shared_work"


def test_macbook_mixed_turn_becomes_grounded_shared_work_history(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()

    learned = mary._learn_shared_work_statement(
        "hey Mary, we're running on my MacBook for the first time. what do you think?",
        intent=_conversation_intent(),
    )

    assert learned is not None
    assert learned["recorded"] is True

    second = mary._learn_shared_work_statement(
        "We've spent all day building you.",
        intent=_conversation_intent(),
    )
    assert second is not None
    assert second["recorded"] is True

    result = mary.process(
        "remind me what we've actually been building together lately"
    )

    assert result.intent.intent_type == IntentType.RELATIONSHIP_QUERY
    assert result.reasoning.metadata["llm_skipped"] is True
    assert result.reflection.metadata["mode"] == "deterministic_system_action"
    lowered = result.final_response.lower()
    assert "your macbook" in lowered
    assert "my macbook" not in lowered
    assert "building me" in lowered
    assert "building you" not in lowered
    assert "what do you think" not in lowered


def test_shared_work_history_survives_restart(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()
    mary._learn_shared_work_statement(
        "we've been building MaryV2 together on the MacBook",
        intent=_conversation_intent(),
    )

    restarted = Mary()
    result = restarted.process("what have we worked on together?")

    assert result.intent.intent_type == IntentType.RELATIONSHIP_QUERY
    assert "maryv2" in result.final_response.lower()
    assert "macbook" in result.final_response.lower()


def test_unrelated_creator_preference_does_not_become_shared_project_history(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()
    mary.remember(
        "I like rainy nights when I'm working on creative projects",
        memory_type="episodic",
        importance=0.8,
        metadata={
            "owner": "creator",
            "speaker": "Unbe",
            "event_type": "creator_natural_share",
            "source": "interaction",
        },
    )

    result = mary.process(
        "what do you remember about what we've been working on together?"
    )

    assert "rainy" not in result.final_response.lower()
    assert "don't have enough grounded shared-work history" in result.final_response.lower()


def test_available_memory_view_combines_episodic_and_semantic_layers(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()
    episode = mary.remember(
        "We completed a portability check",
        memory_type="episodic",
        importance=0.6,
    )
    semantic = mary.remember(
        "blue",
        memory_type="semantic",
        metadata={
            "subject": "creator",
            "predicate": "favorite_color",
            "value": "blue",
            "confidence": 1.0,
        },
    )

    memories = mary._all_available_memories()

    assert episode in memories
    assert semantic in memories
    assert len(memories) == 2


def test_memory_lifecycle_explains_zero_semantic_without_mutating_it(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()
    mary.remember(
        "I like pizza",
        memory_type="episodic",
        importance=0.8,
        metadata={"owner": "creator", "source": "interaction"},
    )

    before = mary.memory.semantic.count()
    status = mary.memory_lifecycle_status()
    after = mary.memory.semantic.count()

    assert before == 0
    assert after == 0
    assert status["consolidation"]["automatic"] is False
    assert status["consolidation"]["eligible_candidates"] >= 1
    assert "not automatic" in status["consolidation"]["reason"]


def test_memory_status_command_is_display_safe_and_reports_shared_work(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()
    mary._learn_shared_work_statement(
        "we're testing MaryV2 together on macOS",
        intent=_conversation_intent(),
    )
    app = create_application(
        mary=mary,
        memory_path=tmp_path / "memory" / "memory.json",
        auto_save=False,
        load_memory=False,
    )

    output = format_memory_status(app)

    assert "MARYV2 MEMORY LIFECYCLE" in output
    assert "Durable shared-work events: 1" in output
    assert "automatic during normal conversation: NO" in output
    assert "we're testing MaryV2" not in output