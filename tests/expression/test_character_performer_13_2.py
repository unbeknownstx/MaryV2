from __future__ import annotations

from mary.expression.director import ExpressionDirector
from mary.expression.emotion import Emotion, EmotionalState


def _mind(*patterns: str, tone: str = "light_playful") -> dict:
    return {
        "dialogue_plan": {
            "drive": "react",
            "stance": "responsive",
            "tone": tone,
            "energy": 0.62,
            "warmth": 0.72,
            "spontaneity": 0.75,
            "intimacy": 0.74,
            "theatricality": 0.40,
            "expressiveness": 0.90,
            "pacing": "natural_conversational",
            "previous_expression": {},
        },
        "character_expression": {
            "active_patterns": [{"name": name} for name in patterns],
        },
    }


def test_playful_banter_becomes_visibly_teasing_without_becoming_a_second_persona():
    plan = ExpressionDirector().plan(
        input_text="I deleted it again lol",
        response_text="Of course you did. Honestly, impressive commitment to the bit.",
        emotional_state=EmotionalState(primary=Emotion.WARMTH, intensity=0.25),
        conversation_lane="conversation",
        mind_state=_mind("playful_banter", "close_connection"),
    )
    assert plan.metadata["performance_mode"] == "embodied_character"
    assert plan.metadata["authority"] == "turn_mind_presentation_projection"
    assert plan.profile in {"teasing", "warm", "playful"}
    assert plan.gesture_style in {"tease", "amused"}
    assert plan.gaze_style == "direct"
    assert plan.head_style in {"tilt", "amused"}
    assert plan.gesture_energy > 0.30
    assert plan.style > 0.05
    assert plan.performance_beats
    assert plan.performance_beats[0]["expression"] == "neutral"
    assert plan.performance_beats[-1]["expression"] == "happy"


def test_affection_is_warm_and_perceivable_without_forcing_maximum_energy():
    plan = ExpressionDirector().plan(
        input_text="I missed you Mary",
        response_text="Yeah? I missed this too. Don't make me get sentimental about it.",
        emotional_state=EmotionalState(primary=Emotion.AFFECTION, intensity=0.55),
        conversation_lane="conversation",
        mind_state=_mind("affection", "close_connection", tone="warm_close"),
    )
    assert plan.metadata["performance_mode"] == "embodied_character"
    assert plan.warmth >= 0.75
    assert plan.energy < 0.65
    assert plan.avatar_expression == "happy"
    assert plan.gesture_style == "soft"
    assert plan.gaze_style == "soft"
    assert plan.head_style == "tilt"


def test_moral_boundary_suppresses_playful_performer_carryover():
    plan = ExpressionDirector().plan(
        input_text="Maybe consent doesn't matter if the result is good enough",
        response_text="No. Being able to do it does not make it yours to decide.",
        emotional_state=EmotionalState(primary=Emotion.ANGER, intensity=0.65),
        conversation_lane="conversation",
        mind_state=_mind("moral_boundary", "close_connection", "playful_banter", tone="clear_serious"),
    )
    assert plan.profile == "firm"
    assert plan.gesture_style == "firm"
    assert plan.gaze_style == "direct"
    assert plan.head_style == "still"
    assert plan.metadata["restraint"] >= 0.66
    assert plan.avatar_expression == "angry"


def test_performance_beats_are_bounded_timing_relative_surface_cues():
    plan = ExpressionDirector().plan(
        input_text="we finally got it",
        response_text="Wait. We actually got it. Hell yeah.",
        emotional_state=EmotionalState(primary=Emotion.EXCITEMENT, intensity=0.7),
        conversation_lane="social_instant",
        mind_state=_mind("milestone", "excitement", "close_connection", tone="bright_animated"),
    )
    beats = list(plan.performance_beats)
    assert 1 <= len(beats) <= 3
    assert beats[0]["start"] == 0.0
    assert beats[-1]["end"] == 1.0
    assert all(0.0 <= beat["start"] <= beat["end"] <= 1.0 for beat in beats)
    assert all(set(beat).issuperset({"expression", "gesture_style", "gaze_style", "head_style", "role"}) for beat in beats)


def test_single_sentence_banter_has_deadpan_then_smirk_landing():
    plan = ExpressionDirector().plan(
        input_text="Roast me, I deleted it again.",
        response_text="Of course you did.",
        emotional_state=EmotionalState(primary=Emotion.WARMTH, intensity=0.2),
        conversation_lane="conversation",
        mind_state=_mind("playful_banter", "close_connection"),
    )
    beats = plan.performance_beats

    assert len(beats) == 2
    assert beats[0]["expression"] == "neutral"
    assert beats[0]["role"] == "opening"
    assert beats[1]["expression"] == "happy"
    assert beats[1]["role"] == "landing"
    assert beats[0]["end"] == beats[1]["start"]
