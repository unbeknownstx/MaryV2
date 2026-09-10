from __future__ import annotations

from pathlib import Path
import re
from types import SimpleNamespace

import mary.desktop.stt as stt_module
from mary.desktop.stt import DesktopSpeechToText


class _FakeTranscriptions:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(text="  Hey Mary, can you hear me?  ")


class _FakeGroq:
    def __init__(self) -> None:
        self.transcriptions = _FakeTranscriptions()
        self.audio = SimpleNamespace(transcriptions=self.transcriptions)


def test_groq_stt_uses_fast_whisper_and_preserves_mary_names(monkeypatch, tmp_path: Path) -> None:
    created: list[_FakeGroq] = []

    def factory(_api_key: str):
        client = _FakeGroq()
        created.append(client)
        return client

    monkeypatch.setattr(stt_module, "_create_groq_client", factory)

    audio = tmp_path / "speech.m4a"
    audio.write_bytes(b"fake-audio")

    stt = DesktopSpeechToText(
        provider="groq",
        model="whisper-large-v3-turbo",
        language="en",
        api_key="test-key",
    )

    text = stt.transcribe(audio)

    assert text == "Hey Mary, can you hear me?"
    call = created[0].transcriptions.calls[0]
    assert call["model"] == "whisper-large-v3-turbo"
    assert call["response_format"] == "json"
    assert call["language"] == "en"
    assert call["temperature"] == 0.0
    assert "Unbe" in call["prompt"]
    assert "Mary Cosma" in call["prompt"]
    assert "MaryV2" in call["prompt"]


def test_desktop_microphone_is_user_initiated_and_transcript_reuses_send_message_path() -> None:
    root = Path(__file__).resolve().parents[2]
    bridge = (root / "mary" / "desktop" / "bridge.py").read_text(encoding="utf-8")
    microphone = (root / "mary" / "desktop" / "microphone.py").read_text(encoding="utf-8")
    frontend = (root / "desktop" / "src" / "main.js").read_text(encoding="utf-8")

    assert "def startListening" in bridge
    assert "def stopListening" in bridge
    assert re.search(r"self\.transcriptionReady\.emit\(\s*value\s*\)", bridge)
    assert "QMediaDevices.audioInputs()" in microphone
    assert "QMediaRecorder" in microphone
    assert "MARY_AUDIO_INPUT_DEVICE" in microphone
    assert "QMediaFormat.FileFormat.Wave" in microphone
    assert "setAudioSampleRate(16000)" in microphone
    assert "setAudioChannelCount(1)" in microphone
    assert "def sendVoiceMessage" in bridge
    assert '"voice_input": bool(self.voice_input)' in bridge
    assert "bridge.startListening()" in frontend
    assert "bridge.stopListening()" in frontend
    assert "bridge.sendVoiceMessage(transcript)" in frontend
    assert "bridge.sendMessage(transcript)" in frontend
    assert "stopVoicePlayback({ notifyBridge: false });" in frontend
