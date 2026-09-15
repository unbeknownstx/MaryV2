from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import mary.desktop.voice as voice_module
from mary.desktop.voice import DesktopVoiceEngine


def _enable_macos(monkeypatch) -> None:
    monkeypatch.setattr(voice_module.sys, "platform", "darwin")
    monkeypatch.setattr(
        voice_module.shutil,
        "which",
        lambda name: f"/usr/bin/{name}" if name in {"say", "afconvert"} else None,
    )
    monkeypatch.delenv("MARY_PIPER_EXECUTABLE", raising=False)
    monkeypatch.delenv("MARY_PIPER_MODEL", raising=False)
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.delenv("MARY_ELEVENLABS_VOICE_ID", raising=False)


def test_macos_local_first_uses_builtin_speech_when_piper_is_not_configured(monkeypatch) -> None:
    _enable_macos(monkeypatch)
    monkeypatch.setenv("MARY_TTS_PROVIDER", "local_first")
    monkeypatch.setenv("MARY_MACOS_TTS_VOICE", "Samantha")
    engine = DesktopVoiceEngine.from_environment()
    assert engine.status.enabled is True
    assert engine.status.provider == "macos_say"
    assert engine.status.voice_id == "Samantha"
    assert engine.status.local is True
    assert engine.local_engine == "macos_say"


def test_macos_builtin_speech_returns_the_same_wav_contract_as_windows(monkeypatch) -> None:
    _enable_macos(monkeypatch)
    monkeypatch.setenv("MARY_TTS_PROVIDER", "macos_say")

    def fake_run(command, **_kwargs):
        executable = Path(command[0]).name
        if executable == "say":
            Path(command[command.index("-o") + 1]).write_bytes(b"FORM" + b"0" * 80)
        elif executable == "afconvert":
            Path(command[-1]).write_bytes(b"RIFF" + b"0" * 80)
        else:
            raise AssertionError(f"unexpected executable: {executable}")
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(voice_module.subprocess, "run", fake_run)
    payload = DesktopVoiceEngine.from_environment().synthesize("Hello from Mary")
    assert payload["status"] == "success"
    assert payload["provider"] == "macos_say"
    assert payload["format"] == "wav"
    assert payload["mime_type"] == "audio/wav"
    assert payload["audio_size"] > 44
