from __future__ import annotations

import base64
from dataclasses import dataclass
from http.client import HTTPConnection
import json
from pathlib import Path
from threading import Thread

from mary.mobile.audio import MobileSpeechAudio, MobileSpeechService
from mary.mobile.server import MaryMobileServer, MobileAuth


@dataclass(frozen=True)
class _Status:
    enabled: bool
    provider: str
    model: str = "test-model"
    voice_id: str | None = "test-voice"
    local: bool = False
    premium: bool = False

    def to_dict(self):
        return {
            "enabled": self.enabled,
            "provider": self.provider,
            "model": self.model,
            "voice_id": self.voice_id,
            "local": self.local,
            "premium": self.premium,
        }


class _Voice:
    def __init__(self):
        self.status = _Status(True, "fake_tts")
        self.calls = 0

    def synthesize(self, text, *, user_text=None, delivery_plan=None):
        self.calls += 1
        audio = b"ID3mary-mobile-test"
        return {
            **self.status.to_dict(),
            "status": "success",
            "format": "mp3",
            "mime_type": "audio/mpeg",
            "audio_base64": base64.b64encode(audio).decode("ascii"),
            "spoken_text": text,
            "delivery_plan": delivery_plan or {},
        }


class _STT:
    def __init__(self):
        self.status = _Status(True, "fake_stt", model="fake-whisper", voice_id=None)
        self.seen_suffix = ""

    def transcribe(self, path):
        self.seen_suffix = Path(path).suffix
        assert Path(path).read_bytes() == b"recorded-audio"
        return "hey mary"


def test_mobile_speech_service_synthesizes_and_caches():
    voice = _Voice()
    service = MobileSpeechService(
        voice_engine=voice,
        stt_engine=_STT(),
        cache_items=4,
        cache_bytes=100_000,
    )

    first = service.synthesize("hello", delivery_plan={"pace": 0.95})
    second = service.synthesize("hello", delivery_plan={"pace": 0.95})

    assert first.successful is True
    assert first.audio == b"ID3mary-mobile-test"
    assert first.mime_type == "audio/mpeg"
    assert first.cached is False
    assert second.cached is True
    assert voice.calls == 1


def test_mobile_speech_service_transcribes_temporary_recording():
    stt = _STT()
    service = MobileSpeechService(
        voice_engine=_Voice(),
        stt_engine=stt,
        stt_max_bytes=10_000,
    )

    result = service.transcribe(
        b"recorded-audio",
        filename="phone.m4a",
        content_type="audio/mp4",
    )

    assert result["status"] == "success"
    assert result["text"] == "hey mary"
    assert result["provider"] == "fake_stt"
    assert stt.seen_suffix == ".m4a"


class _Runtime:
    def status(self):
        return {"name": "Mary"}

    def dashboard_state(self):
        return {}

    def last_turn_trace(self):
        return {}

    def voice_status(self):
        return {
            "tts": {"enabled": True, "provider": "fake_tts"},
            "stt": {"enabled": True, "provider": "fake_stt"},
        }

    def synthesize_speech(self, text, *, user_text=None, delivery_plan=None):
        assert text == "hello from phone"
        assert delivery_plan == {"pace": 0.98}
        return MobileSpeechAudio(
            audio=b"ID3server-audio",
            mime_type="audio/mpeg",
            metadata={
                "status": "success",
                "provider": "fake_tts",
                "model": "flash",
            },
        )

    def transcribe_audio(self, audio, *, filename=None, content_type=None):
        assert audio == b"phone-audio"
        assert filename == "mary-input.m4a"
        assert content_type == "audio/mp4"
        return {"status": "success", "provider": "fake_stt", "text": "voice message"}

    def close(self):
        pass


def _serve(tmp_path):
    (tmp_path / "index.html").write_text("<html>Mary</html>", encoding="utf-8")
    server = MaryMobileServer(
        ("127.0.0.1", 0),
        runtime=_Runtime(),
        static_root=tmp_path,
        auth=MobileAuth("secret", "test", None),
    )
    thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    return server, thread


def test_mobile_tts_endpoint_returns_binary_audio(tmp_path):
    server, thread = _serve(tmp_path)
    try:
        conn = HTTPConnection("127.0.0.1", server.server_address[1], timeout=2)
        body = json.dumps(
            {
                "text": "hello from phone",
                "delivery_plan": {"pace": 0.98},
            }
        ).encode("utf-8")
        conn.request(
            "POST",
            "/api/tts",
            body=body,
            headers={
                "Authorization": "Bearer secret",
                "Content-Type": "application/json",
            },
        )
        response = conn.getresponse()
        audio = response.read()
        assert response.status == 200
        assert response.getheader("Content-Type") == "audio/mpeg"
        assert response.getheader("X-Mary-Voice-Provider") == "fake_tts"
        assert audio == b"ID3server-audio"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_mobile_stt_endpoint_accepts_raw_audio(tmp_path):
    server, thread = _serve(tmp_path)
    try:
        conn = HTTPConnection("127.0.0.1", server.server_address[1], timeout=2)
        conn.request(
            "POST",
            "/api/stt",
            body=b"phone-audio",
            headers={
                "Authorization": "Bearer secret",
                "Content-Type": "audio/mp4",
                "X-Mary-Audio-Filename": "mary-input.m4a",
            },
        )
        response = conn.getresponse()
        payload = json.loads(response.read())
        assert response.status == 200
        assert payload["ok"] is True
        assert payload["text"] == "voice message"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)



def test_mobile_web_uses_server_voice_and_server_stt_routes():
    root = Path(__file__).resolve().parents[2]
    js = (root / "mobile_web" / "app.js").read_text(encoding="utf-8")
    sw = (root / "mobile_web" / "sw.js").read_text(encoding="utf-8")
    manifest = (root / "mobile_web" / "manifest.webmanifest").read_text(encoding="utf-8")
    assert "/api/tts" in js
    assert "/api/stt" in js
    assert "server_preferred_with_device_fallback" in (root / "mary" / "mobile" / "server.py").read_text(encoding="utf-8")
    assert "maryv2-mobile-shell-v3" in sw
    assert "ensureMediaElement" in js
    assert "URL.createObjectURL" in js
    assert "audio.play()" in js
    assert "mary-icon-192.png" in manifest


def test_native_bundle_matches_current_mobile_web():
    root = Path(__file__).resolve().parents[2]
    for name in ("index.html", "style.css", "app.js", "manifest.webmanifest", "sw.js"):
        assert (root / "mobile_native" / "MaryMobile" / "www" / name).read_bytes() == (root / "mobile_web" / name).read_bytes()
