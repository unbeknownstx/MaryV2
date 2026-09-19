from __future__ import annotations

import io
import json

import pytest

from mary.desktop.voice import DesktopVoiceEngine
from mary.voice import SpeechAudioFormat, VoiceSettings
from mary.voice.providers import GPTSoVITSLocalTextToSpeechProvider
import mary.voice.providers.gpt_sovits as gpt_sovits_module


class _Headers(dict):
    def get(self, key, default=None):
        return super().get(key, default)


class _Response:
    def __init__(self, audio: bytes = b"RIFFfake-wave") -> None:
        self.audio = audio
        self.headers = _Headers({"Content-Type": "audio/wav"})

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.audio


def test_gpt_sovits_provider_is_loopback_only():
    with pytest.raises(ValueError, match="loopback-only"):
        GPTSoVITSLocalTextToSpeechProvider(
            base_url="https://example.com:9880",
            ref_audio_path="mary.wav",
        )

    provider = GPTSoVITSLocalTextToSpeechProvider(
        base_url="http://127.0.0.1:9880",
        ref_audio_path="mary.wav",
    )
    assert provider.base_url == "http://127.0.0.1:9880"


def test_gpt_sovits_provider_uses_official_v2_tts_shape(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return _Response()

    monkeypatch.setattr(gpt_sovits_module, "urlopen", fake_urlopen)
    provider = GPTSoVITSLocalTextToSpeechProvider(
        base_url="http://localhost:9880",
        ref_audio_path="mary-reference.wav",
        prompt_text="This is Mary's reference line.",
        text_lang="en",
        prompt_lang="en",
    )
    speech = provider.synthesize(
        "Hey, I'm here.",
        settings=VoiceSettings(
            speed=0.95,
            output_format=SpeechAudioFormat.WAV,
        ),
    )

    assert captured["url"] == "http://localhost:9880/tts"
    assert captured["body"]["text"] == "Hey, I'm here."
    assert captured["body"]["text_lang"] == "en"
    assert captured["body"]["ref_audio_path"] == "mary-reference.wav"
    assert captured["body"]["prompt_lang"] == "en"
    assert captured["body"]["prompt_text"] == "This is Mary's reference line."
    assert captured["body"]["speed_factor"] == pytest.approx(0.95)
    assert captured["body"]["media_type"] == "wav"
    assert captured["body"]["streaming_mode"] is False
    assert speech.is_successful
    assert speech.format == SpeechAudioFormat.WAV
    assert speech.provider == "gpt_sovits"


def test_desktop_can_explicitly_select_local_gpt_sovits(monkeypatch):
    monkeypatch.setenv("MARY_TTS_PROVIDER", "gpt_sovits")
    monkeypatch.setenv("MARY_GPT_SOVITS_URL", "http://127.0.0.1:9880")
    monkeypatch.setenv("MARY_GPT_SOVITS_REF_AUDIO", "C:/MaryVoice/reference.wav")
    monkeypatch.setenv("MARY_GPT_SOVITS_VOICE_LABEL", "Mary local")
    monkeypatch.setenv("MARY_GPT_SOVITS_TEXT_LANG", "en")
    monkeypatch.setenv("MARY_GPT_SOVITS_PROMPT_LANG", "en")

    engine = DesktopVoiceEngine.from_environment()

    assert engine.status.enabled is True
    assert engine.status.provider == "gpt_sovits"
    assert engine.status.local is True
    assert engine.status.premium is False
    assert engine.base_settings.output_format == SpeechAudioFormat.WAV


def test_local_first_only_prefers_gpt_sovits_when_explicitly_enabled(monkeypatch):
    monkeypatch.setenv("MARY_TTS_PROVIDER", "local_first")
    monkeypatch.setenv("MARY_GPT_SOVITS_URL", "http://127.0.0.1:9880")
    monkeypatch.setenv("MARY_GPT_SOVITS_REF_AUDIO", "mary.wav")
    monkeypatch.setenv("MARY_GPT_SOVITS_ENABLED", "true")

    engine = DesktopVoiceEngine.from_environment()

    assert engine.status.provider == "gpt_sovits"
    assert engine.status.local is True
