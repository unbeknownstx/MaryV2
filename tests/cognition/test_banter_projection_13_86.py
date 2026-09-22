from mary.core.mary import Mary
from mary.expression.dialogue_plan import DialoguePlanner
from mary.expression.director import ExpressionDirector


def _familiar_mary() -> Mary:
    mary = Mary()
    for index in range(8):
        mary.relationship.history.record_interaction(
            f"banter familiarity seed {index}",
            importance=0.1,
            metadata={"test_only": True},
        )
    return mary


def test_turnmind_can_activate_opportunistic_banter_without_literal_roast_command():
    mary = _familiar_mary()
    text = "Bro I said that boss was easy and then I lost the round lol."
    intent = mary.cognition.detect_intent(text)

    mind = mary.turn_mind.build(
        input_text=text,
        intent=intent,
        relevant_memories=[],
        recent_conversation=[
            {
                "role": "user",
                "content": "I called the tutorial boss free XP before we started.",
            }
        ],
    ).to_dict()

    expression = mind["character_expression"]
    names = [item["name"] for item in expression["active_patterns"]]
    assert "playful_banter" in names
    assert expression["banter"]["active"] is True
    assert expression["banter"]["callback_scope"] == "session_only"
    assert expression["banter"]["candidate_angles"]


def test_dialogue_and_performance_consume_same_banter_projection():
    mary = _familiar_mary()
    text = "Roast me, I said I never miss and then missed the easiest shot in the game lol."
    intent = mary.cognition.detect_intent(text)

    mind = mary.turn_mind.build(
        input_text=text,
        intent=intent,
        relevant_memories=[],
        recent_conversation=[
            {
                "role": "user",
                "content": "I was calling myself the clutch king five minutes ago.",
            }
        ],
    ).to_dict()
    dialogue = DialoguePlanner().plan(mind, input_text=text).to_dict()
    mind["dialogue_plan"] = dialogue

    assert dialogue["stance"] == "playful_pushback"
    assert dialogue["tone"] == "teasing_dry"
    assert dialogue["allow_question"] is False
    assert any("Banter opportunity" in item for item in dialogue["directives"])
    assert any("Banter angle" in item for item in dialogue["directives"])

    delivery = ExpressionDirector().plan(
        input_text=text,
        response_text="Clutch king had a brief constitutional crisis there.",
        emotional_state=mary.emotion.state,
        conversation_lane="conversation",
        mind_state=mind,
        social_context="stream",
    )

    assert delivery.profile == "teasing"
    assert delivery.pause_style == "dry"
    assert delivery.reaction_style == "smirk"
    assert delivery.metadata["banter_active"] is True
    assert delivery.metadata["banter_intensity"] >= 0.8
    assert delivery.metadata["banter_techniques"]
    assert delivery.metadata["banter_callback_scope"] == "session_only"
    assert delivery.metadata["banter_wit_score"] is not None
    assert delivery.metadata["banter_score"]["genericness_penalty"] == 0.0
    assert delivery.performance_beats


def test_serious_turn_keeps_banter_off_across_turnmind():
    mary = _familiar_mary()
    text = "I know I said roast me earlier, but this is serious and I'm grieving."
    intent = mary.cognition.detect_intent(text)

    mind = mary.turn_mind.build(
        input_text=text,
        intent=intent,
        relevant_memories=[],
        recent_conversation=[],
        incoming_emotion_appraisal={"emotion": "sadness", "intensity": 0.8},
    ).to_dict()

    expression = mind["character_expression"]
    assert expression["banter"]["active"] is False
    names = [item["name"] for item in expression["active_patterns"]]
    assert "grief_or_hurt" in names
