from __future__ import annotations

from mary.desktop.voice import _apply_delivery_plan
from mary.expression.delivery_plan import DeliveryPlan
from mary.voice.text_to_speech import SpeechAudioFormat, VoiceSettings


def test_delivery_plan_overrides_voice_dynamics_without_changing_voice_identity():
    base = VoiceSettings(
        voice="mary-voice",
        speed=0.97,
        output_format=SpeechAudioFormat.MP3,
        metadata={"stability": 0.42, "similarity_boost": 0.82, "style": 0.11},
    )
    plan = DeliveryPlan(profile="playful", pace=1.05, stability=0.30, style=0.15, energy=0.75, warmth=0.7)
    active = _apply_delivery_plan(base, plan)
    assert active.voice == "mary-voice"
    assert active.speed == 1.05
    assert active.metadata["stability"] == 0.30
    assert active.metadata["style"] == 0.15
    assert active.metadata["delivery_profile"] == "playful"
