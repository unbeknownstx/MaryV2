"""Verify MaryV2 Desktop Voice Input Alpha 1 installation."""

from __future__ import annotations

from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    bridge = (root / "mary" / "desktop" / "bridge.py").read_text(encoding="utf-8")
    microphone = (root / "mary" / "desktop" / "microphone.py").read_text(encoding="utf-8")
    stt = (root / "mary" / "desktop" / "stt.py").read_text(encoding="utf-8")
    frontend = (root / "desktop" / "src" / "main.js").read_text(encoding="utf-8")
    html = (root / "desktop" / "index.html").read_text(encoding="utf-8")

    bridge_compact = " ".join(bridge.split())
    checks = [
        ("QMediaCaptureSession" in microphone and "QAudioInput" in microphone, "native Qt microphone capture is installed"),
        ("QMediaDevices.audioInputs()" in microphone, "microphone availability is checked before recording"),
        ('whisper-large-v3-turbo' in stt, "Groq Whisper Large V3 Turbo is the default STT model"),
        ("client.audio.transcriptions.create" in stt, "recorded audio is transcribed through Groq STT"),
        ("timeout=20.0" in stt and "max_retries=0" in stt, "speech transcription has bounded provider latency"),
        ("def startListening" in bridge and "def stopListening" in bridge, "desktop bridge exposes push-to-talk controls"),
        ("self.transcriptionReady.emit( value )" in bridge_compact or "self.transcriptionReady.emit(value)" in bridge_compact, "successful transcription returns text to the desktop"),
        ('id="mic-button"' in html, "desktop microphone button is installed"),
        ("stopVoicePlayback({ notifyBridge: false });" in frontend, "Mary's own TTS is stopped before microphone capture"),
        ("bridge.sendMessage(transcript)" in frontend, "spoken transcript enters the canonical Mary conversation path"),
    ]

    print("MARYV2 DESKTOP VOICE-INPUT INSTALL VERIFICATION")
    print("=" * 72)
    failed = False
    for ok, label in checks:
        print(("PASS" if ok else "FAIL") + f"  {label}")
        failed = failed or not ok

    print("=" * 72)
    if failed:
        return 1
    print("DESKTOP VOICE-INPUT ALPHA 1 INSTALLED CORRECTLY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
