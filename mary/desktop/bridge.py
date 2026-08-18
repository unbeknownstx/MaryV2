"""Qt WebChannel bridge for MaryV2 Desktop Alpha.

The desktop is a presentation surface over the canonical ``MaryApplication``.
Conversation work runs on a dedicated QThread so Qt/WebEngine stays responsive,
and every turn is guaranteed to leave the busy state through an explicit
success or failure slot on the GUI thread.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from time import monotonic
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal, Slot

from mary.runtime.application import MaryApplication
from mary.desktop.voice import DesktopVoiceEngine
from mary.desktop.microphone import DesktopMicrophoneRecorder
from mary.desktop.stt import DesktopSpeechToText
from mary.desktop.conversation_runtime import (
    DesktopConversationRuntime,
    DesktopConversationState,
)


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)


@dataclass(frozen=True)
class DesktopTurnPayload:
    # ``text`` is the conversational transcript shown in the normal desktop
    # chat and is intentionally the same wording sent to TTS.
    text: str
    # Keep Mary's canonical backend response available for debug/history
    # without making the normal transcript disagree with what she actually says.
    canonical_text: str
    avatar: dict[str, Any]
    voice: dict[str, Any]
    runtime: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "canonical_text": self.canonical_text,
            "avatar": dict(self.avatar),
            "voice": dict(self.voice),
            "runtime": dict(self.runtime),
        }


class _ConversationWorker(QObject):
    """Run one canonical Mary turn in a dedicated Qt worker thread."""

    finished = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        application: MaryApplication,
        text: str,
        voice: DesktopVoiceEngine,
    ) -> None:
        super().__init__()
        self.application = application
        self.text = text
        self.voice = voice

    @Slot()
    def run(self) -> None:
        started = monotonic()
        print("[MaryDesktop] turn started", flush=True)

        try:
            result = self.application.run(self.text)

            if not result.success:
                raise RuntimeError(
                    result.error or "Mary's pipeline did not complete."
                )

            response_text = str(result.output or "")
            mary = self.application.mary

            # Avatar presentation is best-effort. A visual-state defect must
            # never swallow an otherwise valid conversation response.
            avatar_error: str | None = None
            try:
                mary.avatar.sync_emotion()
                avatar_state = mary.avatar.controller.present(
                    text=response_text,
                    speaking=False,
                    metadata={"surface": "desktop"},
                )
                avatar_payload = avatar_state.to_dict()
            except Exception as exc:
                avatar_error = f"{type(exc).__name__}: {exc}"
                avatar_payload = mary.avatar.state.to_dict()

            # Voice synthesis is also best-effort. A TTS provider failure must
            # never hide Mary's text response. Voice is opt-in through the
            # desktop environment configuration.
            voice_error: str | None = None
            try:
                voice_payload = self.voice.synthesize(
                    response_text,
                    user_text=self.text,
                    emotional_state=mary.emotion.state,
                )
            except Exception as exc:
                voice_error = f"{type(exc).__name__}: {exc}"
                # Speech rendering is local/deterministic, so preserve the
                # conversational transcript even if the remote TTS request
                # itself fails.
                spoken_text = self.voice.render_text(
                    response_text,
                    user_text=self.text,
                )
                voice_payload = {
                    **self.voice.status.to_dict(),
                    "status": "failed",
                    "error": voice_error,
                    "spoken_text": spoken_text,
                }

            spoken_text = str(voice_payload.get("spoken_text") or "").strip()
            display_text = spoken_text or response_text

            payload = DesktopTurnPayload(
                text=display_text,
                canonical_text=response_text,
                avatar=avatar_payload,
                voice=voice_payload,
                runtime={
                    "turn_id": result.turn_id,
                    "elapsed": result.elapsed,
                    "success": result.success,
                    "avatar_error": avatar_error,
                    "voice_error": voice_error,
                },
            )

            print(
                f"[MaryDesktop] turn completed in {monotonic() - started:.2f}s",
                flush=True,
            )
            self.finished.emit(payload)

        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            print(
                f"[MaryDesktop] turn failed in {monotonic() - started:.2f}s: {error}",
                flush=True,
            )
            self.failed.emit(error)


class _TranscriptionWorker(QObject):
    """Transcribe one recorded microphone utterance off the GUI thread."""

    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, stt: DesktopSpeechToText, path: str) -> None:
        super().__init__()
        self.stt = stt
        self.path = path

    @Slot()
    def run(self) -> None:
        print("[MaryDesktop] transcription started", flush=True)
        try:
            text = self.stt.transcribe(self.path)
            print(f"[MaryDesktop] transcription: {text}", flush=True)
            self.finished.emit(text)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            print(f"[MaryDesktop] transcription failed: {error}", flush=True)
            self.failed.emit(error)


class MaryDesktopBridge(QObject):
    """Object exposed to JavaScript through QWebChannel."""

    messageReady = Signal(str)
    avatarStateChanged = Signal(str)
    busyChanged = Signal(bool)
    errorOccurred = Signal(str)
    listeningStateChanged = Signal(str)
    transcriptionReady = Signal(str)
    conversationStateChanged = Signal(str)
    voicePlaybackStopRequested = Signal()

    def __init__(self, application: MaryApplication) -> None:
        super().__init__()
        self.application = application
        self._busy = False
        self._active_thread: QThread | None = None
        self._active_worker: _ConversationWorker | None = None
        self._speech_thread: QThread | None = None
        self._speech_worker: _TranscriptionWorker | None = None
        self.conversation_runtime = DesktopConversationRuntime()
        self.voice = DesktopVoiceEngine.from_environment()
        self.stt = DesktopSpeechToText.from_environment()
        self.microphone = DesktopMicrophoneRecorder()
        self.microphone.stateChanged.connect(self._on_microphone_state_changed)
        self.microphone.recordingReady.connect(self._on_recording_ready)
        self.microphone.errorOccurred.connect(self._on_microphone_error)
        self.application.mary.avatar.ready()

    @Slot(str)
    def sendMessage(self, text: str) -> None:  # noqa: N802 - JS-facing API
        value = str(text or "").strip()
        if not value:
            return

        state = self.conversation_runtime.state
        if self._busy:
            self.errorOccurred.emit("Mary is already processing a message.")
            return
        if state in {
            DesktopConversationState.LISTENING,
            DesktopConversationState.TRANSCRIBING,
        }:
            self.errorOccurred.emit("Finish the current microphone turn first.")
            return
        if state == DesktopConversationState.SPEAKING:
            # Typed input is also a valid barge-in. Stop browser playback first,
            # then begin the new canonical Mary turn.
            self._transition_conversation_state(
                DesktopConversationState.INTERRUPTED,
                reason="typed_barge_in",
            )
            self.voicePlaybackStopRequested.emit()

        self._transition_conversation_state(
            DesktopConversationState.THINKING,
            reason="message_submitted",
        )
        self._set_busy(True)

        thread = QThread(self)
        worker = _ConversationWorker(self.application, value, self.voice)
        worker.moveToThread(thread)

        # Keep both wrappers alive for the full turn.
        self._active_thread = thread
        self._active_worker = worker

        thread.started.connect(worker.run)
        worker.finished.connect(self._on_turn_finished)
        worker.failed.connect(self._on_turn_failed)
        thread.finished.connect(self._on_thread_finished)

        thread.start()

    @Slot()
    def startListening(self) -> None:  # noqa: N802 - JS-facing API
        state = self.conversation_runtime.state
        if self._busy or state == DesktopConversationState.THINKING:
            self.errorOccurred.emit("Mary is still thinking about the current message.")
            return
        if self._speech_thread is not None or state == DesktopConversationState.TRANSCRIBING:
            self.errorOccurred.emit("Mary is already transcribing microphone audio.")
            return
        if state == DesktopConversationState.LISTENING:
            return
        if not self.stt.enabled:
            self.errorOccurred.emit(
                "Speech input is not configured. Set GROQ_API_KEY and "
                "MARY_STT_PROVIDER=groq."
            )
            return

        if state == DesktopConversationState.SPEAKING:
            # Barge-in is authoritative here: browser playback is told to stop,
            # then the microphone becomes the active side of the conversation.
            self._transition_conversation_state(
                DesktopConversationState.INTERRUPTED,
                reason="microphone_barge_in",
            )
            self.voicePlaybackStopRequested.emit()

        self.microphone.start()

    @Slot()
    def stopListening(self) -> None:  # noqa: N802 - JS-facing API
        self.microphone.stop()

    @Slot()
    def voicePlaybackStarted(self) -> None:  # noqa: N802 - JS-facing API
        state = self.conversation_runtime.state
        if state in {
            DesktopConversationState.LISTENING,
            DesktopConversationState.TRANSCRIBING,
            DesktopConversationState.INTERRUPTED,
        }:
            # A late browser play event must never talk over an active barge-in.
            self.voicePlaybackStopRequested.emit()
            return
        self._transition_conversation_state(
            DesktopConversationState.SPEAKING,
            reason="voice_playback_started",
        )

    @Slot()
    def voicePlaybackFinished(self) -> None:  # noqa: N802 - JS-facing API
        if self.conversation_runtime.state in {
            DesktopConversationState.SPEAKING,
            DesktopConversationState.THINKING,
        }:
            self._transition_conversation_state(
                DesktopConversationState.IDLE,
                reason="voice_playback_finished",
            )

    @Slot(result=str)
    def getStatus(self) -> str:  # noqa: N802 - JS-facing API
        mary = self.application.mary
        status = mary.status()
        cognition = status.get("cognition", {})
        return _json(
            {
                "name": status.get("name", "Mary"),
                "provider": cognition.get("llm", "unknown"),
                "model": cognition.get("model", "unknown"),
                "busy": self._busy,
                "conversation": self.conversation_runtime.snapshot.to_dict(),
                "voice": self.voice.status.to_dict(),
                "speech_to_text": self.stt.status.to_dict(),
            }
        )

    @Slot(result=str)
    def getAvatarState(self) -> str:  # noqa: N802 - JS-facing API
        return _json(self.application.mary.avatar.state.to_dict())

    @Slot()
    def save(self) -> None:
        try:
            self.application.save()
        except Exception as exc:
            self.errorOccurred.emit(f"{type(exc).__name__}: {exc}")

    def close(self) -> None:
        self.microphone.stop()
        speech_thread = self._speech_thread
        if speech_thread is not None and speech_thread.isRunning():
            speech_thread.quit()
            speech_thread.wait()
        self.microphone.cleanup()

        thread = self._active_thread
        if thread is not None and thread.isRunning():
            # Ask the pipeline to stop at the next stage boundary, then wait for
            # the in-flight synchronous provider call to return naturally.
            self.application.pipeline.cancel()
            thread.quit()
            thread.wait()
        self.application.close()

    @Slot(str)
    def _on_recording_ready(self, path: str) -> None:
        if self._speech_thread is not None:
            self.errorOccurred.emit("Speech transcription is already active.")
            self.microphone.cleanup()
            return

        thread = QThread(self)
        worker = _TranscriptionWorker(self.stt, path)
        worker.moveToThread(thread)
        self._speech_thread = thread
        self._speech_worker = worker

        thread.started.connect(worker.run)
        worker.finished.connect(self._on_transcription_finished)
        worker.failed.connect(self._on_transcription_failed)
        thread.finished.connect(self._on_speech_thread_finished)
        thread.start()

    @Slot(str)
    def _on_transcription_finished(self, text: str) -> None:
        value = str(text or "").strip()
        self.microphone.cleanup()
        self.listeningStateChanged.emit("idle")
        self._transition_conversation_state(
            DesktopConversationState.IDLE,
            reason="transcription_finished",
        )
        if value:
            self.transcriptionReady.emit(value)
        else:
            self.errorOccurred.emit("No speech was detected in the recording.")
        self._finish_speech_thread()

    @Slot(str)
    def _on_transcription_failed(self, error: str) -> None:
        self.microphone.cleanup()
        self.listeningStateChanged.emit("idle")
        self._transition_conversation_state(
            DesktopConversationState.IDLE,
            reason="transcription_failed",
        )
        self.errorOccurred.emit(str(error))
        self._finish_speech_thread()

    @Slot(str)
    def _on_microphone_error(self, error: str) -> None:
        self.listeningStateChanged.emit("idle")
        self._transition_conversation_state(
            DesktopConversationState.IDLE,
            reason="microphone_error",
        )
        self.errorOccurred.emit(str(error))

    @Slot(str)
    def _on_microphone_state_changed(self, state: str) -> None:
        value = str(state or "idle").strip().lower()
        self.listeningStateChanged.emit(value)
        if value == "listening":
            self._transition_conversation_state(
                DesktopConversationState.LISTENING,
                reason="microphone_recording",
            )
        elif value == "transcribing":
            self._transition_conversation_state(
                DesktopConversationState.TRANSCRIBING,
                reason="microphone_stopped",
            )

    @Slot()
    def _on_speech_thread_finished(self) -> None:
        self._speech_worker = None
        self._speech_thread = None

    def _finish_speech_thread(self) -> None:
        thread = self._speech_thread
        if thread is not None and thread.isRunning():
            thread.quit()

    def _transition_conversation_state(
        self,
        state: DesktopConversationState | str,
        *,
        reason: str,
    ) -> None:
        try:
            snapshot = self.conversation_runtime.transition(state, reason=reason)
        except ValueError as exc:
            print(f"[MaryDesktop] conversation-state warning: {exc}", flush=True)
            return
        print(
            f"[MaryDesktop] conversation state: "
            f"{snapshot.previous.value} -> {snapshot.state.value} "
            f"({snapshot.reason})",
            flush=True,
        )
        self.conversationStateChanged.emit(_json(snapshot.to_dict()))

    def _set_busy(self, value: bool) -> None:
        self._busy = bool(value)
        self.busyChanged.emit(self._busy)

    @Slot(object)
    def _on_turn_finished(self, payload: object) -> None:
        """Receive a successful turn on the GUI thread and release the UI."""

        if not isinstance(payload, DesktopTurnPayload):
            self._finish_thread()
            self._set_busy(False)
            self.errorOccurred.emit(
                "Mary's desktop worker returned an invalid response payload."
            )
            return

        self._set_busy(False)
        payload_dict = payload.to_dict()
        self.messageReady.emit(_json(payload_dict))
        self.avatarStateChanged.emit(_json(payload.avatar))

        voice = payload.voice
        voice_will_play = bool(
            voice.get("enabled")
            and voice.get("status") == "success"
            and voice.get("audio_base64")
        )
        if not voice_will_play:
            self._transition_conversation_state(
                DesktopConversationState.IDLE,
                reason="turn_finished_without_voice",
            )

        avatar_error = str(
            payload.runtime.get("avatar_error") or ""
        ).strip()
        if avatar_error:
            print(
                f"[MaryDesktop] avatar presentation warning: {avatar_error}",
                flush=True,
            )

        voice_error = str(
            payload.runtime.get("voice_error") or ""
        ).strip()
        if voice_error:
            print(
                f"[MaryDesktop] voice synthesis warning: {voice_error}",
                flush=True,
            )

        self._finish_thread()

    @Slot(str)
    def _on_turn_failed(self, error: str) -> None:
        """Receive a failed turn on the GUI thread and always release input."""

        self._set_busy(False)
        self._transition_conversation_state(
            DesktopConversationState.IDLE,
            reason="turn_failed",
        )
        self.errorOccurred.emit(str(error))
        self._finish_thread()

    @Slot()
    def _on_thread_finished(self) -> None:
        """Guard against a worker thread ending without a terminal signal."""

        if self._busy:
            self._set_busy(False)
            self._transition_conversation_state(
                DesktopConversationState.IDLE,
                reason="worker_stopped_without_response",
            )
            self.errorOccurred.emit(
                "Mary's desktop worker stopped without returning a response."
            )

        self._active_worker = None
        self._active_thread = None

    def _finish_thread(self) -> None:
        thread = self._active_thread
        if thread is not None and thread.isRunning():
            thread.quit()
