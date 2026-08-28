from __future__ import annotations

from mary.desktop.voice import DesktopVoiceEngine, DesktopVoiceStatus
from mary.expression.delivery_plan import DeliveryPlan
from mary.voice.text_to_speech import (
    SpeechAudio,
    SpeechAudioFormat,
    TextToSpeechProvider,
    TextToSpeechService,
    VoiceSettings,
)


class RecordingProvider(TextToSpeechProvider):
    name = "recording"

    def __init__(self) -> None:
        self.settings: VoiceSettings | None = None

    def synthesize(self, text: str, *, settings: VoiceSettings | None = None) -> SpeechAudio:
        self.settings = settings
        return SpeechAudio(
            audio=b"fake-mp3",
            format=SpeechAudioFormat.MP3,
            text=text,
            provider=self.name,
            voice=settings.voice if settings else None,
        )


def _engine(provider: RecordingProvider) -> DesktopVoiceEngine:
    base = VoiceSettings(
        voice="mary",
        speed=1.0,
        output_format=SpeechAudioFormat.MP3,
        metadata={"stability": 0.50, "similarity_boost": 0.75, "style": 0.0},
    )
    return DesktopVoiceEngine(
        service=TextToSpeechService(provider, settings=base),
        status=DesktopVoiceStatus(True, "recording", "mary", "fake"),
        base_settings=base,
    )


def test_character_performance_delivery_is_on_by_default_even_when_dynamic_emotion_is_off(monkeypatch):
    monkeypatch.setenv("MARY_TTS_DYNAMIC_DELIVERY", "false")
    monkeypatch.delenv("MARY_TTS_PERFORMANCE_DELIVERY", raising=False)
    provider = RecordingProvider()
    engine = _engine(provider)

    payload = engine.synthesize(
        "Of course you did.",
        delivery_plan=DeliveryPlan(
            profile="teasing",
            pace=1.07,
            stability=0.41,
            style=0.08,
            energy=0.66,
            warmth=0.64,
        ),
    )

    assert payload["status"] == "success"
    assert provider.settings is not None
    assert provider.settings.speed == 1.07
    assert provider.settings.metadata["stability"] == 0.41
    assert provider.settings.metadata["style"] == 0.08
    assert provider.settings.metadata["delivery_profile"] == "teasing"


def test_character_performance_delivery_can_be_explicitly_disabled(monkeypatch):
    monkeypatch.setenv("MARY_TTS_DYNAMIC_DELIVERY", "false")
    monkeypatch.setenv("MARY_TTS_PERFORMANCE_DELIVERY", "false")
    provider = RecordingProvider()
    engine = _engine(provider)

    engine.synthesize(
        "Of course you did.",
        delivery_plan=DeliveryPlan(profile="teasing", pace=1.07, stability=0.41, style=0.08),
    )

    assert provider.settings is not None
    assert provider.settings.speed == 1.0
    assert provider.settings.metadata["stability"] == 0.50
    assert provider.settings.metadata["style"] == 0.0
    assert "delivery_profile" not in provider.settings.metadata
