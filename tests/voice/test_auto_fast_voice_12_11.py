from mary.desktop.voice import DesktopVoiceEngine


def test_auto_fast_prefers_configured_elevenlabs(monkeypatch):
    monkeypatch.setenv("MARY_TTS_PROVIDER", "auto_fast")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key-not-used")
    monkeypatch.setenv("MARY_ELEVENLABS_VOICE_ID", "test-voice")
    monkeypatch.setenv("MARY_ELEVENLABS_MODEL", "eleven_flash_v2_5")
    voice = DesktopVoiceEngine.from_environment()
    assert voice.status.enabled is True
    assert voice.status.provider == "elevenlabs"
    assert voice.status.premium is True
    assert voice.status.model == "eleven_flash_v2_5"


def test_auto_fast_stays_optional_without_cloud_credentials(monkeypatch):
    monkeypatch.setenv("MARY_TTS_PROVIDER", "auto_fast")
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.delenv("MARY_ELEVENLABS_VOICE_ID", raising=False)
    voice = DesktopVoiceEngine.from_environment()
    # Non-Windows test hosts have no automatic local SAPI. The important
    # contract is that missing cloud credentials do not crash or force cloud.
    assert voice.status.provider in {"local_first", "windows_sapi", "piper"}
    assert voice.status.premium is False
