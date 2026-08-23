from __future__ import annotations

from mary.expression.director import ExpressionDirector
from mary.expression.emotion import Emotion, EmotionalState


def test_expression_director_keeps_social_delivery_alive_but_restrained_without_model():
    director = ExpressionDirector()
    neutral = director.plan(
        input_text="hey mary",
        response_text="Heyy. I'm here!",
        emotional_state=EmotionalState(primary=Emotion.NEUTRAL, intensity=0.0),
        conversation_lane="social_instant",
        dialogue_act="greet",
    )
    assert neutral.profile == "playful"
    assert neutral.stability >= 0.50
    assert neutral.style <= 0.05
    assert neutral.emphasis <= 0.24
    assert neutral.gesture_energy <= 0.25
    assert neutral.metadata["performance_mode"] == "natural_conversation"


def test_expression_director_softens_concerned_delivery():
    director = ExpressionDirector()
    plan = director.plan(
        input_text="rough day",
        response_text="Yeah. I'm here.",
        emotional_state=EmotionalState(primary=Emotion.CONCERN, intensity=0.8),
        conversation_lane="conversation",
    )
    assert plan.profile == "soft"
    assert plan.pace < 1.0
    assert plan.warmth > 0.7
    assert plan.style <= 0.05
