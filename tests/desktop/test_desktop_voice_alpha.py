from __future__ import annotations

from pathlib import Path


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
    assert "new Audio(`data:${mimeType};base64,${voice.audio_base64}`)" in source


def test_desktop_voice_uses_calibrated_mary_settings_from_environment() -> None:
    source = (_root() / "mary" / "desktop" / "voice.py").read_text(encoding="utf-8")
    assert 'MARY_TTS_STABILITY", 0.42' in source
    assert 'MARY_TTS_SIMILARITY", 0.82' in source
    assert 'MARY_TTS_STYLE", 0.11' in source
    assert 'MARY_TTS_SPEED", 0.97' in source
    assert 'MARY_TTS_SPEAKER_BOOST", True' in source


def test_desktop_voice_renders_spoken_text_separately_from_gui_text() -> None:
    source = (_root() / "mary" / "desktop" / "voice.py").read_text(encoding="utf-8")
    renderer = (_root() / "mary" / "voice" / "speech_renderer.py").read_text(encoding="utf-8")
    assert "spoken_text = self.renderer.render" in source
    assert '"spoken_text": spoken_text' in source
    assert "class SpeechRenderer" in renderer
