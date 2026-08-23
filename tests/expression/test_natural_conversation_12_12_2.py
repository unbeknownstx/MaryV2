from __future__ import annotations

from mary.expression.director import ExpressionDirector
from mary.expression.emotion import Emotion, EmotionalState
from mary.voice.speech_renderer import SpeechRenderer


def test_ordinary_conversation_defaults_to_restraint():
    plan = ExpressionDirector().plan(
        input_text="that's actually pretty cool",
        response_text="Yeah. I like it.",
        emotional_state=EmotionalState(primary=Emotion.NEUTRAL, intensity=0.0),
        conversation_lane="conversation",
    )
    assert plan.metadata["performance_mode"] == "natural_conversation"
    assert plan.metadata["restraint"] >= 0.8
    assert plan.stability >= 0.5
    assert plan.style <= 0.05
    assert plan.emphasis <= 0.2
    assert plan.gesture_energy <= 0.2


def test_strong_positive_emotion_colors_instead_of_replacing_baseline():
    plan = ExpressionDirector().plan(
        input_text="we finally got it working",
        response_text="Okay, that's really good!",
        emotional_state=EmotionalState(primary=Emotion.EXCITEMENT, intensity=1.0),
        conversation_lane="conversation",
    )
    assert plan.profile == "bright"
    assert plan.energy < 0.6
    assert plan.style <= 0.09
    assert plan.emphasis < 0.3
    assert plan.gesture_energy < 0.3


def test_spoken_renderer_reduces_theatrical_pause_cues_without_changing_content():
    rendered = SpeechRenderer().render("Well... okay!! That's actually good???")
    assert "..." not in rendered
    assert "!!" not in rendered
    assert "???" not in rendered
    assert "actually good" in rendered
