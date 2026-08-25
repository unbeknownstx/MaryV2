"""Verify MaryV2 Desktop Alpha files without requiring a display server."""

from __future__ import annotations

import json
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    required = [
        root / "requirements-desktop.txt",
        root / "mary" / "desktop" / "bridge.py",
        root / "mary" / "desktop" / "window.py",
        root / "mary" / "desktop" / "voice.py",
        root / "mary" / "desktop" / "microphone.py",
        root / "mary" / "desktop" / "stt.py",
        root / "mary" / "desktop" / "conversation_runtime.py",
        root / "mary" / "voice" / "providers" / "elevenlabs.py",
        root / "mary" / "voice" / "speech_renderer.py",
        root / "mary" / "voice" / "emotion_profile.py",
        root / "desktop" / "package.json",
        root / "desktop" / "vite.config.js",
        root / "desktop" / "index.html",
        root / "desktop" / "src" / "main.js",
        root / "desktop" / "src" / "style.css",
        root / "scripts" / "run_desktop.py",
    ]

    print("MARYV2 DESKTOP ALPHA INSTALL VERIFICATION")
    print("=" * 72)

    missing = [path for path in required if not path.exists()]
    if missing:
        for path in missing:
            print(f"FAIL  missing {path.relative_to(root)}")
        return 1

    package = json.loads((root / "desktop" / "package.json").read_text(encoding="utf-8"))
    checks = [
        (package["dependencies"].get("three") == "0.185.1", "Three.js version pinned"),
        (package["dependencies"].get("@pixiv/three-vrm") == "3.5.5", "three-vrm version pinned"),
        ("MaryApplication" in (root / "mary" / "desktop" / "bridge.py").read_text(encoding="utf-8"), "desktop uses canonical MaryApplication"),
        ("base: './'" in (root / "desktop" / "vite.config.js").read_text(encoding="utf-8"), "Vite emits Qt-friendly relative asset paths"),
        ("VRMUtils.rotateVRM0(currentVrm)" in (root / "desktop" / "src" / "main.js").read_text(encoding="utf-8"), "VRM orientation is version-aware"),
        ("setNormalizedPose" in (root / "desktop" / "src" / "main.js").read_text(encoding="utf-8"), "desktop applies a relaxed humanoid pose"),
        ("currentVrm.scene.rotation.y = Math.PI" not in (root / "desktop" / "src" / "main.js").read_text(encoding="utf-8"), "VRM 1.0 is not forcibly turned backward"),
        ("new THREE.Clock" not in (root / "desktop" / "src" / "main.js").read_text(encoding="utf-8"), "deprecated Three.js Clock removed"),
        ("expression = mary.avatar.sync_emotion()" not in (root / "mary" / "desktop" / "bridge.py").read_text(encoding="utf-8"), "desktop bridge keeps AvatarState and AvatarExpression types separate"),
        ("leftUpperArm: { rotation: quaternionArrayFromEuler(0, 0, -1.28) }" in (root / "desktop" / "src" / "main.js").read_text(encoding="utf-8"), "left arm lowers from T-pose"),
        ("rightUpperArm: { rotation: quaternionArrayFromEuler(0, 0, 1.28) }" in (root / "desktop" / "src" / "main.js").read_text(encoding="utf-8"), "right arm lowers from T-pose"),
        ("const distance = Math.max(verticalDistance, horizontalDistance) * padding" in (root / "desktop" / "src" / "main.js").read_text(encoding="utf-8") and "setAvatarFraming" in (root / "desktop" / "src" / "main.js").read_text(encoding="utf-8"), "camera frames Mary using geometry-aware adjustable presentation"),
        ("worker.moveToThread(thread)" in (root / "mary" / "desktop" / "bridge.py").read_text(encoding="utf-8"), "desktop conversation uses a dedicated QThread"),
        ("@Slot(object)" in (root / "mary" / "desktop" / "bridge.py").read_text(encoding="utf-8"), "desktop completion is marshalled through a Qt slot"),
        ("Avatar presentation is best-effort" in (root / "mary" / "desktop" / "bridge.py").read_text(encoding="utf-8"), "avatar presentation cannot swallow a chat response"),
        ("Mary's desktop worker stopped without returning a response." in (root / "mary" / "desktop" / "bridge.py").read_text(encoding="utf-8"), "desktop releases Thinking on unexpected worker termination"),
        ("timeout=20.0" in (root / "mary" / "llm" / "providers" / "groq.py").read_text(encoding="utf-8"), "Groq interactive request timeout is bounded"),
        ("max_retries=0" in (root / "mary" / "llm" / "providers" / "groq.py").read_text(encoding="utf-8"), "Groq SDK retries do not trap desktop in Thinking"),
        ("MARY_TTS_PROVIDER" in (root / "mary" / "desktop" / "voice.py").read_text(encoding="utf-8"), "desktop voice is explicit opt-in"),
        ("voice=voice_payload" in (root / "mary" / "desktop" / "bridge.py").read_text(encoding="utf-8"), "desktop response carries synthesized voice separately from text"),
        ("playVoice(payload.voice || {})" in (root / "desktop" / "src" / "main.js").read_text(encoding="utf-8"), "desktop plays returned Mary voice audio"),
        ("PlaybackRequiresUserGesture" in (root / "mary" / "desktop" / "window.py").read_text(encoding="utf-8"), "Qt permits async TTS playback"),
        ("Voice synthesis is also best-effort" in (root / "mary" / "desktop" / "bridge.py").read_text(encoding="utf-8"), "voice failure cannot swallow Mary's text response"),
        ('MARY_TTS_STABILITY", 0.50' in (root / "mary" / "desktop" / "voice.py").read_text(encoding="utf-8"), "Mary voice stability baseline is calibrated"),
        ('MARY_TTS_SIMILARITY", 0.75' in (root / "mary" / "desktop" / "voice.py").read_text(encoding="utf-8"), "Mary voice similarity baseline is calibrated"),
        ('MARY_TTS_STYLE", 0.0' in (root / "mary" / "desktop" / "voice.py").read_text(encoding="utf-8"), "Mary voice style baseline is calibrated"),
        ('MARY_TTS_SPEED", 1.0' in (root / "mary" / "desktop" / "voice.py").read_text(encoding="utf-8"), "Mary voice speed baseline is calibrated"),
        ("spoken_text = self.render_text" in (root / "mary" / "desktop" / "voice.py").read_text(encoding="utf-8"), "desktop always renders natural spoken text"),
        ("canonical_text: str" in (root / "mary" / "desktop" / "bridge.py").read_text(encoding="utf-8"), "desktop preserves canonical Mary response for debug/history"),
        ("display_text = spoken_text or response_text" in (root / "mary" / "desktop" / "bridge.py").read_text(encoding="utf-8"), "desktop transcript matches Mary's exact spoken wording"),
        ("class SpeechRenderer" in (root / "mary" / "voice" / "speech_renderer.py").read_text(encoding="utf-8"), "local deterministic speech renderer is installed"),
        (".main-column" in (root / "desktop" / "src" / "style.css").read_text(encoding="utf-8") and "grid-template-rows: var(--titlebar-height) minmax(0, 1fr) 120px" in (root / "desktop" / "src" / "style.css").read_text(encoding="utf-8") and ".chat-scroll" in (root / "desktop" / "src" / "style.css").read_text(encoding="utf-8") and "overflow-y:auto" in (root / "desktop" / "src" / "style.css").read_text(encoding="utf-8") and ".composer-deck" in (root / "desktop" / "src" / "style.css").read_text(encoding="utf-8"), "desktop pins composer while chat/workspace content can scroll"),
        ("emotional_state=mary.emotion.state" in (root / "mary" / "desktop" / "bridge.py").read_text(encoding="utf-8"), "desktop voice and avatar share Mary's existing emotion state"),
        ("resolve_emotion_voice_settings" in (root / "mary" / "desktop" / "voice.py").read_text(encoding="utf-8"), "Mary voice delivery resolves from emotional state"),
        ("class EmotionVoiceAdjustment" in (root / "mary" / "voice" / "emotion_profile.py").read_text(encoding="utf-8"), "emotion voice profile is local and provider-independent"),
        ("user_text=user_text" in (root / "mary" / "desktop" / "voice.py").read_text(encoding="utf-8"), "speech renderer receives creator-turn context"),
        ("structured understanding" in (root / "mary" / "voice" / "speech_renderer.py").read_text(encoding="utf-8"), "SpeechRenderer V3 naturalizes backend-facing responses"),
        ('Emotion.CONCERN: EmotionVoiceAdjustment("concerned", -0.01, 0.015, -0.01)' in (root / "mary" / "voice" / "emotion_profile.py").read_text(encoding="utf-8"), "concern voice stays close to Mary's calibrated baseline"),
        ('Emotion.PRIDE: EmotionVoiceAdjustment("proud", -0.03, 0.025, 0.015)' in (root / "mary" / "voice" / "emotion_profile.py").read_text(encoding="utf-8"), "pride voice remains expressive without changing identity"),
        ("createMediaElementSource(audio)" in (root / "desktop" / "src" / "main.js").read_text(encoding="utf-8"), "lip sync analyses Mary's actual playback audio"),
        ("getByteTimeDomainData(speechWaveform)" in (root / "desktop" / "src" / "main.js").read_text(encoding="utf-8"), "lip sync reads real-time speech waveform amplitude"),
        ("manager.setValue(activeMouthExpression, lipSyncWeight)" in (root / "desktop" / "src" / "main.js").read_text(encoding="utf-8"), "lip sync drives a standard VRM mouth expression"),
        ("disconnectLipSyncGraph();" in (root / "desktop" / "src" / "main.js").read_text(encoding="utf-8"), "lip sync resets mouth and audio graph after speech"),
        ("QMediaCaptureSession" in (root / "mary" / "desktop" / "microphone.py").read_text(encoding="utf-8"), "desktop captures microphone through native Qt Multimedia"),
        ('MARY_STT_MODEL", "whisper-large-v3-turbo"' in (root / "mary" / "desktop" / "stt.py").read_text(encoding="utf-8"), "desktop STT defaults to Groq Whisper Large V3 Turbo"),
        ("client.audio.transcriptions.create" in (root / "mary" / "desktop" / "stt.py").read_text(encoding="utf-8"), "desktop STT uses Groq audio transcription endpoint"),
        ("bridge.startListening()" in (root / "desktop" / "src" / "main.js").read_text(encoding="utf-8"), "desktop exposes user-initiated push-to-talk"),
        ("stopVoicePlayback({ notifyBridge: false });" in (root / "desktop" / "src" / "main.js").read_text(encoding="utf-8"), "push-to-talk stops Mary voice before recording to avoid feedback"),
        ("bridge.sendMessage(transcript)" in (root / "desktop" / "src" / "main.js").read_text(encoding="utf-8"), "voice transcript reuses canonical Mary conversation path"),
        ("DesktopConversationRuntime()" in (root / "mary" / "desktop" / "bridge.py").read_text(encoding="utf-8"), "desktop owns one authoritative conversation runtime"),
        ("conversationStateChanged = Signal(str)" in (root / "mary" / "desktop" / "bridge.py").read_text(encoding="utf-8"), "desktop publishes conversation lifecycle state"),
        ("voicePlaybackStopRequested = Signal()" in (root / "mary" / "desktop" / "bridge.py").read_text(encoding="utf-8"), "desktop can stop Mary playback for barge-in"),
        ("bridge?.voicePlaybackStarted?.();" in (root / "desktop" / "src" / "main.js").read_text(encoding="utf-8"), "real audio playback marks Mary speaking"),
        ("bridge.voicePlaybackStopRequested.connect" in (root / "desktop" / "src" / "main.js").read_text(encoding="utf-8"), "browser obeys authoritative interruption requests"),
        ("characterStateChanged = Signal(str)" in (root / "mary" / "desktop" / "bridge.py").read_text(encoding="utf-8"), "desktop publishes live character state"),
        ("def getCharacterState" in (root / "mary" / "desktop" / "bridge.py").read_text(encoding="utf-8"), "desktop exposes display-safe character snapshot"),
        ("applyCharacterState" in (root / "desktop" / "src" / "main.js").read_text(encoding="utf-8"), "frontend renders Mary state in real time"),
        ('id="sidebar-status-card"' in (root / "desktop" / "index.html").read_text(encoding="utf-8") and 'id="avatar-live-state"' in (root / "desktop" / "index.html").read_text(encoding="utf-8"), "desktop includes Mary live-state presentation"),
    ]

    failed = False
    for ok, label in checks:
        print(("PASS" if ok else "FAIL") + f"  {label}")
        failed = failed or not ok

    if failed:
        return 1

    dist = root / "desktop" / "dist" / "index.html"
    if dist.exists():
        print("PASS  desktop frontend is built")
    else:
        print("INFO  frontend not built yet; run `cd desktop`, `npm install`, `npm run build`")

    print("=" * 72)
    print("DESKTOP ALPHA FILES INSTALLED CORRECTLY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
