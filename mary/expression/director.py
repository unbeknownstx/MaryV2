"""Deterministic expression director shared by voice and avatar presentation.

12.12.2 calibrates Mary around *ordinary conversation first*.  Emotional state
colors a stable conversational baseline instead of replacing it with a new
performance persona on every turn.  This keeps voice/gesture dynamic while
avoiding the theatrical, over-emphasized delivery that can make routine chat
sound like a scripted protagonist monologue.
"""
from __future__ import annotations

import re
from typing import Any

from mary.expression.emotion import Emotion, EmotionalState
from .delivery_plan import DeliveryPlan


class ExpressionDirector:
    """Map represented state + speech act into a bounded, restrained plan.

    The director never infers hidden creator emotion. It only uses Mary's
    represented emotional state, her already-selected dialogue act/lane and
    literal features of Mary's response.
    """

    def plan(
        self,
        *,
        input_text: str,
        response_text: str,
        emotional_state: EmotionalState | None,
        conversation_lane: str = "conversation",
        dialogue_act: str | None = None,
    ) -> DeliveryPlan:
        emotion = emotional_state.primary if emotional_state is not None else Emotion.NEUTRAL
        intensity = _clamp(getattr(emotional_state, "intensity", 0.0), 0.0, 1.0)
        response = str(response_text or "")
        lane = str(conversation_lane or "conversation").lower()
        act = str(dialogue_act or "").lower()

        # Natural baseline: Mary is talking to someone familiar, not auditioning
        # for a dramatic role.  Stability is intentionally higher and style/
        # emphasis lower than 12.12.0. Personality should come mostly from what
        # Mary says, with delivery providing subtle color.
        profile = "conversational"
        energy = 0.38
        warmth = 0.50
        pace = 1.00
        stability = 0.54
        style = 0.025
        emphasis = 0.15
        avatar = "neutral"
        gesture = 0.18
        pause_style = "natural"
        rationale = "restrained conversational baseline"

        # Ordinary conversation gets deliberately low emotional gain. Thinking
        # can slow slightly; strong states can still become visibly expressive,
        # but they blend into the baseline instead of replacing it wholesale.
        influence = 0.08 + (0.24 * intensity)
        if lane == "thinking":
            influence = min(0.28, influence + 0.04)
            pace = _lerp(pace, 0.96, 0.45)
            gesture = _lerp(gesture, 0.14, 0.45)
            pause_style = "thoughtful"

        target = _emotion_target(emotion)
        if target is not None:
            target_profile, target_energy, target_warmth, target_pace, target_stability, target_style, target_emphasis, target_avatar, target_gesture = target
            profile = target_profile if intensity >= 0.58 else profile
            energy = _lerp(energy, target_energy, influence)
            warmth = _lerp(warmth, target_warmth, influence)
            pace = _lerp(pace, target_pace, influence)
            stability = _lerp(stability, target_stability, influence)
            style = _lerp(style, target_style, influence)
            emphasis = _lerp(emphasis, target_emphasis, influence)
            gesture = _lerp(gesture, target_gesture, influence)
            if intensity >= 0.42:
                avatar = target_avatar
            # Concern/softness can remain very warm without becoming theatrical;
            # warmth is descriptive metadata, not an ElevenLabs exaggeration knob.
            if emotion in {Emotion.CONCERN, Emotion.SADNESS, Emotion.DISAPPOINTMENT, Emotion.LONELINESS} and intensity >= 0.65:
                warmth = max(warmth, 0.72)
            rationale += f"; {emotion.value} blended at {influence:.2f} gain"

        # Short social turns should be *easier*, not more performed. A tiny lift
        # keeps greetings alive without dropping stability or forcing playful
        # emphasis.
        if lane == "social_instant" or act in {"greet", "react", "laugh", "thanks_response"}:
            if emotion not in {Emotion.CONCERN, Emotion.SADNESS, Emotion.ANGER}:
                profile = "playful"
            energy = min(0.58, energy + 0.05)
            pace = min(1.04, max(pace, 1.00))
            emphasis = min(0.28, emphasis + 0.03)
            gesture = min(0.30, gesture + 0.04)
            rationale += "; restrained social beat"

        # Literal amusement can move farther because the response itself carries
        # explicit evidence that Mary intends amusement. Even here, 12.12.2
        # remains well below the old theatrical profile.
        if re.search(r"(?:😂|😭|\blol\b|\blmao\b|\bhaha+\b|\bhehe+\b)", response, flags=re.I):
            profile = "amused"
            energy = max(energy, 0.56)
            stability = min(stability, 0.48)
            style = max(style, 0.04)
            emphasis = max(emphasis, 0.22)
            avatar = "happy"
            gesture = max(gesture, 0.26)
            rationale += "; explicit amusement"

        # Exclamation is only a small cue now. It should never turn a normal line
        # into a trailer voice.
        if "!" in response:
            energy = min(0.72, energy + 0.02)
            emphasis = min(0.38, emphasis + 0.02)

        return DeliveryPlan(
            profile=profile,
            energy=_clamp(energy, 0.0, 1.0),
            warmth=_clamp(warmth, 0.0, 1.0),
            pace=_clamp(pace, 0.88, 1.10),
            stability=_clamp(stability, 0.40, 0.68),
            style=_clamp(style, 0.0, 0.09),
            emphasis=_clamp(emphasis, 0.0, 0.45),
            pause_style=pause_style,
            avatar_expression=avatar,
            gesture_energy=_clamp(gesture, 0.0, 0.45),
            rationale=rationale,
            metadata={
                "emotion": emotion.value,
                "emotion_intensity": intensity,
                "emotion_gain": round(influence, 3),
                "lane": lane,
                "dialogue_act": act or None,
                "performance_mode": "natural_conversation",
                "restraint": 0.82,
            },
        )


def _emotion_target(emotion: Emotion) -> tuple[str, float, float, float, float, float, float, str, float] | None:
    if emotion in {Emotion.JOY, Emotion.EXCITEMENT, Emotion.SURPRISE, Emotion.PRIDE}:
        return ("bright", 0.72, 0.66, 1.04, 0.47, 0.065, 0.36, "happy", 0.40)
    if emotion in {Emotion.WARMTH, Emotion.AFFECTION, Emotion.LOVE, Emotion.APPRECIATION, Emotion.GRATITUDE}:
        return ("warm", 0.48, 0.80, 0.98, 0.55, 0.035, 0.24, "happy", 0.26)
    if emotion in {Emotion.CONCERN, Emotion.SADNESS, Emotion.DISAPPOINTMENT, Emotion.LONELINESS}:
        return ("soft", 0.28, 0.72, 0.94, 0.58, 0.025, 0.18, "sad", 0.16)
    if emotion in {Emotion.FRUSTRATION, Emotion.ANGER}:
        return ("firm", 0.60, 0.34, 1.00, 0.57, 0.045, 0.34, "angry", 0.34)
    if emotion in {Emotion.CURIOSITY, Emotion.CONFUSION}:
        return ("thoughtful", 0.39, 0.55, 0.97, 0.55, 0.03, 0.20, "neutral", 0.20)
    return None


def _lerp(start: float, end: float, amount: float) -> float:
    return float(start) + ((float(end) - float(start)) * _clamp(amount, 0.0, 1.0))


def _clamp(value: Any, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = minimum
    return max(minimum, min(maximum, number))
