from __future__ import annotations

from mary.expression.emotion import Emotion, EmotionalState
from mary.voice import SpeechAudioFormat, VoiceSettings, resolve_emotion_voice_settings


def _base() -> VoiceSettings:
    return VoiceSettings(
        voice="mary",
        speed=0.97,
        output_format=SpeechAudioFormat.MP3,
        metadata={
            "stability": 0.42,
            "similarity_boost": 0.82,
            "style": 0.11,
            "use_speaker_boost": True,
        },
    )


def test_neutral_emotion_preserves_marys_calibrated_voice() -> None:
    base = _base()
    active = resolve_emotion_voice_settings(
        base,
        EmotionalState(primary=Emotion.NEUTRAL, intensity=0.0),
    )

    assert active.speed == 0.97
    assert active.metadata["stability"] == 0.42
    assert active.metadata["similarity_boost"] == 0.82
    assert active.metadata["style"] == 0.11
    assert active.metadata["use_speaker_boost"] is True
    assert active.emotion == Emotion.NEUTRAL
    assert active.emotion_intensity == 0.0


def test_excitement_makes_delivery_subtly_more_dynamic_without_changing_identity() -> None:
    base = _base()
    active = resolve_emotion_voice_settings(
        base,
        EmotionalState(primary=Emotion.EXCITEMENT, intensity=1.0),
    )

    assert round(active.metadata["stability"], 2) == 0.38
    assert active.metadata["similarity_boost"] == 0.82
    assert round(active.metadata["style"], 3) == 0.135
    assert round(active.speed, 3) == 0.995
    assert active.voice == "mary"
    assert active.emotion == Emotion.EXCITEMENT


def test_calm_delivery_is_slightly_slower_and_more_stable() -> None:
    active = resolve_emotion_voice_settings(
        _base(),
        EmotionalState(primary=Emotion.CALM, intensity=1.0),
    )

    assert round(active.metadata["stability"], 2) == 0.43
    assert round(active.metadata["style"], 3) == 0.105
    assert round(active.speed, 3) == 0.955


def test_emotion_adjustment_scales_with_intensity_and_does_not_mutate_base() -> None:
    base = _base()
    active = resolve_emotion_voice_settings(
        base,
        EmotionalState(primary=Emotion.CURIOSITY, intensity=0.5),
    )

    assert round(active.metadata["stability"], 2) == 0.41
    assert round(active.metadata["style"], 4) == 0.1175
    assert round(active.speed, 4) == 0.9725

    assert base.speed == 0.97
    assert base.metadata["stability"] == 0.42
    assert base.metadata["style"] == 0.11
    assert base.emotion is None
