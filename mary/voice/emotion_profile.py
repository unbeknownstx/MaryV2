"""Emotion-aware voice profile resolution for MaryV2.

This module maps Mary's existing expressive emotional state into tiny,
provider-independent adjustments around the calibrated Mary voice.

SpeechRenderer V3 intentionally keeps these shifts close to the user's tuned
baseline. Emotion should color Mary's delivery, not overpower the identity of
the cloned voice or make serious/concerned responses sound stiff.
"""

from __future__ import annotations

from dataclasses import dataclass

from mary.expression.emotion import Emotion, EmotionalState
from mary.voice.text_to_speech import VoiceSettings


@dataclass(frozen=True)
class EmotionVoiceAdjustment:
    """Small delivery deltas applied around Mary's calibrated voice."""

    name: str
    stability_delta: float = 0.0
    style_delta: float = 0.0
    speed_delta: float = 0.0


# Keep Mary's calibrated clone as the anchor. Even at intensity 1.0 these are
# intentionally small changes; the text and punctuation are allowed to carry
# most of the performance.
_ADJUSTMENTS: dict[Emotion, EmotionVoiceAdjustment] = {
    Emotion.NEUTRAL: EmotionVoiceAdjustment("neutral"),
    Emotion.CALM: EmotionVoiceAdjustment("calm", 0.01, -0.005, -0.015),
    Emotion.CURIOSITY: EmotionVoiceAdjustment("curious", -0.02, 0.015, 0.005),
    Emotion.JOY: EmotionVoiceAdjustment("joyful", -0.03, 0.02, 0.015),
    Emotion.EXCITEMENT: EmotionVoiceAdjustment("excited", -0.04, 0.025, 0.025),
    Emotion.SURPRISE: EmotionVoiceAdjustment("surprised", -0.035, 0.025, 0.02),
    Emotion.LOVE: EmotionVoiceAdjustment("warm", 0.005, 0.01, -0.01),
    Emotion.AFFECTION: EmotionVoiceAdjustment("affectionate", 0.005, 0.01, -0.01),
    Emotion.GRATITUDE: EmotionVoiceAdjustment("grateful", 0.0, 0.01, -0.005),
    Emotion.HOPE: EmotionVoiceAdjustment("hopeful", -0.015, 0.015, 0.005),
    Emotion.PRIDE: EmotionVoiceAdjustment("proud", -0.03, 0.025, 0.015),
    Emotion.SADNESS: EmotionVoiceAdjustment("sad", 0.01, 0.005, -0.02),
    Emotion.LONELINESS: EmotionVoiceAdjustment("lonely", 0.01, 0.005, -0.02),
    Emotion.DISAPPOINTMENT: EmotionVoiceAdjustment("disappointed", 0.01, 0.01, -0.015),
    Emotion.CONCERN: EmotionVoiceAdjustment("concerned", -0.01, 0.015, -0.01),
    Emotion.CONFUSION: EmotionVoiceAdjustment("confused", -0.015, 0.015, -0.005),
    Emotion.FRUSTRATION: EmotionVoiceAdjustment("frustrated", -0.025, 0.02, 0.01),
    Emotion.ANGER: EmotionVoiceAdjustment("firm", -0.02, 0.015, 0.005),
    Emotion.FEAR: EmotionVoiceAdjustment("uneasy", -0.02, 0.02, 0.01),
}


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, float(value)))


def resolve_emotion_voice_settings(
    base: VoiceSettings,
    emotional_state: EmotionalState | None,
) -> VoiceSettings:
    """Return a copy of ``base`` subtly adapted to Mary's current emotion."""

    if emotional_state is None:
        emotion = Emotion.NEUTRAL
        intensity = 0.0
    else:
        emotion = emotional_state.primary
        intensity = _clamp(emotional_state.intensity, 0.0, 1.0)

    adjustment = _ADJUSTMENTS.get(
        emotion,
        EmotionVoiceAdjustment(emotion.value),
    )

    metadata = dict(base.metadata)
    base_stability = _clamp(metadata.get("stability", 0.42), 0.0, 1.0)
    base_similarity = _clamp(metadata.get("similarity_boost", 0.82), 0.0, 1.0)
    base_style = _clamp(metadata.get("style", 0.11), 0.0, 1.0)

    stability = _clamp(
        base_stability + (adjustment.stability_delta * intensity),
        0.0,
        1.0,
    )
    style = _clamp(
        base_style + (adjustment.style_delta * intensity),
        0.0,
        1.0,
    )
    speed = _clamp(
        base.speed + (adjustment.speed_delta * intensity),
        0.7,
        1.2,
    )

    metadata.update(
        {
            "stability": stability,
            "similarity_boost": base_similarity,
            "style": style,
            "emotion_profile": adjustment.name,
            "emotion": emotion.value,
            "emotion_intensity": intensity,
        }
    )

    return VoiceSettings(
        voice=base.voice,
        language=base.language,
        speed=speed,
        pitch=base.pitch,
        volume=base.volume,
        style=base.style,
        emotion=emotion,
        emotion_intensity=intensity,
        output_format=base.output_format,
        sample_rate=base.sample_rate,
        metadata=metadata,
    )


def emotion_voice_profile_name(
    emotional_state: EmotionalState | None,
) -> str:
    """Return the human-readable delivery profile for an emotional state."""

    emotion = (
        emotional_state.primary
        if emotional_state is not None
        else Emotion.NEUTRAL
    )
    return _ADJUSTMENTS.get(
        emotion,
        EmotionVoiceAdjustment(emotion.value),
    ).name
