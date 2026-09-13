from __future__ import annotations

from mary.cognition.cognitive_character import CognitiveCharacterRuntime


def _plan(text: str, *, communication: dict | None = None, emotion: str = "neutral"):
    return CognitiveCharacterRuntime().plan(
        input_text=text,
        relationship={
            "user_profile": {
                "communication_style": dict(communication or {}),
            }
        },
        disposition={"preferred_length": "natural"},
        performance={"emotional_color": emotion, "pacing": "natural_conversational"},
        emotion={"turn_primary": emotion},
        continuity={"drive": "react"},
    )


def test_deep_work_prefers_quality_and_allows_escalation():
    plan = _plan("Analyze the architecture and develop a plan to debug the system conflicts.")

    assert plan.cognitive_mode == "deliberate"
    assert plan.reasoning_depth == "deep"
    assert plan.knowledge_breadth == "broad"
    assert plan.latency_priority == "quality_first"
    assert plan.escalation_allowed is True


def test_quick_lookup_prefers_fast_small_sufficient_compute():
    plan = _plan("What is the meaning of recursion?")

    assert plan.cognitive_mode == "direct"
    assert plan.reasoning_depth == "light"
    assert plan.latency_priority == "fast"
    assert plan.local_preference > 0.7


def test_relational_conversation_prefers_local_responsive_presence():
    plan = _plan("Mary, what do you think about what we were talking about yesterday?")

    assert plan.cognitive_mode == "relational"
    assert plan.latency_priority == "responsive"
    assert plan.local_preference >= 0.8
    assert "preserve_conversational_thread" in plan.continuity_intents


def test_user_communication_preferences_shape_delivery_not_identity():
    plan = _plan(
        "Explain why this architecture works.",
        communication={
            "preferred_length": "compact",
            "explanation_style": "examples_first",
            "technical_register": "plain_then_technical",
            "conversational_register": "familiar",
        },
    )

    assert plan.preferred_length == "compact"
    assert plan.explanation_style == "examples_first"
    assert plan.technical_register == "plain_then_technical"
    assert plan.conversational_register == "familiar"


def test_embodiment_intents_are_non_action_claiming_presentation_hints():
    plan = _plan("I finally got it working!", emotion="joy")

    assert "attend_to_user" in plan.embodiment_intents
    assert "brighten_expression" in plan.embodiment_intents
    assert any("presentation" in instruction.lower() for instruction in plan.instructions)


def test_runtime_does_not_choose_or_name_a_provider():
    plan = _plan("Research and compare the options for me.")
    payload = plan.to_dict()

    assert "provider" not in payload
    assert "model" not in payload
    assert set(payload) >= {
        "cognitive_mode",
        "reasoning_depth",
        "local_preference",
        "escalation_allowed",
        "embodiment_intents",
    }
