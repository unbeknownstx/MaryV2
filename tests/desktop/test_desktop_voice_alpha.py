from __future__ import annotations

from pathlib import Path
import re


def _root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_desktop_voice_is_explicitly_opt_in_and_provider_independent() -> None:
    source = (_root() / "mary" / "desktop" / "voice.py").read_text(encoding="utf-8")
    assert 'os.getenv("MARY_TTS_PROVIDER", "off")' in source
    assert "create_tts_service" in source
    assert "DesktopVoiceEngine" in source
    assert "audio_base64" in source


def test_desktop_turn_payload_carries_voice_without_exposing_credentials() -> None:
    source = (_root() / "mary" / "desktop" / "bridge.py").read_text(encoding="utf-8")
    frontend = (_root() / "desktop" / "src" / "main.js").read_text(encoding="utf-8")
    assert "voice: dict[str, Any]" in source
    assert "voice=voice_payload" in source
    assert "Voice synthesis is also best-effort" in source
    assert "ELEVENLABS_API_KEY" not in frontend
    assert "playVoice(payload.voice || {})" in frontend


def test_qt_allows_programmatic_voice_playback_after_async_response() -> None:
    source = (_root() / "mary" / "desktop" / "window.py").read_text(encoding="utf-8")
    assert "PlaybackRequiresUserGesture" in source
    assert "False" in source


def test_frontend_marks_mary_speaking_during_audio_playback() -> None:
    source = (_root() / "desktop" / "src" / "main.js").read_text(encoding="utf-8")
    assert "function playVoice(voice = {})" in source
    assert "Mary speaking" in source
    assert "function audioSourceFromVoice(voice = {})" in source
    assert "voice.audio_url" in source
    assert "URL.createObjectURL" in source
    assert "voicePlaybackStarted" in source


def test_desktop_voice_uses_calibrated_mary_settings_from_environment() -> None:
    source = (_root() / "mary" / "desktop" / "voice.py").read_text(encoding="utf-8")
    assert 'MARY_TTS_STABILITY", 0.50' in source
    assert 'MARY_TTS_SIMILARITY", 0.75' in source
    assert 'MARY_TTS_STYLE", 0.0' in source
    assert 'MARY_TTS_SPEED", 1.0' in source
    assert 'MARY_TTS_SPEAKER_BOOST", False' in source


def test_desktop_voice_always_renders_spoken_text_for_transcript_sync() -> None:
    source = (_root() / "mary" / "desktop" / "voice.py").read_text(encoding="utf-8")
    renderer = (_root() / "mary" / "voice" / "speech_renderer.py").read_text(encoding="utf-8")
    assert "def render_text(" in source
    assert "spoken_text = self.render_text" in source
    assert '"spoken_text": spoken_text' in source
    assert "class SpeechRenderer" in renderer


def test_desktop_voice_passes_creator_turn_context_into_speech_renderer() -> None:
    voice = (_root() / "mary" / "desktop" / "voice.py").read_text(encoding="utf-8")
    bridge = (_root() / "mary" / "desktop" / "bridge.py").read_text(encoding="utf-8")
    assert "user_text: str | None = None" in voice
    assert "user_text=user_text" in voice
    assert "user_text=self.text" in bridge


def test_desktop_transcript_matches_the_exact_spoken_text() -> None:
    bridge = (_root() / "mary" / "desktop" / "bridge.py").read_text(encoding="utf-8")
    frontend = (_root() / "desktop" / "src" / "main.js").read_text(encoding="utf-8")

    assert "canonical_text: str" in bridge
    assert '"canonical_text": self.canonical_text' in bridge
    assert re.search(r'spoken_text\s*=\s*str\(\s*voice_payload\.get\("spoken_text"\)\s*or\s*""\s*\)\.strip\(\)', bridge)
    assert "display_text = response_text or spoken_text" in bridge
    assert "text=display_text" in bridge
    assert "canonical_text=response_text" in bridge
    # Frontend's normal Mary bubble already displays payload.text, which is
    # now the speech-synchronized transcript.
    assert "appendMessage('Mary', payload.text || '[No response]', 'mary')" in frontend


def test_voice_failure_still_preserves_speech_synchronized_transcript() -> None:
    bridge = (_root() / "mary" / "desktop" / "bridge.py").read_text(encoding="utf-8")
    voice = (_root() / "mary" / "desktop" / "voice.py").read_text(encoding="utf-8")

    assert "self.voice.render_text(" in bridge
    assert '"spoken_text": spoken_text' in bridge
    assert '"status": "disabled",' in voice
    assert '"spoken_text": spoken_text' in voice

def test_remote_core_voice_prefers_core_and_falls_back_locally():
    from mary.desktop.voice import (
        DesktopVoiceEngine,
        DesktopVoiceStatus,
        RemoteCoreVoiceEngine,
    )

    class Gateway:
        def __init__(self):
            self.fail = False

        def voice_status(self):
            return {
                "tts": {
                    "enabled": True,
                    "provider": "core-elevenlabs",
                    "model": "flash",
                    "premium": True,
                }
            }

        def voice_synthesize(self, text, *, user_text=None, delivery_plan=None):
            if self.fail:
                raise RuntimeError("temporary core voice failure")
            return {
                "status": "success",
                "provider": "core-elevenlabs",
                "model": "flash",
                "audio_base64": "SUQz",
                "mime_type": "audio/mpeg",
                "spoken_text": text,
            }

    class LocalFallback(DesktopVoiceEngine):
        def __init__(self):
            super().__init__(
                status=DesktopVoiceStatus(
                    True,
                    "local-test",
                    model="local",
                    local=True,
                )
            )

        def synthesize(self, text, **kwargs):
            return {
                **self.status.to_dict(),
                "status": "success",
                "format": "wav",
                "mime_type": "audio/wav",
                "audio_base64": "UklGRg==",
                "audio_size": 4,
                "spoken_text": text,
            }

    gateway = Gateway()
    engine = RemoteCoreVoiceEngine(gateway, fallback=LocalFallback())
    core = engine.synthesize("hello")
    assert core["provider"] == "core-elevenlabs"
    assert core["authority"] == "remote_mary_core"

    gateway.fail = True
    fallback = engine.synthesize("hello")
    assert fallback["provider"] == "local-test"
    assert fallback["authority"] == "desktop_local_fallback"

def test_remote_core_voice_treats_configured_but_unavailable_as_degraded():
    from mary.desktop.voice import (
        DesktopVoiceEngine,
        DesktopVoiceStatus,
        RemoteCoreVoiceEngine,
    )

    class Gateway:
        def voice_status(self):
            return {
                "tts": {
                    "enabled": True,
                    "configured": True,
                    "server_available": False,
                    "degraded": True,
                    "provider": "elevenlabs",
                }
            }

        def voice_synthesize(self, *args, **kwargs):
            raise AssertionError("degraded Core voice should not be called")

    class LocalFallback(DesktopVoiceEngine):
        def __init__(self):
            super().__init__(
                status=DesktopVoiceStatus(
                    True,
                    "local-test",
                    model="local",
                    local=True,
                )
            )

        def synthesize(self, text, **kwargs):
            return {
                **self.status.to_dict(),
                "status": "success",
                "spoken_text": text,
            }

    engine = RemoteCoreVoiceEngine(Gateway(), fallback=LocalFallback())

    assert engine.status.provider == "local-test"
    assert engine._core_enabled is False

    result = engine.synthesize("hello")
    assert result["provider"] == "local-test"
    assert result["authority"] == "desktop_local_fallback"

