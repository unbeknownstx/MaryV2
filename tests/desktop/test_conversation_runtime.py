from __future__ import annotations

from pathlib import Path

import pytest

from mary.desktop.conversation_runtime import (
    DesktopConversationRuntime,
    DesktopConversationState,
)


def _root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_conversation_runtime_follows_voice_turn_lifecycle() -> None:
    runtime = DesktopConversationRuntime()

    assert runtime.state == DesktopConversationState.IDLE
    runtime.transition(DesktopConversationState.THINKING, reason="message_submitted")
    runtime.transition(DesktopConversationState.SPEAKING, reason="voice_playback_started")
    runtime.transition(DesktopConversationState.IDLE, reason="voice_playback_finished")

    assert runtime.state == DesktopConversationState.IDLE
    assert runtime.snapshot.reason == "voice_playback_finished"
    assert runtime.snapshot.sequence == 3


def test_conversation_runtime_models_microphone_turn() -> None:
    runtime = DesktopConversationRuntime()

    runtime.transition(DesktopConversationState.LISTENING, reason="microphone_recording")
    runtime.transition(DesktopConversationState.TRANSCRIBING, reason="microphone_stopped")
    runtime.transition(DesktopConversationState.IDLE, reason="transcription_finished")
    runtime.transition(DesktopConversationState.THINKING, reason="message_submitted")

    assert runtime.state == DesktopConversationState.THINKING


def test_speaking_can_be_interrupted_then_listen_or_think() -> None:
    runtime = DesktopConversationRuntime()
    runtime.transition(DesktopConversationState.SPEAKING, reason="voice_playback_started")
    runtime.transition(DesktopConversationState.INTERRUPTED, reason="microphone_barge_in")
    runtime.transition(DesktopConversationState.LISTENING, reason="microphone_recording")

    assert runtime.state == DesktopConversationState.LISTENING

    runtime = DesktopConversationRuntime()
    runtime.transition(DesktopConversationState.SPEAKING, reason="voice_playback_started")
    runtime.transition(DesktopConversationState.INTERRUPTED, reason="typed_barge_in")
    runtime.transition(DesktopConversationState.THINKING, reason="message_submitted")

    assert runtime.state == DesktopConversationState.THINKING


def test_invalid_overlap_transition_is_rejected() -> None:
    runtime = DesktopConversationRuntime()
    runtime.transition(DesktopConversationState.LISTENING, reason="microphone_recording")

    with pytest.raises(ValueError, match="listening -> thinking"):
        runtime.transition(DesktopConversationState.THINKING, reason="bad_overlap")


def test_bridge_owns_authoritative_conversation_state_and_playback_handshake() -> None:
    bridge = (_root() / "mary" / "desktop" / "bridge.py").read_text(encoding="utf-8")

    assert "DesktopConversationRuntime" in bridge
    assert "conversationStateChanged = Signal(str)" in bridge
    assert "voicePlaybackStopRequested = Signal()" in bridge
    assert "def voicePlaybackStarted" in bridge
    assert "def voicePlaybackFinished" in bridge
    assert "microphone_barge_in" in bridge
    assert "typed_barge_in" in bridge
    assert '"conversation": self.conversation_runtime.snapshot.to_dict()' in bridge


def test_frontend_reports_real_audio_playback_and_supports_barge_in() -> None:
    frontend = (_root() / "desktop" / "src" / "main.js").read_text(encoding="utf-8")

    assert "let conversationState = 'idle';" in frontend
    assert "bridge?.voicePlaybackStarted?.();" in frontend
    assert "bridge?.voicePlaybackFinished?.();" in frontend
    assert "bridge.voicePlaybackStopRequested.connect" in frontend
    assert "stopVoicePlayback({ notifyBridge: false });" in frontend
    assert "conversationState === 'speaking'" in frontend
    assert "micButton.textContent" in frontend and "'Interrupt'" in frontend
