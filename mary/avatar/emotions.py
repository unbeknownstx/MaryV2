"""
MaryV2 - Avatar Emotion Mapping

Translates Mary's expressive emotional state into presentation data that
an avatar controller can consume.

This module does not alter Mary's emotional state and does not connect to
an external avatar engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mary.expression.emotion import Emotion, EmotionalState


@dataclass(frozen=True)
class AvatarExpression:
    """Presentation-safe avatar expression description."""

    name: str
    emotion: Emotion = Emotion.NEUTRAL
    intensity: float = 0.0
    parameters: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class AvatarEmotionMapper:
    """Map Mary's existing emotional state into avatar presentation data."""

    EXPRESSION_NAMES = {
        Emotion.NEUTRAL: "neutral",
        Emotion.JOY: "happy",
        Emotion.SADNESS: "sad",
        Emotion.ANGER: "angry",
        Emotion.FEAR: "afraid",
        Emotion.LOVE: "loving",
        Emotion.AFFECTION: "affectionate",
        Emotion.GRATITUDE: "grateful",
        Emotion.CURIOSITY: "curious",
        Emotion.EXCITEMENT: "excited",
        Emotion.SURPRISE: "surprised",
        Emotion.CONFUSION: "confused",
        Emotion.FRUSTRATION: "frustrated",
        Emotion.CALM: "calm",
        Emotion.CONCERN: "concerned",
        Emotion.PRIDE: "proud",
        Emotion.DISAPPOINTMENT: "disappointed",
        Emotion.HOPE: "hopeful",
        Emotion.LONELINESS: "lonely",
    }

    def map_state(self, state: EmotionalState) -> AvatarExpression:
        """Translate an EmotionalState without mutating it."""

        intensity = max(0.0, min(1.0, float(state.intensity)))

        return AvatarExpression(
            name=self.EXPRESSION_NAMES.get(
                state.primary,
                "neutral",
            ),
            emotion=state.primary,
            intensity=intensity,
            parameters={
                "intensity": intensity,
                "valence": float(state.valence),
                "arousal": float(state.arousal),
                "confidence": float(state.confidence),
            },
            metadata={
                "source": "mary.expression.emotion",
            },
        )
