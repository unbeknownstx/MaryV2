from __future__ import annotations

import json
from pathlib import Path


def _root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_desktop_frontend_manifest_is_pinned_and_local() -> None:
    package = json.loads((_root() / "desktop" / "package.json").read_text(encoding="utf-8"))

    assert package["dependencies"]["three"] == "0.185.1"
    assert package["dependencies"]["@pixiv/three-vrm"] == "3.5.5"
    assert package["devDependencies"]["vite"] == "8.2.1"
    assert package["scripts"]["build"] == "vite build"


def test_desktop_build_uses_relative_asset_base_for_qt_file_url() -> None:
    source = (_root() / "desktop" / "vite.config.js").read_text(encoding="utf-8")
    assert "base: './'" in source


def test_desktop_bridge_uses_canonical_application_not_second_mary() -> None:
    source = (_root() / "mary" / "desktop" / "bridge.py").read_text(encoding="utf-8")
    assert "MaryApplication" in source
    assert "Mary(" not in source
    assert "self.application.run" in source


def test_vrm_orientation_and_relaxed_pose_are_version_safe() -> None:
    source = (_root() / "desktop" / "src" / "main.js").read_text(encoding="utf-8")

    assert "VRMUtils.rotateVRM0(currentVrm)" in source
    assert "currentVrm.scene.rotation.y = Math.PI" not in source
    assert "setNormalizedPose" in source
    assert "RELAXED_STANDING_POSE" in source
    assert "new THREE.Clock" not in source


def test_desktop_bridge_does_not_pass_avatar_state_as_expression() -> None:
    source = (_root() / "mary" / "desktop" / "bridge.py").read_text(encoding="utf-8")

    assert "mary.avatar.sync_emotion()" in source
    assert "expression = mary.avatar.sync_emotion()" not in source
    assert "expression=expression" not in source


def test_relaxed_pose_lowers_arms_from_t_pose() -> None:
    source = (_root() / "desktop" / "src" / "main.js").read_text(encoding="utf-8")

    assert "leftUpperArm: { rotation: quaternionArrayFromEuler(0, 0, -1.28) }" in source
    assert "rightUpperArm: { rotation: quaternionArrayFromEuler(0, 0, 1.28) }" in source


def test_desktop_full_body_camera_framing_is_geometry_based() -> None:
    source = (_root() / "desktop" / "src" / "main.js").read_text(encoding="utf-8")

    assert "verticalDistance" in source
    assert "horizontalDistance" in source
    assert "Math.max(verticalDistance, horizontalDistance) * 1.18" in source
    assert "const distance = height * 1.05" not in source


def test_desktop_bridge_uses_dedicated_qthread_and_gui_thread_slots() -> None:
    source = (_root() / "mary" / "desktop" / "bridge.py").read_text(encoding="utf-8")

    assert "from PySide6.QtCore import QObject, QThread, Signal, Slot" in source
    assert "self._active_thread: QThread | None = None" in source
    assert "worker.moveToThread(thread)" in source
    assert "thread.started.connect(worker.run)" in source
    assert "@Slot(object)" in source
    assert "@Slot(str)" in source
    assert "self._set_busy(False)" in source
    assert "worker.finished.connect(self._on_turn_finished)" in source
    assert "worker.failed.connect(self._on_turn_failed)" in source


def test_desktop_avatar_failure_cannot_swallow_chat_response() -> None:
    source = (_root() / "mary" / "desktop" / "bridge.py").read_text(encoding="utf-8")

    assert "Avatar presentation is best-effort" in source
    assert '"avatar_error": avatar_error' in source
    assert "self.finished.emit(payload)" in source
    assert "self.failed.emit(error)" in source


def test_groq_provider_has_bounded_interactive_timeout_without_sdk_retries() -> None:
    source = (_root() / "mary" / "llm" / "providers" / "groq.py").read_text(encoding="utf-8")

    assert "timeout=20.0" in source
    assert "max_retries=0" in source


def test_conversation_composer_stays_visible_while_messages_scroll() -> None:
    source = (_root() / "desktop" / "src" / "style.css").read_text(encoding="utf-8")

    assert "grid-template-rows: auto minmax(0, 1fr) auto" in source
    assert ".conversation-pane" in source
    assert "height: 100%" in source
    assert "overflow: hidden" in source
    assert ".messages" in source
    assert "min-height: 0" in source
    assert "overflow-y: auto" in source
    assert ".composer" in source
    assert "z-index: 2" in source


def test_desktop_voice_and_avatar_share_marys_existing_emotion_state() -> None:
    bridge = (_root() / "mary" / "desktop" / "bridge.py").read_text(encoding="utf-8")
    voice = (_root() / "mary" / "desktop" / "voice.py").read_text(encoding="utf-8")

    assert "mary.avatar.sync_emotion()" in bridge
    assert "emotional_state=mary.emotion.state" in bridge
    assert "resolve_emotion_voice_settings" in voice
    assert '"emotion_profile"' in voice
    assert '"voice_settings"' in voice


def test_desktop_lip_sync_uses_real_speech_audio_waveform() -> None:
    source = (_root() / "desktop" / "src" / "main.js").read_text(encoding="utf-8")

    assert "createMediaElementSource(audio)" in source
    assert "context.createAnalyser()" in source
    assert "getByteTimeDomainData(speechWaveform)" in source
    assert "const rms = Math.sqrt(sumSquares / speechWaveform.length)" in source
    assert "updateLipSync();" in source


def test_desktop_lip_sync_drives_standard_vrm_mouth_expression_and_resets() -> None:
    source = (_root() / "desktop" / "src" / "main.js").read_text(encoding="utf-8")

    assert "const MOUTH_PRESET_CANDIDATES = ['aa', 'oh', 'ou', 'ih', 'ee'];" in source
    assert "manager.getExpression?.(preset)" in source
    assert "manager.setValue(activeMouthExpression, lipSyncWeight)" in source
    assert "resetLipSyncMouth()" in source
    assert "disconnectLipSyncGraph();" in source


def test_desktop_push_to_talk_uses_native_qt_microphone_and_groq_stt() -> None:
    root = _root()
    bridge = (root / "mary" / "desktop" / "bridge.py").read_text(encoding="utf-8")
    microphone = (root / "mary" / "desktop" / "microphone.py").read_text(encoding="utf-8")
    stt = (root / "mary" / "desktop" / "stt.py").read_text(encoding="utf-8")
    frontend = (root / "desktop" / "src" / "main.js").read_text(encoding="utf-8")

    assert "DesktopMicrophoneRecorder" in bridge
    assert "DesktopSpeechToText.from_environment()" in bridge
    assert "QMediaCaptureSession" in microphone
    assert "QAudioInput" in microphone
    assert 'MARY_STT_MODEL", "whisper-large-v3-turbo"' in stt
    assert "client.audio.transcriptions.create" in stt
    assert "transcriptionReady" in bridge
    assert "bridge.sendMessage(transcript)" in frontend
