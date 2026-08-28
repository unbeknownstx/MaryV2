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

    mary = Mary()
    mary.preferences.set_preference(
        name="blue_neon",
        category="aesthetic",
        strength=0.95,
        polarity=0.95,
        confidence=0.95,
        source="preferences",
    )
    mary.mind.rebuild_reservoir()
    local = mary.mind.try_respond(
        "do you like blue neon?",
        intent=Intent(intent_type=IntentType.UNKNOWN, confidence=1.0),
        context={},
    )
    assert local.handled is True
    assert "blue neon" in local.response.lower()




def test_core_mary_preference_answers_locally_even_when_reservoir_is_cold():
    from mary.cognition.intent import Intent, IntentType

    mary = Mary()
    # Do not rebuild the reservoir. The input topic is only a selector; the
    # local path must confirm it against Mary's live canonical Preferences owner.
    local = mary.mind.try_respond(
        "do you like drawing?",
        intent=Intent(intent_type=IntentType.QUESTION, confidence=1.0),
        context={},
    )
    assert local.handled is True
    assert "drawing" in local.response.lower()
    assert "like" in local.response.lower()


def test_unknown_direct_mary_preference_still_escalates_when_reservoir_is_cold():
    from mary.cognition.intent import Intent, IntentType

    mary = Mary()
    local = mary.mind.try_respond(
        "do you like fog?",
        intent=Intent(intent_type=IntentType.QUESTION, confidence=1.0),
        context={},
    )
    assert local.handled is False
    assert local.metadata["escalation_reason"] == "mary_preference_confirmation_missing"


def test_high_confidence_local_knowledge_can_answer_without_model():
    from mary.cognition.intent import Intent, IntentType

    mary = Mary()
    # Production Hybrid V2 local answers require confirmation against a
    # canonical owner. Semantic memory is the authority-bearing owner for this
    # bounded local knowledge surface; the reservoir is only its derived index.
    mary.memory.semantic.add(
        subject="cognitive reservoir",
        predicate="definition",
        value="a rebuildable local retrieval layer over authoritative Mary state",
        confidence=0.95,
        source="semantic_memory",
    )
    mary.mind.rebuild_reservoir()
    local = mary.mind.try_respond(
        "what do you know about cognitive reservoir?",
        intent=Intent(intent_type=IntentType.UNKNOWN, confidence=1.0),
        context={},
    )
    assert local.handled is True
    assert "rebuildable local retrieval" in local.response.lower()


def test_shared_work_milestone_is_a_local_character_reflex_without_llm(monkeypatch):
    mary = Mary()
    called = {"value": False}

    def forbidden(*args, **kwargs):
        called["value"] = True
        raise AssertionError("milestone reflex should not require a language-model call")

    monkeypatch.setattr(mary.llm, "generate", forbidden)
    result = mary.process("I finally solved that bug and all the tests passed.")

    assert called["value"] is False
    assert result.metadata["handled_by"] == "mary_local_mind"
    assert result.reasoning.metadata["provider"] == "local/mind"
    assert result.reasoning.metadata["response_engine"] == "local_composer_v2"
    assert result.reflection.metadata["llm_calls"] == 0
    assert "?" not in result.final_response
    assert result.final_response.strip()
