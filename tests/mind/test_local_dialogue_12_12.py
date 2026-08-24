from __future__ import annotations

from mary.core.mary import Mary


def test_simple_greeting_is_answered_by_marys_local_mind_without_llm_call(monkeypatch):
    mary = Mary()
    called = {"value": False}

    def forbidden(*args, **kwargs):
        called["value"] = True
        raise AssertionError("LLM should not be called for a local reflex greeting")

    monkeypatch.setattr(mary.llm, "generate", forbidden)
    result = mary.process("hey mary")

    assert called["value"] is False
    assert result.metadata["handled_by"] == "mary_local_mind"
    assert result.reasoning.metadata["provider"] == "local/mind"
    assert result.reflection.metadata["mode"] == "local_mind_no_model"
    assert result.final_response.strip()
    assert result.metadata["delivery_plan"]["profile"] in {"playful", "amused", "bright", "casual"}


def test_local_mind_escalates_open_ended_language_instead_of_faking_intelligence():
    mary = Mary()
    decision = mary.mind.try_respond(
        "Explain why retrieval architecture matters for long-term AI character continuity.",
        intent=mary.cognition.detect_intent("Explain why retrieval architecture matters for long-term AI character continuity."),
        context={},
    )
    assert decision.handled is False
    assert decision.metadata["plan"]["act"] == "escalate"


def test_known_creator_fact_can_be_retrieved_and_spoken_locally():
    mary = Mary()
    mary.user_model.record_profile(
        category="fact",
        key="favorite_color",
        value="blue",
        source="creator_explicit",
        confidence=1.0,
        explicitly_shared=True,
    )
    mary.mind.rebuild_reservoir()
    intent = mary.cognition.detect_intent("what is my favorite color?")
    # The full Mary coordinator may route this exact phrasing through the older
    # authoritative relationship-query handler, which outranks the reservoir.
    # The local mind itself must still be able to retrieve/compose the fact.
    from mary.cognition.intent import Intent, IntentType
    local = mary.mind.try_respond(
        "what is my favorite color?",
        intent=Intent(intent_type=IntentType.UNKNOWN, confidence=1.0),
        context={},
    )
    assert local.handled is True
    assert "blue" in local.response.lower()


def test_represented_mary_preference_can_answer_locally():
    from mary.cognition.intent import Intent, IntentType
    from mary.mind.reservoir import ReservoirRecord

    mary = Mary()
    mary.mind.reservoir.upsert(ReservoirRecord(
        record_id="pref:blue-neon",
        kind="mary_preference",
        subject="mary",
        predicate="blue_neon",
        content="Mary likes blue neon.",
        source="preferences",
        authority="mary_developed",
        confidence=.95,
        tags=("mary", "preference", "blue neon"),
    ))
    local = mary.mind.try_respond(
        "do you like blue neon?",
        intent=Intent(intent_type=IntentType.UNKNOWN, confidence=1.0),
        context={},
    )
    assert local.handled is True
    assert "blue neon" in local.response.lower()


def test_high_confidence_local_knowledge_can_answer_without_model():
    from mary.cognition.intent import Intent, IntentType
    from mary.mind.reservoir import ReservoirRecord

    mary = Mary()
    mary.mind.reservoir.upsert(ReservoirRecord(
        record_id="knowledge:reservoir",
        kind="knowledge_concept",
        subject="world",
        predicate="cognitive_reservoir",
        content="A cognitive reservoir is a rebuildable local retrieval layer over authoritative Mary state.",
        source="knowledge_manager",
        authority="knowledge_verified",
        confidence=.95,
        tags=("knowledge", "cognitive reservoir"),
    ))
    local = mary.mind.try_respond(
        "what do you know about cognitive reservoir?",
        intent=Intent(intent_type=IntentType.UNKNOWN, confidence=1.0),
        context={},
    )
    assert local.handled is True
    assert "rebuildable local retrieval" in local.response.lower()
