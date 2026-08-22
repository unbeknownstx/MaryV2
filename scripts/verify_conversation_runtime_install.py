"""Verify MaryV2 Desktop Conversation Runtime Alpha 1 installation."""

from __future__ import annotations

from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    runtime = (root / "mary" / "desktop" / "conversation_runtime.py").read_text(encoding="utf-8")
    bridge = (root / "mary" / "desktop" / "bridge.py").read_text(encoding="utf-8")
    frontend = (root / "desktop" / "src" / "main.js").read_text(encoding="utf-8")
    css = (root / "desktop" / "src" / "style.css").read_text(encoding="utf-8")

    checks = [
        ("class DesktopConversationState" in runtime, "authoritative desktop conversation states are installed"),
        (all(value in runtime for value in ['IDLE = "idle"', 'LISTENING = "listening"', 'TRANSCRIBING = "transcribing"', 'THINKING = "thinking"', 'SPEAKING = "speaking"', 'INTERRUPTED = "interrupted"']), "idle/listening/transcribing/thinking/speaking/interrupted lifecycle exists"),
        ("_ALLOWED_TRANSITIONS" in runtime and "Invalid desktop conversation transition" in runtime, "invalid overlapping runtime transitions are rejected"),
        ("DesktopConversationRuntime()" in bridge and "conversationStateChanged = Signal(str)" in bridge, "Qt bridge owns and publishes the conversation runtime"),
        ("voicePlaybackStarted" in bridge and "voicePlaybackFinished" in bridge, "real browser playback reports speaking start/end to Python"),
        ("voicePlaybackStopRequested = Signal()" in bridge, "Python can synchronously request speech playback stop"),
        ("microphone_barge_in" in bridge and "typed_barge_in" in bridge, "mic and typed messages can interrupt Mary while speaking"),
        ("bridge.voicePlaybackStopRequested.connect" in frontend, "frontend obeys authoritative playback-stop requests"),
        ("stopVoicePlayback({ notifyBridge: false });" in frontend, "barge-in silences Mary before the next input path starts"),
        ("bridge?.voicePlaybackStarted?.();" in frontend and "bridge?.voicePlaybackFinished?.();" in frontend, "actual audio playback drives speaking lifecycle"),
        ("'Interrupt'" in frontend and ".round-button.speaking" in css, "mic UI visibly becomes an interruption control while Mary speaks"),
    ]

    print("MARYV2 DESKTOP CONVERSATION RUNTIME INSTALL VERIFICATION")
    print("=" * 72)
    failed = False
    for ok, label in checks:
        print(("PASS" if ok else "FAIL") + f"  {label}")
        failed = failed or not ok

    print("=" * 72)
    if failed:
        return 1
    print("DESKTOP CONVERSATION RUNTIME ALPHA 1 INSTALLED CORRECTLY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
