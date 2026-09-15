from __future__ import annotations

import json

from mary.desktop.stt import DesktopSpeechToText, _safe_specialist_endpoint


def test_specialist_endpoint_rejects_remote_plain_http() -> None:
    assert _safe_specialist_endpoint("http://example.com/transcribe") == ""
    assert _safe_specialist_endpoint("http://127.0.0.1:9010/transcribe")
    assert _safe_specialist_endpoint("https://asr.example.com/transcribe")


def test_qwen_specialist_bridge_uses_fixed_configured_endpoint(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("MARY_QWEN_ASR_ENDPOINT", "http://127.0.0.1:9010/transcribe")
    stt = DesktopSpeechToText(provider="qwen3_asr", model="qwen3-asr", language="en", api_key=None)
    assert stt.enabled is True
    assert stt.status.local is True

    audio = tmp_path / "sample.wav"
    audio.write_bytes(b"RIFF" + b"\x00" * 128)

    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self, _limit):
            return json.dumps({"text": "hello from qwen"}).encode("utf-8")

    def fake_urlopen(request, timeout=0):
        assert request.full_url == "http://127.0.0.1:9010/transcribe"
        assert timeout == 45
        return Response()

    monkeypatch.setattr("mary.desktop.stt.urlopen", fake_urlopen)
    assert stt.transcribe(audio) == "hello from qwen"


def test_fluid_audio_alias_uses_fluid_endpoint(monkeypatch) -> None:
    monkeypatch.setenv("MARY_FLUID_AUDIO_ENDPOINT", "http://localhost:9020/transcribe")
    stt = DesktopSpeechToText(provider="fluid_audio", model="fluid-audio", language="en", api_key=None)
    assert stt.enabled is True
    assert stt.status.provider == "fluid_audio"
