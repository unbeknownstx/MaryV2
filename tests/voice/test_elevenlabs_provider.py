from __future__ import annotations

import json
from unittest.mock import patch

from mary.voice import SpeechAudioFormat, VoiceSettings
from mary.voice.providers.elevenlabs import ElevenLabsTextToSpeechProvider


class _FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return self.payload


def test_elevenlabs_provider_uses_documented_tts_endpoint_without_sdk() -> None:
    provider = ElevenLabsTextToSpeechProvider(
        api_key="secret-test-key",
        voice_id="mary-voice",
        model_id="eleven_flash_v2_5",
    )

    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return _FakeResponse(b"fake-mp3")

    with patch("mary.voice.providers.elevenlabs.urlopen", fake_urlopen):
        speech = provider.synthesize(
            "Hello Unbe",
            settings=VoiceSettings(
                voice="mary-voice",
                speed=0.97,
                output_format=SpeechAudioFormat.MP3,
                metadata={
                    "stability": 0.42,
                    "similarity_boost": 0.82,
                    "style": 0.11,
                    "use_speaker_boost": True,
                },
            ),
        )

    assert speech.audio == b"fake-mp3"
    assert speech.format == SpeechAudioFormat.MP3
    assert speech.provider == "elevenlabs"
    assert "/text-to-speech/mary-voice" in captured["url"]
    assert "output_format=mp3_44100_128" in captured["url"]
    assert captured["body"] == {
        "text": "Hello Unbe",
        "model_id": "eleven_flash_v2_5",
        "voice_settings": {
            "stability": 0.42,
            "similarity_boost": 0.82,
            "style": 0.11,
            "speed": 0.97,
            "use_speaker_boost": True,
        },
    }
    assert captured["timeout"] == 20.0
    assert "secret-test-key" not in captured["url"]
