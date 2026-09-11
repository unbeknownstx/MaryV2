from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from mary.protocol.server import create_app


class _SpeechAudio:
    def __init__(self):
        self.audio = b"ID3mary-core-elevenlabs-test"
        self.mime_type = "audio/mpeg"
        self.cached = False
        self.metadata = {
            "status": "success",
            "provider": "elevenlabs",
            "model": "eleven_flash_v2_5",
            "voice_id": "private-voice-id-must-not-be-header",
        }


class _VoiceCore:
    instance_id = "voice-core-test"
    started_monotonic = 0.0

    def __init__(self):
        self.calls = []

    def health(self):
        return {
            "ok": True,
            "service": "mary-core",
            "architecture": "13.3",
            "instance_id": self.instance_id,
        }

    def voice_status(self):
        return {
            "tts": {
                "enabled": True,
                "provider": "elevenlabs",
                "model": "eleven_flash_v2_5",
                "server_available": True,
            },
            "stt": {
                "enabled": False,
                "provider": "disabled",
                "server_available": False,
            },
        }

    def voice_synthesize(self, text, *, user_text=None, delivery_plan=None):
        self.calls.append((text, user_text, dict(delivery_plan or {})))
        return _SpeechAudio()

    def close(self):
        return None


def test_core_voice_status_and_synthesis_are_authenticated_and_binary(monkeypatch):
    monkeypatch.setenv("MARY_CORE_TOKEN", "core-secret")
    core = _VoiceCore()

    with TestClient(create_app(core)) as client:
        assert client.get("/v1/voice/status").status_code == 401

        headers = {"Authorization": "Bearer core-secret"}
        status = client.get("/v1/voice/status", headers=headers)
        assert status.status_code == 200
        assert status.json()["tts"]["provider"] == "elevenlabs"

        response = client.post(
            "/v1/voice/synthesize",
            headers=headers,
            json={
                "text": "hello from native iphone",
                "user_text": "hey Mary",
                "delivery_plan": {"pace": 0.98},
            },
        )
        assert response.status_code == 200
        assert response.content == b"ID3mary-core-elevenlabs-test"
        assert response.headers["content-type"].startswith("audio/mpeg")
        assert response.headers["x-mary-voice-provider"] == "elevenlabs"
        assert response.headers["x-mary-voice-model"] == "eleven_flash_v2_5"
        assert "voice-id" not in str(response.headers).lower()
        assert core.calls == [
            ("hello from native iphone", "hey Mary", {"pace": 0.98})
        ]


def test_core_voice_synthesis_rejects_empty_or_oversized_payload(monkeypatch):
    monkeypatch.setenv("MARY_CORE_TOKEN", "core-secret")
    core = _VoiceCore()
    headers = {"Authorization": "Bearer core-secret"}

    with TestClient(create_app(core)) as client:
        empty = client.post("/v1/voice/synthesize", headers=headers, json={"text": ""})
        assert empty.status_code == 422

        oversized = client.post(
            "/v1/voice/synthesize",
            headers={**headers, "Content-Type": "application/json"},
            content=b'{"text":"' + (b"x" * 40_000) + b'"}',
        )
        assert oversized.status_code == 413
