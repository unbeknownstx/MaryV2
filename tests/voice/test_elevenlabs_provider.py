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


def test_elevenlabs_provider_retries_ssl_handshake_with_verified_tls12() -> None:
    import ssl
    from urllib.error import URLError

    provider = ElevenLabsTextToSpeechProvider(
        api_key="secret-test-key",
        voice_id="mary-voice",
        model_id="eleven_flash_v2_5",
    )

    calls = []

    def fake_urlopen(request, timeout, context=None):
        calls.append({"timeout": timeout, "context": context})
        if len(calls) == 1:
            raise URLError(ssl.SSLError("SSLV3_ALERT_HANDSHAKE_FAILURE"))
        return _FakeResponse(b"tls12-mp3")

    with patch("mary.voice.providers.elevenlabs.urlopen", fake_urlopen):
        speech = provider.synthesize("Hello again")

    assert speech.audio == b"tls12-mp3"
    assert len(calls) == 2
    assert calls[0]["context"] is None
    assert calls[1]["context"] is not None
    assert calls[1]["context"].minimum_version == ssl.TLSVersion.TLSv1_2
    assert calls[1]["context"].maximum_version == ssl.TLSVersion.TLSv1_2


def test_elevenlabs_provider_does_not_bypass_certificate_verification_errors() -> None:
    import ssl
    from urllib.error import URLError

    provider = ElevenLabsTextToSpeechProvider(
        api_key="secret-test-key",
        voice_id="mary-voice",
        model_id="eleven_flash_v2_5",
    )

    error = ssl.SSLCertVerificationError(1, "certificate verify failed")

    with patch(
        "mary.voice.providers.elevenlabs.urlopen",
        side_effect=URLError(error),
    ) as mocked:
        try:
            provider.synthesize("Hello")
        except Exception as exc:
            assert "certificate verify failed" in str(exc).lower()
        else:
            raise AssertionError("Expected synthesis to fail on certificate verification.")

    assert mocked.call_count == 1


def test_elevenlabs_provider_can_return_precise_alignment_without_changing_voice_owner() -> None:
    import base64

    provider = ElevenLabsTextToSpeechProvider(
        api_key="fake-key",
        voice_id="mary-voice",
        model_id="eleven_flash_v2_5",
    )
    payload = {
        "audio_base64": base64.b64encode(b"aligned-mp3").decode("ascii"),
        "normalized_alignment": {
            "characters": ["H", "i", " ", "M", "a", "r", "y"],
            "character_start_times_seconds": [0.0, 0.08, 0.16, 0.20, 0.29, 0.36, 0.43],
            "character_end_times_seconds": [0.08, 0.16, 0.20, 0.29, 0.36, 0.43, 0.52],
        },
    }
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["accept"] = dict(request.header_items()).get("Accept")
        return _FakeResponse(json.dumps(payload).encode("utf-8"))

    with patch("mary.voice.providers.elevenlabs.urlopen", fake_urlopen):
        speech = provider.synthesize(
            "Hi Mary",
            settings=VoiceSettings(
                voice="mary-voice",
                output_format=SpeechAudioFormat.MP3,
                metadata={"with_timestamps": True},
            ),
        )

    assert speech.audio == b"aligned-mp3"
    assert "/with-timestamps" in captured["url"]
    assert captured["accept"] == "application/json"
    alignment = speech.metadata["alignment"]
    assert alignment["normalized"] is True
    assert alignment["words"][0]["text"] == "Hi"
    assert alignment["words"][1]["text"] == "Mary"
    assert alignment["characters"][-1]["end_seconds"] == 0.52
    assert speech.metadata["alignment_source"] == "elevenlabs_tts_timestamps"
