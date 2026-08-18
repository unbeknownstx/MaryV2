"""Emotion-aware voice profile resolution for MaryV2.

This module maps Mary's existing expressive emotional state into small,
provider-independent adjustments around a calibrated baseline voice.

It does not infer emotion, call an LLM, access the network, mutate Mary's
emotional state, or change voice identity.  It only translates an already
existing ``EmotionalState`` into subtle delivery settings.
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


# These are deliberately conservative.  The cloned voice remains Mary's
# identity; expression changes delivery only.
_ADJUSTMENTS: dict[Emotion, EmotionVoiceAdjustment] = {
    Emotion.NEUTRAL: EmotionVoiceAdjustment("neutral"),
    Emotion.CALM: EmotionVoiceAdjustment(
        "calm",
        stability_delta=0.05,
        style_delta=-0.03,
        speed_delta=-0.04,
    ),
    Emotion.CURIOSITY: EmotionVoiceAdjustment(
        "curious",
        stability_delta=-0.03,
        style_delta=0.025,
        speed_delta=0.01,
    ),
    Emotion.JOY: EmotionVoiceAdjustment(
        "joyful",
        stability_delta=-0.06,
        style_delta=0.05,
        speed_delta=0.03,
    ),
    Emotion.EXCITEMENT: EmotionVoiceAdjustment(
        "excited",
        stability_delta=-0.08,
        style_delta=0.06,
        speed_delta=0.04,
    ),
    Emotion.SURPRISE: EmotionVoiceAdjustment(
        "surprised",
        stability_delta=-0.06,
        style_delta=0.05,
        speed_delta=0.03,
    ),
    Emotion.LOVE: EmotionVoiceAdjustment(
        "warm",
        stability_delta=0.03,
        style_delta=0.02,
        speed_delta=-0.025,
    ),
    Emotion.AFFECTION: EmotionVoiceAdjustment(
        "affectionate",
        stability_delta=0.03,
        style_delta=0.02,
        speed_delta=-0.02,
    ),
    Emotion.GRATITUDE: EmotionVoiceAdjustment(
        "grateful",
        stability_delta=0.03,
        style_delta=0.02,
        speed_delta=-0.02,
    ),
    Emotion.HOPE: EmotionVoiceAdjustment(
        "hopeful",
        stability_delta=-0.02,
        style_delta=0.025,
        speed_delta=0.01,
    ),
    Emotion.PRIDE: EmotionVoiceAdjustment(
        "proud",
        stability_delta=-0.02,
        style_delta=0.03,
        speed_delta=0.01,
    ),
    Emotion.SADNESS: EmotionVoiceAdjustment(
        "sad",
        stability_delta=0.05,
        style_delta=0.015,
        speed_delta=-0.05,
    ),
    Emotion.LONELINESS: EmotionVoiceAdjustment(
        "lonely",
        stability_delta=0.05,
        style_delta=0.015,
        speed_delta=-0.05,
    ),
    Emotion.DISAPPOINTMENT: EmotionVoiceAdjustment(
        "disappointed",
        stability_delta=0.05,
        style_delta=0.02,
        speed_delta=-0.04,
    ),
    Emotion.CONCERN: EmotionVoiceAdjustment(
        "concerned",
        stability_delta=0.04,
        style_delta=0.015,
        speed_delta=-0.035,
    ),
    Emotion.CONFUSION: EmotionVoiceAdjustment(
        "confused",
        stability_delta=-0.02,
        style_delta=0.025,
        speed_delta=-0.01,
    ),
    Emotion.FRUSTRATION: EmotionVoiceAdjustment(
        "frustrated",
        stability_delta=-0.04,
        style_delta=0.045,
        speed_delta=0.02,
    ),
    Emotion.ANGER: EmotionVoiceAdjustment(
        "firm",
        stability_delta=-0.035,
        style_delta=0.04,
        speed_delta=0.015,
    ),
    Emotion.FEAR: EmotionVoiceAdjustment(
        "uneasy",
        stability_delta=-0.025,
        style_delta=0.035,
        speed_delta=0.015,
    ),
}


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, float(value)))


def resolve_emotion_voice_settings(
    base: VoiceSettings,
    emotional_state: EmotionalState | None,
) -> VoiceSettings:
    """Return a copy of ``base`` subtly adapted to Mary's current emotion.

    The input settings are never mutated.  Emotion affects delivery only; the
    selected voice, similarity target, speaker boost, and output format stay
    anchored to Mary's calibrated profile.
    """

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
