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


def test_concern_stays_close_to_calibrated_voice_instead_of_becoming_stiff() -> None:
    active = resolve_emotion_voice_settings(
        _base(),
        EmotionalState(primary=Emotion.CONCERN, intensity=1.0),
    )

    assert round(active.metadata["stability"], 2) == 0.41
    assert round(active.metadata["style"], 3) == 0.125
    assert round(active.speed, 2) == 0.96
    assert active.metadata["similarity_boost"] == 0.82


def test_pride_is_warmer_and_more_dynamic_but_remains_mary() -> None:
    active = resolve_emotion_voice_settings(
        _base(),
        EmotionalState(primary=Emotion.PRIDE, intensity=1.0),
    )

    assert round(active.metadata["stability"], 2) == 0.39
    assert round(active.metadata["style"], 3) == 0.135
    assert round(active.speed, 3) == 0.985
    assert active.voice == "mary"
