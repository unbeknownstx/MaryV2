from __future__ import annotations

import pytest

from mary.cognition.intent import Intent, IntentType
from mary.core.mary import Mary
from mary.runtime.application import MaryApplication, create_application, format_memory_status


_applications: list[MaryApplication] = []


def _run(app: MaryApplication, input_text: str):
    return app.run(input_text).metadata["pipeline_values"]["cognitive_cycle"]


def _application() -> MaryApplication:
    app = create_application(
        auto_save=False, load_memory=False, load_developed_self=False,
        load_preference_promotion=False, load_knowledge=False,
    )
    _applications.append(app)
    return app


@pytest.fixture(autouse=True)
def _close_applications():
    yield
    while _applications:
        _applications.pop().close()


def _conversation_intent() -> Intent:
    return Intent(
        intent_type=IntentType.CONVERSATION,
        confidence=1.0,
        source="test",
    )


def test_shared_work_question_routes_to_durable_relationship_recall(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = _application()
    mary = app.mary

    prompts = (
        "what do you remember about what we've been working on together?",
        "remind me what we've actually been building together lately",
        "what are we working on?",
        "what have we been working on today?",
        "where are we with MaryV2?",
    )

    for prompt in prompts:
        intent = mary.cognition.detect_intent(prompt)
        assert intent.intent_type == IntentType.RELATIONSHIP_QUERY
        assert intent.parameters["relationship_query_type"] == "shared_work"



def test_exact_current_work_question_uses_durable_shared_work_not_model_guess(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = _application()
    mary = app.mary

    learned = mary._learn_shared_work_statement(
        "We were working on you on the Mac and now have you an iPhone app.",
        intent=_conversation_intent(),
    )
    assert learned is not None
    assert learned["recorded"] is True

    result = _run(app, "What are we working on?")

    assert result.intent.intent_type == IntentType.RELATIONSHIP_QUERY
    assert result.intent.parameters["relationship_query_type"] == "shared_work"
    assert result.reasoning.metadata["llm_skipped"] is True
    assert "iphone app" in result.final_response.lower()
    assert mary._last_memory_recall_trace["selected_count"] >= 1

def test_macbook_mixed_turn_becomes_grounded_shared_work_history(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = _application()
    mary = app.mary

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

    result = _run(app,
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
    app = _application()
    mary = app.mary
    mary._learn_shared_work_statement(
        "we've been building MaryV2 together on the MacBook",
        intent=_conversation_intent(),
    )

    restarted_app = _application()
    restarted = restarted_app.mary
    result = _run(restarted_app, "what have we worked on together?")

    assert result.intent.intent_type == IntentType.RELATIONSHIP_QUERY
    assert "maryv2" in result.final_response.lower()
    assert "macbook" in result.final_response.lower()


def test_unrelated_creator_preference_does_not_become_shared_project_history(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = _application()
    mary = app.mary
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

    result = _run(app,
        "what do you remember about what we've been working on together?"
    )

    assert "rainy" not in result.final_response.lower()
    assert "don't have enough grounded shared-work history" in result.final_response.lower()


def test_available_memory_view_combines_episodic_and_semantic_layers(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = _application()
    mary = app.mary
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
    app = _application()
    mary = app.mary
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
    app = _application()
    mary = app.mary
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
    _applications.append(app)

    output = format_memory_status(app)

    assert "MARYV2 MEMORY LIFECYCLE" in output
    assert "Durable shared-work events: 1" in output
    assert "automatic during normal conversation: NO" in output
    assert "we're testing MaryV2" not in output