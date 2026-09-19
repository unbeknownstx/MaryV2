"""Qt WebChannel bridge for MaryV2 Desktop Alpha.

The desktop is a presentation surface over the canonical ``MaryApplication``.
Conversation work runs on a dedicated QThread so Qt/WebEngine stays responsive,
and every turn is guaranteed to leave the busy state through an explicit
success or failure slot on the GUI thread.
"""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from time import monotonic, sleep
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtCore import QByteArray, QBuffer, QIODevice, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QImage
from PySide6.QtWidgets import QFileDialog

from mary.runtime.application import MaryApplication
from mary.desktop.remote_application import RemoteMaryApplicationView
from mary.desktop.voice import DesktopVoiceEngine, RemoteCoreVoiceEngine
from mary.desktop.audio_cache import DesktopAudioCache
from mary.desktop.microphone import DesktopMicrophoneRecorder
from mary.desktop.resident_hearing import DesktopResidentHearing
from mary.desktop.stt import DesktopSpeechToText
from mary.desktop.dashboard import build_desktop_dashboard_state
from mary.desktop.integrations import DesktopIntegrationRegistry
from mary.desktop.projects import CreativeWorkspaceManager
from mary.desktop.turn_trace import build_turn_trace
from mary.presence import PresenceEventType
from mary.presence.websocket_server import LocalPresenceWebSocket
from mary.conversation import ConversationLane, classify_conversation_lane
from mary.distributed.permissions import DeviceExecutionPermissions
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
        application: MaryApplication | RemoteMaryApplicationView,
        text: str,
        voice: DesktopVoiceEngine,
        audio_cache: DesktopAudioCache | None = None,
        *,
        voice_input: bool = False,
    ) -> None:
        super().__init__()
        self.application = application
        self.text = text
        self.voice = voice
        self.audio_cache = audio_cache
        self.voice_input = bool(voice_input)

    @Slot()
    def run(self) -> None:
        started = monotonic()
        print("[MaryDesktop] turn started", flush=True)

        try:
            pipeline_started = monotonic()
            result = self.application.run(
                self.text,
                metadata={
                    "surface": "desktop",
                    "transport": (
                        "core"
                        if getattr(self.application, "authority", "") == "remote_mary_core"
                        else "in_process"
                    ),
                    "conversation_id": getattr(
                        self.application,
                        "conversation_id",
                        "creator-primary",
                    ),
                    "device_id": getattr(
                        self.application,
                        "device_id",
                        "desktop",
                    ),
                    "voice_input": bool(self.voice_input),
                    "client_local_time": datetime.now().astimezone().isoformat(timespec="seconds"),
                },
            )
            pipeline_ms = (monotonic() - pipeline_started) * 1000.0

            if not result.success:
                raise RuntimeError(
                    result.error or "Mary's pipeline did not complete."
                )

            response_text = str(result.output or "")
            mary = self.application.mary
            pipeline_values = dict(
                getattr(result, "metadata", {}).get("pipeline_values", {}) or {}
            )
            cognitive_cycle = pipeline_values.get("cognitive_cycle")
            cycle_metadata = dict(
                getattr(cognitive_cycle, "metadata", {}) or {}
            )
            delivery_plan = dict(
                cycle_metadata.get("delivery_plan", {}) or {}
            )
            performance_packet = dict(
                cycle_metadata.get("performance_packet", {}) or {}
            )

            # Avatar presentation is best-effort. A visual-state defect must
            # never swallow an otherwise valid conversation response.
            avatar_error: str | None = None
            avatar_started = monotonic()
            try:
                mary.avatar.sync_emotion()
                avatar_state = mary.avatar.controller.present(
                    text=response_text,
                    speaking=False,
                    metadata={
                        "surface": "desktop",
                        "delivery_plan": delivery_plan,
                    },
                )
                avatar_payload = avatar_state.to_dict()
            except Exception as exc:
                avatar_error = f"{type(exc).__name__}: {exc}"
                avatar_payload = mary.avatar.state.to_dict()

            avatar_ms = (monotonic() - avatar_started) * 1000.0

            # Voice synthesis is also best-effort. A TTS provider failure must
            # never hide Mary's text response. Voice is opt-in through the
            # desktop environment configuration.
            voice_error: str | None = None
            voice_started = monotonic()
            try:
                voice_payload = self.voice.synthesize(
                    response_text,
                    user_text=self.text,
                    emotional_state=mary.emotion.state,
                    delivery_plan=delivery_plan,
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

            voice_ms = (monotonic() - voice_started) * 1000.0

            # Large base64 audio blobs are expensive to serialize through
            # QWebChannel. Stage them into a finite temp cache and send a local
            # file URL instead. Keep base64 only as a fallback if staging fails.
            if (
                self.audio_cache is not None
                and voice_payload.get("status") == "success"
            ):
                voice_payload = self.audio_cache.stage(voice_payload)

            spoken_text = str(
                voice_payload.get("spoken_text") or ""
            ).strip()
            display_text = response_text or spoken_text
            worker_total_ms = (monotonic() - started) * 1000.0

            trace = build_turn_trace(
                result,
                pipeline_ms=pipeline_ms,
                avatar_ms=avatar_ms,
                voice_payload=voice_payload,
                worker_total_ms=worker_total_ms,
            )

            # Keep a direct wall-clock voice measurement as a fallback even if
            # a custom voice adapter did not provide internal timing metadata.
            trace.setdefault("timings", {}).setdefault(
                "voice_total_ms",
                round(voice_ms, 2),
            )

            voice_payload = {
                **voice_payload,
                "delivery_plan": delivery_plan,
                "performance_packet": performance_packet,
            }
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
                    "delivery_plan": delivery_plan,
                    "performance_packet": performance_packet,
                    "trace": trace,
                },
            )

            print(
                f"[MaryDesktop] turn completed in "
                f"{monotonic() - started:.2f}s",
                flush=True,
            )
            self.finished.emit(payload)

        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            print(
                f"[MaryDesktop] turn failed in "
                f"{monotonic() - started:.2f}s: {error}",
                flush=True,
            )
            self.failed.emit(error)


class _PresenceWorker(QObject):
    """Run one cheap Presence arbitration pulse off the Qt GUI thread."""

    finished = Signal(object)
    silent = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        application: MaryApplication | RemoteMaryApplicationView,
        voice: DesktopVoiceEngine,
        audio_cache: DesktopAudioCache | None = None,
    ) -> None:
        super().__init__()
        self.application = application
        self.voice = voice
        self.audio_cache = audio_cache

    @Slot()
    def run(self) -> None:
        started = monotonic()
        try:
            focus_active = False
            try:
                focus_active = bool(self.application.ecosystem.focus.snapshot().get("active", False))
            except Exception:
                pass

            conversation_id = str(getattr(self.application, "conversation_id", "creator-primary"))
            if getattr(self.application, "authority", "") == "remote_mary_core":
                pulse = dict(
                    self.application.ecosystem.presence.pulse(
                        surface_visible=True,
                        focus_active=focus_active,
                        conversation_id=conversation_id,
                    )
                    or {}
                )
                spoke = bool(pulse.get("speak") or pulse.get("spoke"))
            else:
                pulse = dict(
                    self.application.presence_pulse(
                        surface="desktop",
                        surface_visible=True,
                        focus_active=focus_active,
                        conversation_id=conversation_id,
                        device_id=str(getattr(self.application, "device_id", "desktop")),
                    )
                    or {}
                )
                spoke = bool(pulse.get("speak") or pulse.get("spoke"))

            if not spoke:
                self.silent.emit(pulse)
                return

            result = pulse.get("pipeline_result")
            hints: dict[str, Any] = {}
            response_text = str(pulse.get("text") or pulse.get("response") or "").strip()
            turn_id = str(pulse.get("turn_id") or "")
            elapsed = monotonic() - started

            if result is not None:
                response_text = str(getattr(result, "output", None) or response_text).strip()
                turn_id = str(getattr(result, "turn_id", None) or turn_id)
                elapsed = float(getattr(result, "elapsed", elapsed) or elapsed)
                pipeline_values = dict(getattr(result, "metadata", {}).get("pipeline_values", {}) or {})
                cycle = pipeline_values.get("cognitive_cycle")
                cycle_metadata = dict(getattr(cycle, "metadata", {}) or {})
                hints = {
                    "delivery_plan": dict(cycle_metadata.get("delivery_plan", {}) or {}),
                    "performance_packet": dict(cycle_metadata.get("performance_packet", {}) or {}),
                }
            else:
                hints = dict(pulse.get("display_hints") or {})

            if not response_text:
                self.silent.emit({**pulse, "reason": "initiative_returned_empty_text"})
                return

            delivery_plan = dict(hints.get("delivery_plan", {}) or {})
            performance_packet = dict(
                pulse.get("performance_packet")
                or hints.get("performance_packet")
                or {}
            )
            mary = self.application.mary
            if getattr(self.application, "authority", "") == "remote_mary_core":
                try:
                    mary.update_from_display_hints(hints, response_text)
                except Exception:
                    pass

            avatar_error: str | None = None
            try:
                mary.avatar.sync_emotion()
                avatar_state = mary.avatar.controller.present(
                    text=response_text,
                    speaking=False,
                    metadata={
                        "surface": "desktop",
                        "delivery_plan": delivery_plan,
                        "performance_packet": performance_packet,
                        "initiative": True,
                    },
                )
                avatar_payload = avatar_state.to_dict()
            except Exception as exc:
                avatar_error = f"{type(exc).__name__}: {exc}"
                avatar_payload = mary.avatar.state.to_dict()

            voice_error: str | None = None
            try:
                voice_payload = self.voice.synthesize(
                    response_text,
                    user_text=None,
                    emotional_state=mary.emotion.state,
                    delivery_plan=delivery_plan,
                )
            except Exception as exc:
                voice_error = f"{type(exc).__name__}: {exc}"
                voice_payload = {
                    **self.voice.status.to_dict(),
                    "status": "failed",
                    "error": voice_error,
                    "spoken_text": response_text,
                }

            if self.audio_cache is not None and voice_payload.get("status") == "success":
                voice_payload = self.audio_cache.stage(voice_payload)

            spoken_text = str(voice_payload.get("spoken_text") or "").strip()
            display_text = response_text or spoken_text
            payload = DesktopTurnPayload(
                text=display_text,
                canonical_text=response_text,
                avatar=avatar_payload,
                voice={
                    **voice_payload,
                    "delivery_plan": delivery_plan,
                    "performance_packet": performance_packet,
                },
                runtime={
                    "turn_id": turn_id,
                    "elapsed": elapsed,
                    "success": True,
                    "initiative": True,
                    "initiative_kind": str(pulse.get("initiative_kind") or "presence_event"),
                    "presence_action": str(pulse.get("presence_action") or "react"),
                    "presence_context": str(
                        pulse.get("presence_context")
                        or dict(pulse.get("candidate") or {}).get("summary")
                        or pulse.get("initiative_kind")
                        or "Mary initiative"
                    )[:4000],
                    "input_authority": str(pulse.get("authority") or "environment_context_only"),
                    "provenance": dict(pulse.get("provenance") or {}),
                    "avatar_error": avatar_error,
                    "voice_error": voice_error,
                    "delivery_plan": delivery_plan,
                    "performance_packet": performance_packet,
                    "trace": {
                        "turn_id": turn_id,
                        "initiative": True,
                        "response_engine": "mary_presence",
                        "delivery_plan": delivery_plan,
                    },
                },
            )
            self.finished.emit(payload)
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class _TranscriptionWorker(QObject):
    """Transcribe one recorded microphone utterance off the GUI thread."""

    finished = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        stt: DesktopSpeechToText,
        path: str,
    ) -> None:
        super().__init__()
        self.stt = stt
        self.path = path

    @Slot()
    def run(self) -> None:
        print("[MaryDesktop] transcription started", flush=True)
        try:
            text = self.stt.transcribe(self.path)
            print(
                f"[MaryDesktop] transcription: {text}",
                flush=True,
            )
            self.finished.emit(text)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            print(
                f"[MaryDesktop] transcription failed: {error}",
                flush=True,
            )
            self.failed.emit(error)


_CREATOR_IMAGE_MAX_BYTES = 1_350_000


def _prepare_creator_image(path: str) -> bytes:
    """Normalize one explicitly selected local image into a bounded JPEG."""

    image = QImage(path)
    if image.isNull():
        raise ValueError("The selected image could not be decoded.")
    if max(image.width(), image.height()) > 1600:
        image = image.scaled(
            1600,
            1600,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    image = image.convertToFormat(QImage.Format.Format_RGB888)

    def encode(source: QImage, quality: int) -> bytes:
        target = QByteArray()
        buffer = QBuffer(target)
        if not buffer.open(QIODevice.OpenModeFlag.WriteOnly):
            raise RuntimeError("Could not prepare the selected image.")
        try:
            if not source.save(buffer, "JPEG", quality):
                raise RuntimeError("Could not encode the selected image.")
            return bytes(target)
        finally:
            buffer.close()

    for quality in (80, 72, 64, 56, 48, 40):
        data = encode(image, quality)
        if 0 < len(data) <= _CREATOR_IMAGE_MAX_BYTES:
            return data

    if max(image.width(), image.height()) > 1200:
        image = image.scaled(
            1200,
            1200,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        for quality in (64, 54, 44, 36):
            data = encode(image, quality)
            if 0 < len(data) <= _CREATOR_IMAGE_MAX_BYTES:
                return data
    raise ValueError("The selected image remains too large after bounded compression.")


class _CreatorImageVisionWorker(QObject):
    """Ground one explicit image through canonical Core off the GUI thread."""

    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, gateway: Any, image: bytes) -> None:
        super().__init__()
        self.gateway = gateway
        self.image = bytes(image)

    @Slot()
    def run(self) -> None:
        try:
            encoded = base64.b64encode(self.image).decode("ascii")
            digest = hashlib.sha256(self.image).hexdigest()
            registered = self.gateway.runtime_action(
                "perception.asset.register",
                {
                    "kind": "image",
                    "mime_type": "image/jpeg",
                    "content_sha256": digest,
                    "byte_count": len(self.image),
                },
            )
            asset = dict(registered.get("asset") or {})
            asset_id = str(asset.get("asset_id") or "")
            if not asset_id:
                raise RuntimeError("Mary Core did not register the creator image.")

            dispatched = self.gateway.dispatch_capability_task(
                "sensor.image_describe",
                "Describe one creator-selected image as factual creative evidence for Mary.",
                {
                    "image_base64": encoded,
                    "mime_type": "image/jpeg",
                    "mode": "creative",
                    "asset_id": asset_id,
                },
            )
            task = dict(dispatched.get("task") or {})
            task_id = str(task.get("task_id") or "")
            if not task_id:
                raise RuntimeError("Mary Core did not create a visual-description task.")

            deadline = monotonic() + 45.0
            while monotonic() < deadline:
                current = self.gateway.capability_task_status(task_id)
                task = dict(current.get("task") or {})
                status = str(task.get("status") or "").casefold()
                if status == "completed":
                    result = dict(task.get("result") or {})
                    description = " ".join(
                        str(result.get("description") or "").split()
                    )[:12_000]
                    if not description:
                        raise RuntimeError(
                            "The vision node completed without a usable description."
                        )
                    self.finished.emit({
                        "ok": True,
                        "asset_id": asset_id,
                        "task_id": task_id,
                        "description": description,
                        "provider": str(result.get("provider") or "")[:80],
                        "model": str(result.get("model") or "")[:180],
                        "source_sha256": str(result.get("source_sha256") or "")[:64],
                        "raw_media_stored": False,
                        "authority": "ephemeral_perception_evidence",
                    })
                    return
                if status in {"failed", "rejected", "expired"}:
                    raise RuntimeError(
                        str(task.get("error") or "").strip()
                        or f"Vision task ended as {status}."
                    )
                sleep(0.35)
            raise RuntimeError("Vision task did not finish within the bounded wait.")
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class _CreatorSocialWorker(QObject):
    """Ask canonical Mary Core to author from already-grounded visual evidence."""

    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, gateway: Any, brief: str, summary: str, tone: str) -> None:
        super().__init__()
        self.gateway = gateway
        self.brief = brief
        self.summary = summary
        self.tone = tone

    @Slot()
    def run(self) -> None:
        try:
            result = self.gateway.runtime_action(
                "social.propose",
                {
                    "platform": "instagram",
                    "kind": "caption",
                    "brief": self.brief[:2000],
                    "media_summary": self.summary[:12_000],
                    "tone": self.tone[:120] or "natural",
                    "audience_text": "",
                },
            )
            self.finished.emit(dict(result or {}))
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class _CreatorDraftVoiceWorker(QObject):
    """Synthesize one Creator Lab preview through Mary's configured voice."""

    finished = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        voice: DesktopVoiceEngine,
        audio_cache: DesktopAudioCache,
        text: str,
    ) -> None:
        super().__init__()
        self.voice = voice
        self.audio_cache = audio_cache
        self.text = text

    @Slot()
    def run(self) -> None:
        try:
            payload = self.voice.synthesize(
                self.text,
                user_text=None,
                emotional_state=None,
                delivery_plan={},
            )
            if payload.get("status") == "success":
                payload = self.audio_cache.stage(payload)
            self.finished.emit(payload)
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class MaryDesktopBridge(QObject):
    """Object exposed to JavaScript through QWebChannel."""

    messageReady = Signal(str)
    avatarStateChanged = Signal(str)
    busyChanged = Signal(bool)
    errorOccurred = Signal(str)
    listeningStateChanged = Signal(str)
    transcriptionReady = Signal(str)
    residentHearingStateChanged = Signal(str)
    conversationStateChanged = Signal(str)
    characterStateChanged = Signal(str)
    dashboardStateChanged = Signal(str)
    creatorImageReady = Signal(str)
    creatorSocialReady = Signal(str)
    creatorDraftVoiceReady = Signal(str)
    voicePlaybackStopRequested = Signal()
    minimizeRequested = Signal()
    maximizeRequested = Signal()
    closeRequested = Signal()
    windowMoveRequested = Signal()

    def __init__(
        self,
        application: MaryApplication | RemoteMaryApplicationView,
    ) -> None:
        super().__init__()

        self.application = application
        self._busy = False

        self._active_thread: QThread | None = None
        self._active_worker: _ConversationWorker | None = None

        self._presence_thread: QThread | None = None
        self._presence_worker: _PresenceWorker | None = None

        self._speech_thread: QThread | None = None
        self._speech_worker: _TranscriptionWorker | None = None

        self._creator_image_thread: QThread | None = None
        self._creator_image_worker: _CreatorImageVisionWorker | None = None
        self._creator_social_thread: QThread | None = None
        self._creator_social_worker: _CreatorSocialWorker | None = None
        self._creator_voice_thread: QThread | None = None
        self._creator_voice_worker: _CreatorDraftVoiceWorker | None = None
        self._creator_image_bytes: bytes = b""

        self.conversation_runtime = DesktopConversationRuntime()

        local_voice = DesktopVoiceEngine.from_environment()
        self.voice = (
            RemoteCoreVoiceEngine(application.gateway, fallback=local_voice)
            if getattr(application, "authority", "") == "remote_mary_core"
            else local_voice
        )
        self.audio_cache = DesktopAudioCache()
        self.stt = DesktopSpeechToText.from_environment()
        self.microphone = DesktopMicrophoneRecorder()
        self.resident_hearing = DesktopResidentHearing()

        self.integrations = DesktopIntegrationRegistry()
        self.creative_workspace = CreativeWorkspaceManager()

        # MaryApplication owns the canonical ecosystem. Desktop is only a
        # presentation/client surface over that same shared instance.
        self.ecosystem = self.application.ecosystem

        self.presence_socket = LocalPresenceWebSocket(
            self.ecosystem.snapshot
        )
        self.presence_socket.start()

        self._active_turn_submitted_at: float | None = None
        self._pending_turn_trace: dict[str, Any] | None = None
        self._pending_turn_submitted_at: float | None = None
        self._active_feedback_user_text: str = ""
        self._last_feedback_context: dict[str, Any] = {}
        self._node_agent: Any | None = None
        self._device_permissions = DeviceExecutionPermissions()

        self.microphone.stateChanged.connect(
            self._on_microphone_state_changed
        )
        self.microphone.recordingReady.connect(
            self._on_recording_ready
        )
        self.microphone.errorOccurred.connect(
            self._on_microphone_error
        )
        self.resident_hearing.stateChanged.connect(
            self._on_resident_hearing_state_changed
        )
        self.resident_hearing.voiceActivity.connect(
            self._on_resident_voice_activity
        )
        self.resident_hearing.recordingReady.connect(
            self._on_resident_recording_ready
        )
        self.resident_hearing.errorOccurred.connect(
            self._on_resident_hearing_error
        )

        self.application.mary.avatar.ready()

    @Slot(str)
    def sendMessage(
        self,
        text: str,
    ) -> None:  # noqa: N802 - JS-facing API
        value = str(text or "").strip()
        if not value:
            return

        state = self.conversation_runtime.state

        if self._busy:
            self.errorOccurred.emit(
                "Mary is already processing a message."
            )
            return

        if state in {
            DesktopConversationState.LISTENING,
            DesktopConversationState.TRANSCRIBING,
        }:
            self.errorOccurred.emit(
                "Finish the current microphone turn first."
            )
            return

        if state == DesktopConversationState.SPEAKING:
            # Typed input is also a valid barge-in. Finalize perceived latency
            # for the interrupted voice turn before the next turn owns timing.
            self._finalize_pending_turn_trace(
                reason="interrupted"
            )

            # Stop browser playback first, then begin the new canonical Mary turn.
            self._transition_conversation_state(
                DesktopConversationState.INTERRUPTED,
                reason="typed_barge_in",
            )
            self.voicePlaybackStopRequested.emit()

        if self.resident_hearing.enabled:
            self.resident_hearing.pause("turn_active")

        self._active_turn_submitted_at = monotonic()
        self._active_feedback_user_text = value

        lane = classify_conversation_lane(value)

        presentation_state = (
            DesktopConversationState.RESPONDING
            if lane.lane
            in {
                ConversationLane.SOCIAL_INSTANT,
                ConversationLane.CONVERSATION,
            }
            else DesktopConversationState.THINKING
        )

        self._transition_conversation_state(
            presentation_state,
            reason=f"message_submitted:{lane.lane.value}",
        )

        self._set_busy(True)

        thread = QThread(self)

        worker = _ConversationWorker(
            self.application,
            value,
            self.voice,
            self.audio_cache,
            voice_input=bool(getattr(self, "_next_voice_input", False)),
        )

        worker.moveToThread(thread)

        # Keep both wrappers alive for the full turn.
        self._active_thread = thread
        self._active_worker = worker

        thread.started.connect(worker.run)
        worker.finished.connect(self._on_turn_finished)
        worker.failed.connect(self._on_turn_failed)
        thread.finished.connect(self._on_thread_finished)

        thread.start()

    @Slot(str)
    def sendVoiceMessage(
        self,
        text: str,
    ) -> None:  # noqa: N802 - JS-facing API
        """Submit one locally transcribed creator utterance as a voice turn."""
        self._next_voice_input = True
        try:
            self.sendMessage(text)
        finally:
            self._next_voice_input = False

    @Slot()
    def pulsePresence(self) -> None:  # noqa: N802 - JS-facing API
        """Run one non-blocking canonical Presence pulse while Desktop is idle."""

        if self._busy or self._presence_thread is not None:
            return
        if self.conversation_runtime.state != DesktopConversationState.IDLE:
            return
        if self._speech_thread is not None or self.microphone.is_recording:
            return
        if self.resident_hearing.enabled:
            return

        thread = QThread(self)
        worker = _PresenceWorker(
            self.application,
            self.voice,
            self.audio_cache,
        )
        worker.moveToThread(thread)
        self._presence_thread = thread
        self._presence_worker = worker
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_presence_finished)
        worker.silent.connect(self._on_presence_silent)
        worker.failed.connect(self._on_presence_failed)
        thread.finished.connect(self._on_presence_thread_finished)
        thread.start()

    @Slot()
    def startListening(
        self,
    ) -> None:  # noqa: N802 - JS-facing API
        state = self.conversation_runtime.state

        if self._busy or state in {
            DesktopConversationState.RESPONDING,
            DesktopConversationState.THINKING,
        }:
            self.errorOccurred.emit(
                "Mary is still thinking about the current message."
            )
            return

        if (
            self._speech_thread is not None
            or state == DesktopConversationState.TRANSCRIBING
        ):
            self.errorOccurred.emit(
                "Mary is already transcribing microphone audio."
            )
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
            # Barge-in is authoritative here. Finalize the previous perceived
            # trace before microphone ownership replaces the speaking state.
            self._finalize_pending_turn_trace(
                reason="microphone_barge_in"
            )

            # Browser playback is told to stop, then the microphone becomes the
            # active side of the conversation.
            self._transition_conversation_state(
                DesktopConversationState.INTERRUPTED,
                reason="microphone_barge_in",
            )

            self.voicePlaybackStopRequested.emit()

        if self.resident_hearing.enabled:
            self.resident_hearing.pause("push_to_talk")

        self.microphone.start()

    @Slot()
    def stopListening(
        self,
    ) -> None:  # noqa: N802 - JS-facing API
        self.microphone.stop()

    @Slot(bool, result=str)
    def setResidentHearing(
        self,
        enabled: bool,
    ) -> str:  # noqa: N802 - JS-facing API
        """Explicitly arm/disarm local resident hearing; startup stays OFF."""
        requested = bool(enabled)

        if not requested:
            self.resident_hearing.disable()
            return _json({"ok": True, **self.resident_hearing.status()})

        if not self.stt.enabled:
            return _json(
                {
                    "ok": False,
                    "error": "Speech input is not configured.",
                    **self.resident_hearing.status(),
                }
            )

        if self._busy or self._speech_thread is not None or self.microphone.is_recording:
            return _json(
                {
                    "ok": False,
                    "error": "Wait until the current turn or recording finishes.",
                    **self.resident_hearing.status(),
                }
            )

        if self.conversation_runtime.state != DesktopConversationState.IDLE:
            return _json(
                {
                    "ok": False,
                    "error": "Resident Hearing can be enabled while Mary is idle.",
                    **self.resident_hearing.status(),
                }
            )

        self.resident_hearing.enable()
        status = self.resident_hearing.status()
        return _json({"ok": bool(status.get("enabled")), **status})

    @Slot(result=str)
    def getResidentHearingState(self) -> str:  # noqa: N802 - JS-facing API
        return _json(self.resident_hearing.status())

    @Slot(str)
    def _on_resident_hearing_state_changed(self, _state: str) -> None:
        self.residentHearingStateChanged.emit(
            _json(self.resident_hearing.status())
        )

    @Slot(bool, bool, float)
    def _on_resident_voice_activity(
        self,
        active: bool,
        confirmed: bool,
        confidence: float,
    ) -> None:
        try:
            self.application.mary.realtime.report_voice_activity(
                bool(active),
                confirmed=bool(confirmed),
                source="desktop_resident_vad",
                confidence=float(confidence),
            )
        except Exception:
            pass

        if (
            active
            and confirmed
            and self.conversation_runtime.state == DesktopConversationState.IDLE
        ):
            self._transition_conversation_state(
                DesktopConversationState.LISTENING,
                reason="resident_vad_confirmed",
            )

    @Slot(str)
    def _on_resident_recording_ready(self, path: str) -> None:
        self._transition_conversation_state(
            DesktopConversationState.TRANSCRIBING,
            reason="resident_vad_endpoint",
        )
        self._on_recording_ready(path)

    @Slot(str)
    def _on_resident_hearing_error(self, error: str) -> None:
        self.errorOccurred.emit(str(error))
        self.residentHearingStateChanged.emit(
            _json(self.resident_hearing.status())
        )

    def _resume_resident_hearing_if_idle(self) -> None:
        if not self.resident_hearing.enabled:
            return
        if self._busy or self._speech_thread is not None:
            return
        if self.microphone.is_recording:
            return
        if self.conversation_runtime.state != DesktopConversationState.IDLE:
            return
        self.resident_hearing.resume()

    @Slot(str)
    def voicePlaybackStage(
        self,
        stage: str,
    ) -> None:  # noqa: N802 - JS-facing API
        """Record browser/audio startup milestones without finalizing the turn."""

        trace = self._pending_turn_trace
        submitted_at = self._pending_turn_submitted_at

        if not trace or submitted_at is None:
            return

        key_map = {
            "payload_received": "ui_payload_ms",
            "play_requested": "play_request_ms",
            "audio_ready": "audio_ready_ms",
        }

        key = key_map.get(
            str(stage or "").strip().lower()
        )

        if not key:
            return

        timings = dict(
            trace.get("timings") or {}
        )

        timings.setdefault(
            key,
            round(
                (monotonic() - submitted_at) * 1000.0,
                2,
            ),
        )

        trace["timings"] = timings

    @Slot()
    def voicePlaybackStarted(
        self,
    ) -> None:  # noqa: N802 - JS-facing API
        state = self.conversation_runtime.state

        if state in {
            DesktopConversationState.LISTENING,
            DesktopConversationState.TRANSCRIBING,
            DesktopConversationState.INTERRUPTED,
        }:
            # A late browser play event must never talk over an active barge-in.
            self.voicePlaybackStopRequested.emit()
            return

        self._finalize_pending_turn_trace(
            reason="voice_playback_started"
        )

        self._transition_conversation_state(
            DesktopConversationState.SPEAKING,
            reason="voice_playback_started",
        )

    @Slot()
    def voicePlaybackFinished(
        self,
    ) -> None:  # noqa: N802 - JS-facing API
        self._finalize_pending_turn_trace(
            reason="voice_playback_finished"
        )

        if self.conversation_runtime.state in {
            DesktopConversationState.SPEAKING,
            DesktopConversationState.RESPONDING,
            DesktopConversationState.THINKING,
        }:
            self._transition_conversation_state(
                DesktopConversationState.IDLE,
                reason="voice_playback_finished",
            )

    @Slot(result=str)
    def getStatus(
        self,
    ) -> str:  # noqa: N802 - JS-facing API
        mary = self.application.mary

        status = mary.status()
        cognition = status.get(
            "cognition",
            {},
        )

        return _json(
            {
                "name": status.get(
                    "name",
                    "Mary",
                ),
                "provider": cognition.get(
                    "llm",
                    "unknown",
                ),
                "model": cognition.get(
                    "model",
                    "unknown",
                ),
                "busy": self._busy,
                "conversation": self.conversation_runtime.snapshot.to_dict(),
                "voice": self.voice.status.to_dict(),
                "speech_to_text": self.stt.status.to_dict(),
                "resident_hearing": self.resident_hearing.status(),
                "presence_socket": self.presence_socket.status(),
                "realtime": mary.realtime.status(),
                "nodes": mary.node_registry.snapshot(),
            }
        )

    def attach_node_agent(self, agent: Any | None) -> None:
        """Attach the bounded local capability host owned by the Desktop window."""
        self._node_agent = agent
        if agent is not None:
            permissions = getattr(agent, "permissions", None)
            if permissions is not None:
                self._device_permissions = permissions

    @Slot(result=str)
    def getLocalComputePermission(self) -> str:  # noqa: N802 - JS-facing API
        allowed = self._device_permissions.is_allowed("llm.local")
        agent = self._node_agent
        status = {}
        if agent is not None:
            try:
                status = dict(agent.status() or {})
            except Exception:
                status = {}
        return _json({
            "ok": True,
            "capability": "llm.local",
            "enabled": bool(allowed),
            "registered": bool(status.get("registered", False)),
            "default": "deny",
            "authority": "device_local_permission",
        })

    @Slot(bool, result=str)
    def setLocalComputePermission(self, enabled: bool) -> str:  # noqa: N802
        """Explicit creator control for this host's bounded local LLM executor."""

        try:
            if bool(enabled):
                status = self._device_permissions.allow("llm.local")
            else:
                status = self._device_permissions.deny("llm.local")

            agent = self._node_agent
            registration = {}
            if agent is not None:
                try:
                    registration = dict(agent.refresh_registration() or {})
                except Exception as exc:
                    registration = {
                        "ok": False,
                        "error": f"{type(exc).__name__}: {exc}",
                    }

            self._emit_dashboard_state()
            return _json({
                "ok": True,
                "capability": "llm.local",
                "enabled": self._device_permissions.is_allowed("llm.local"),
                "registration": registration,
                "allowed_capabilities": list(status.get("allowed_capabilities", []) or []),
                "authority": "device_local_permission",
            })
        except Exception as exc:
            return _json({
                "ok": False,
                "capability": "llm.local",
                "enabled": self._device_permissions.is_allowed("llm.local"),
                "error": f"{type(exc).__name__}: {exc}",
            })

    @Slot(result=str)
    def getAvatarState(
        self,
    ) -> str:  # noqa: N802 - JS-facing API
        return _json(
            self.application.mary.avatar.state.to_dict()
        )

    @Slot(result=str)
    def getCharacterState(
        self,
    ) -> str:  # noqa: N802 - JS-facing API
        return _json(
            self.application.mary.live_state(
                runtime_status=self.conversation_runtime.state.value,
            )
        )

    @Slot(result=str)
    def getDashboardState(
        self,
    ) -> str:  # noqa: N802 - JS-facing API
        if getattr(
            self.application,
            "authority",
            "",
        ) == "remote_mary_core":
            return _json(
                self.application.dashboard_state(
                    runtime_status=self.conversation_runtime.state.value,
                )
            )

        payload = build_desktop_dashboard_state(
            self.application.mary,
            runtime_status=self.conversation_runtime.state.value,
        )

        payload["ecosystem"] = self.ecosystem.snapshot()

        try:
            payload["mind"] = self.application.mary.mind.status()
        except Exception as exc:
            payload["mind"] = {
                "enabled": False,
                "error": f"{type(exc).__name__}: {exc}",
            }

        payload["realtime"] = (
            self.application.mary.realtime.status()
        )

        payload["nodes"] = (
            self.application.mary.node_registry.snapshot()
        )

        payload["retrieval"] = (
            self.application.mary.mind.retrieval.status()
        )

        payload["perception"] = (
            self.application.mary.perception_director.snapshot()
        )

        try:
            from mary.runtime.system_fabric import build_system_fabric_projection
            payload["system_fabric"] = build_system_fabric_projection(self.application)
        except Exception as exc:
            payload["system_fabric"] = {
                "version": "1",
                "available": False,
                "error_type": type(exc).__name__,
                "authority": {"projection": "read_only"},
            }

        return _json(payload)

    @Slot(result=str)
    def getEcosystemState(
        self,
    ) -> str:  # noqa: N802
        return _json(
            self.ecosystem.snapshot()
        )

    @Slot(result=str)
    def getMindStatus(
        self,
    ) -> str:  # noqa: N802
        try:
            return _json(
                self.application.mary.mind.status()
            )
        except Exception as exc:
            return _json(
                {
                    "enabled": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    @Slot(result=str)
    def rebuildCognitiveReservoir(
        self,
    ) -> str:  # noqa: N802
        """Rebuild only Mary's derived local index; canonical state is untouched."""

        try:
            count = int(
                self.application.mary.mind.rebuild_reservoir()
            )

            self.dashboardStateChanged.emit(
                self.getDashboardState()
            )

            return _json(
                {
                    "ok": True,
                    "records": count,
                    "status": self.application.mary.mind.status(),
                }
            )

        except Exception as exc:
            return _json(
                {
                    "ok": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    @Slot(result=str)
    def getTrainingFeedbackState(self) -> str:  # noqa: N802 - JS-facing API
        """Return the explicit-feedback dataset status; never character authority."""
        try:
            if getattr(self.application, "authority", "") == "remote_mary_core":
                state = self.application.gateway.runtime_action("training.feedback.status")
            else:
                state = self.application.mary.training_feedback.status()
            return _json(state)
        except Exception as exc:
            return _json({"ok": False, "error": f"{type(exc).__name__}: {exc}"})

    @Slot(str, str, str, str, result=str)
    def recordResponseFeedback(
        self,
        rating: str,
        tags_json: str = "[]",
        note: str = "",
        chosen_text: str = "",
    ) -> str:  # noqa: N802 - JS-facing API
        """Record one opt-in Mary response rating/correction from Desktop."""
        context = dict(self._last_feedback_context)
        if not context:
            return _json({"ok": False, "error": "No completed desktop turn is available to rate."})
        try:
            parsed = json.loads(tags_json or "[]")
            tags = list(parsed if isinstance(parsed, list) else [])
        except Exception:
            tags = []
        values = {
            **context,
            "rating": str(rating or "neutral"),
            "tags": tags,
            "note": str(note or ""),
            "chosen_text": str(chosen_text or ""),
        }
        try:
            if getattr(self.application, "authority", "") == "remote_mary_core":
                result = self.application.gateway.runtime_action("training.feedback.record", values)
            else:
                record = self.application.mary.training_feedback.record(**values)
                result = {
                    "ok": True,
                    "id": record.id,
                    "status": self.application.mary.training_feedback.status(),
                }
            self.dashboardStateChanged.emit(self.getDashboardState())
            return _json(result)
        except Exception as exc:
            return _json({"ok": False, "error": f"{type(exc).__name__}: {exc}"})

    @Slot(str, result=str)
    def getModelExperimentStatus(
        self,
        experiment_id: str = "",
    ) -> str:  # noqa: N802 - JS-facing API
        """Return bounded experiment/node readiness from canonical remote Core."""

        if getattr(self.application, "authority", "") != "remote_mary_core":
            return _json({
                "ok": False,
                "error": "Model experiment trials require canonical remote Mary Core.",
                "execution_performed": False,
                "promotion_performed": False,
            })
        try:
            result = self.application.gateway.runtime_action(
                "model.experiment.status",
                {"experiment_id": str(experiment_id or "").strip()[:160]},
            )
            return _json(result)
        except Exception as exc:
            return _json({"ok": False, "error": f"{type(exc).__name__}: {exc}"})

    @Slot(str, str, result=str)
    def runModelExperiment(
        self,
        experiment_id: str,
        prompt: str,
    ) -> str:  # noqa: N802 - JS-facing API
        """Queue one explicit lab-only model experiment through Mary Core."""

        if getattr(self.application, "authority", "") != "remote_mary_core":
            return _json({
                "ok": False,
                "error": "Model experiment trials require canonical remote Mary Core.",
                "production_route_changed": False,
                "promotion_performed": False,
            })
        experiment = str(experiment_id or "").strip()[:160]
        clean_prompt = " ".join(str(prompt or "").split())[:12_000]
        if not experiment or not clean_prompt:
            return _json({"ok": False, "error": "Experiment ID and prompt are required."})
        try:
            result = self.application.gateway.runtime_action(
                "model.experiment.dispatch",
                {
                    "experiment_id": experiment,
                    "prompt": clean_prompt,
                    "max_tokens": 512,
                    "temperature": 0.7,
                },
            )
            return _json(result)
        except Exception as exc:
            return _json({"ok": False, "error": f"{type(exc).__name__}: {exc}"})

    @Slot(str, result=str)
    def getCapabilityTaskStatus(
        self,
        task_id: str,
    ) -> str:  # noqa: N802 - JS-facing API
        """Read one bounded capability-task result from canonical remote Core."""

        if getattr(self.application, "authority", "") != "remote_mary_core":
            return _json({
                "ok": False,
                "error": "Capability task status requires canonical remote Mary Core.",
            })
        clean = str(task_id or "").strip()[:180]
        if not clean:
            return _json({"ok": False, "error": "Capability task ID is required."})
        try:
            return _json(self.application.gateway.capability_task_status(clean))
        except Exception as exc:
            return _json({"ok": False, "error": f"{type(exc).__name__}: {exc}"})

    @Slot(result=str)
    def getLastTurnTrace(
        self,
    ) -> str:  # noqa: N802
        """Return display-safe timing/provider metadata for the latest desktop turn."""

        return _json(
            self.ecosystem.metrics.last_turn()
        )

    def _publish_workspace_event(
        self,
        event_type: PresenceEventType,
        summary: str,
        *,
        importance: float = .55,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Best-effort live context; workspace actions must never fail because Presence did."""

        try:
            self.ecosystem.publish_workspace_event(
                event_type,
                summary,
                importance=importance,
                metadata=metadata,
            )
        except Exception:
            pass

    @Slot(str, str, result=str)
    def addCommandItem(
        self,
        title: str,
        kind: str = "task",
    ) -> str:  # noqa: N802
        try:
            item = self.ecosystem.command.add(
                title,
                kind=kind or "task",
            )

            self._publish_workspace_event(
                PresenceEventType.COMMAND_CHANGED,
                f"Command Center added "
                f"{item.get('kind', 'item')}: "
                f"{item.get('title', '')}",
                importance=.58,
                metadata={
                    "item_id": item.get("id"),
                    "status": item.get("status"),
                },
            )

            self.dashboardStateChanged.emit(
                self.getDashboardState()
            )

            return _json(
                {
                    "ok": True,
                    "item": item,
                }
            )

        except Exception as exc:
            self.errorOccurred.emit(
                f"{type(exc).__name__}: {exc}"
            )

            return _json(
                {
                    "ok": False,
                    "error": str(exc),
                }
            )

    @Slot(str, str, result=str)
    def updateCommandStatus(
        self,
        item_id: str,
        status: str,
    ) -> str:  # noqa: N802
        try:
            item = self.ecosystem.command.update(
                item_id,
                status=status,
            )

            self._publish_workspace_event(
                PresenceEventType.COMMAND_CHANGED,
                f"Command Center updated "
                f"{item.get('title', 'an item')} to "
                f"{item.get('status', status)}",
                importance=.54,
                metadata={
                    "item_id": item.get("id"),
                    "status": item.get("status"),
                },
            )

            self.dashboardStateChanged.emit(
                self.getDashboardState()
            )

            return _json(
                {
                    "ok": True,
                    "item": item,
                }
            )

        except Exception as exc:
            self.errorOccurred.emit(
                f"{type(exc).__name__}: {exc}"
            )

            return _json(
                {
                    "ok": False,
                    "error": str(exc),
                }
            )

    @Slot(int, str, result=str)
    def startFocus(
        self,
        minutes: int,
        task: str = "",
    ) -> str:  # noqa: N802
        try:
            state = self.ecosystem.focus.start(
                minutes,
                task=task,
            )

            self._publish_workspace_event(
                PresenceEventType.FOCUS_CHANGED,
                f"Focus started for {int(minutes)} minutes"
                + (
                    f" on {task}"
                    if task
                    else ""
                ),
                importance=.44,
                metadata={
                    "active": True,
                    "minutes": int(minutes),
                },
            )

            self.dashboardStateChanged.emit(
                self.getDashboardState()
            )

            return _json(
                {
                    "ok": True,
                    "focus": state,
                }
            )

        except Exception as exc:
            return _json(
                {
                    "ok": False,
                    "error": str(exc),
                }
            )

    @Slot(result=str)
    def stopFocus(
        self,
    ) -> str:  # noqa: N802
        state = self.ecosystem.focus.stop()

        self._publish_workspace_event(
            PresenceEventType.FOCUS_CHANGED,
            "Focus session stopped",
            importance=.42,
            metadata={
                "active": False,
            },
        )

        self.dashboardStateChanged.emit(
            self.getDashboardState()
        )

        return _json(
            {
                "ok": True,
                "focus": state,
            }
        )

    @Slot(str, str, result=str)
    def createStudyProject(
        self,
        title: str,
        objective: str = "",
    ) -> str:  # noqa: N802
        try:
            project = self.ecosystem.study.create_project(
                title,
                objective=objective,
            )

            self._publish_workspace_event(
                PresenceEventType.STUDY_CHANGED,
                f"Study project created: "
                f"{project.get('title', title)}",
                importance=.58,
                metadata={
                    "project_id": project.get("id"),
                },
            )

            self.dashboardStateChanged.emit(
                self.getDashboardState()
            )

            return _json(
                {
                    "ok": True,
                    "project": project,
                }
            )

        except Exception as exc:
            return _json(
                {
                    "ok": False,
                    "error": str(exc),
                }
            )

    @Slot(str, str, str, result=str)
    def addStudyCard(
        self,
        project_id: str,
        prompt: str,
        answer: str,
    ) -> str:  # noqa: N802
        try:
            card = self.ecosystem.study.add_card(
                project_id,
                prompt,
                answer,
            )

            self._publish_workspace_event(
                PresenceEventType.STUDY_CHANGED,
                "A study card was added",
                importance=.46,
                metadata={
                    "project_id": project_id,
                    "card_id": card.get("id"),
                },
            )

            self.dashboardStateChanged.emit(
                self.getDashboardState()
            )

            return _json(
                {
                    "ok": True,
                    "card": card,
                }
            )

        except Exception as exc:
            return _json(
                {
                    "ok": False,
                    "error": str(exc),
                }
            )

    @Slot(str, str, int, result=str)
    def reviewStudyCard(
        self,
        project_id: str,
        card_id: str,
        score: int,
    ) -> str:  # noqa: N802
        try:
            card = self.ecosystem.study.review(
                project_id,
                card_id,
                score,
            )

            self._publish_workspace_event(
                PresenceEventType.STUDY_CHANGED,
                f"A study review was scored "
                f"{int(score)}/5",
                importance=.5,
                metadata={
                    "project_id": project_id,
                    "card_id": card_id,
                    "score": int(score),
                },
            )

            self.dashboardStateChanged.emit(
                self.getDashboardState()
            )

            return _json(
                {
                    "ok": True,
                    "card": card,
                }
            )

        except Exception as exc:
            return _json(
                {
                    "ok": False,
                    "error": str(exc),
                }
            )

    @Slot(str, result=str)
    def personalSearch(
        self,
        query: str,
    ) -> str:  # noqa: N802
        try:
            return _json(
                {
                    "ok": True,
                    "results": self.ecosystem.search.search(
                        query
                    ),
                }
            )

        except Exception as exc:
            return _json(
                {
                    "ok": False,
                    "error": str(exc),
                    "results": [],
                }
            )

    @Slot(result=str)
    def chooseSearchRoot(
        self,
    ) -> str:  # noqa: N802
        path = QFileDialog.getExistingDirectory(
            None,
            "Choose a folder Mary may search",
            "",
        )

        if not path:
            return _json(
                {
                    "selected": False,
                }
            )

        self.ecosystem.add_search_root(
            path
        )

        self.dashboardStateChanged.emit(
            self.getDashboardState()
        )

        return _json(
            {
                "selected": True,
                "path": path,
                "roots": [
                    str(x)
                    for x in self.ecosystem.search.roots
                ],
            }
        )

    @Slot(str, result=bool)
    def markNoticeRead(
        self,
        notice_id: str,
    ) -> bool:  # noqa: N802
        changed = self.ecosystem.inbox.mark_read(
            notice_id,
            True,
        )

        if changed:
            self.dashboardStateChanged.emit(
                self.getDashboardState()
            )

        return changed

    @Slot(str, str, result=str)
    def createResearchThread(
        self,
        title: str,
        question: str = "",
    ) -> str:  # noqa: N802
        try:
            thread = self.ecosystem.research.create(
                title,
                question=question,
            )

            self._publish_workspace_event(
                PresenceEventType.PROJECT_CHANGED,
                f"Research thread created: "
                f"{thread.get('title', title)}",
                importance=.57,
                metadata={
                    "thread_id": thread.get("id"),
                },
            )

            self.dashboardStateChanged.emit(
                self.getDashboardState()
            )

            return _json(
                {
                    "ok": True,
                    "thread": thread,
                }
            )

        except Exception as exc:
            return _json(
                {
                    "ok": False,
                    "error": str(exc),
                }
            )

    @Slot(str, str, str, result=str)
    def playArcade(
        self,
        key: str,
        payload: str = "",
        unused: str = "",
    ) -> str:  # noqa: N802
        try:
            return _json(
                {
                    "ok": True,
                    **self.ecosystem.arcade.play(
                        key,
                        payload,
                    ),
                }
            )

        except Exception as exc:
            return _json(
                {
                    "ok": False,
                    "error": str(exc),
                }
            )

    @Slot(result=str)
    def getPerformanceContext(self) -> str:  # noqa: N802
        try:
            if getattr(self.application, "authority", "") == "remote_mary_core":
                payload = self.application.gateway.runtime_action("performance.context.status")
            else:
                payload = self.application.mary.performance_context.status()
            return _json(payload)
        except Exception as exc:
            return _json({"ok": False, "error": f"{type(exc).__name__}: {exc}"})

    @Slot(str, result=str)
    def setPerformanceContext(self, mode: str) -> str:  # noqa: N802
        try:
            value = str(mode or "private")
            if getattr(self.application, "authority", "") == "remote_mary_core":
                payload = self.application.gateway.runtime_action(
                    "performance.context.set",
                    {"mode": value},
                )
            else:
                payload = self.application.mary.performance_context.set_mode(value)
            self.dashboardStateChanged.emit(self.getDashboardState())
            return _json(payload)
        except Exception as exc:
            return _json({"ok": False, "error": f"{type(exc).__name__}: {exc}"})

    @Slot(result=str)
    def getIdleAction(
        self,
    ) -> str:  # noqa: N802
        focus_active = bool(
            self.ecosystem.focus.snapshot().get(
                "active"
            )
        )

        maintenance = {}

        try:
            maintenance = (
                self.application.mary.mind.maintenance()
            )
        except Exception as exc:
            maintenance = {
                "error": f"{type(exc).__name__}: {exc}"
            }

        payload = self.ecosystem.presence.idle_tick(
            focus_active=focus_active
        )

        payload["mind_maintenance"] = maintenance

        return _json(payload)

    @Slot(result=str)
    def getIntegrationState(
        self,
    ) -> str:  # noqa: N802 - JS-facing API
        self.integrations.refresh()

        return _json(
            {
                "creative_apps": self.integrations.status(),
            }
        )

    @Slot(result=str)
    def getYouTubeStatus(
        self,
    ) -> str:  # noqa: N802
        return _json(
            self.ecosystem.youtube.status()
        )

    @Slot(str, result=str)
    def searchYouTube(
        self,
        query: str,
    ) -> str:  # noqa: N802
        try:
            results = self.ecosystem.youtube.search(
                query
            )

            self._publish_workspace_event(
                PresenceEventType.MEDIA_CHANGED,
                f"YouTube search requested: "
                f"{str(query or '').strip()[:120]}",
                importance=.38,
                metadata={
                    "result_count": len(results),
                    "source": "youtube_data_api",
                },
            )

            return _json(
                {
                    "ok": True,
                    "results": results,
                    "status": self.ecosystem.youtube.status(),
                }
            )

        except Exception as exc:
            return _json(
                {
                    "ok": False,
                    "error": str(exc),
                    "results": [],
                    "status": self.ecosystem.youtube.status(),
                }
            )

    @Slot(str, str, result=str)
    def saveYouTubeToResearch(
        self,
        title: str,
        url: str,
    ) -> str:  # noqa: N802
        try:
            thread = self.ecosystem.research.create(
                str(
                    title
                    or "YouTube research"
                ),
                question=str(
                    url
                    or ""
                ),
            )

            self._publish_workspace_event(
                PresenceEventType.PROJECT_CHANGED,
                f"Saved YouTube result to research: "
                f"{thread.get('title', title)}",
                importance=.48,
                metadata={
                    "thread_id": thread.get("id"),
                    "source": "youtube",
                },
            )

            self.dashboardStateChanged.emit(
                self.getDashboardState()
            )

            return _json(
                {
                    "ok": True,
                    "thread": thread,
                }
            )

        except Exception as exc:
            return _json(
                {
                    "ok": False,
                    "error": str(exc),
                }
            )

    @Slot(str, result=bool)
    def openExternalUrl(
        self,
        url: str,
    ) -> bool:  # noqa: N802 - JS-facing API
        value = str(
            url
            or ""
        ).strip()

        parsed = QUrl(
            value
        )

        if (
            parsed.scheme().lower()
            not in {
                "http",
                "https",
            }
            or not parsed.host()
        ):
            self.errorOccurred.emit(
                "Only http(s) links can be opened "
                "from Mary's media panel."
            )
            return False

        return bool(
            QDesktopServices.openUrl(
                parsed
            )
        )

    @Slot(str, str, result=bool)
    def launchCreativeApp(
        self,
        key: str,
        file_path: str = "",
    ) -> bool:  # noqa: N802
        try:
            self.integrations.launch(
                key,
                file_path=file_path or None,
            )
            return True

        except Exception as exc:
            self.errorOccurred.emit(
                f"{type(exc).__name__}: {exc}"
            )
            return False

    @Slot(result=str)
    def chooseMediaFile(
        self,
    ) -> str:  # noqa: N802 - JS-facing API
        path, _ = QFileDialog.getOpenFileName(
            None,
            "Choose music or audio for Mary",
            "",
            "Audio (*.mp3 *.wav *.ogg *.m4a *.flac);;"
            "All files (*)",
        )

        if not path:
            return _json(
                {
                    "selected": False,
                }
            )

        resolved = QUrl.fromLocalFile(
            path
        )

        return _json(
            {
                "selected": True,
                "path": path,
                "url": resolved.toString(),
            }
        )

    @Slot(result=str)
    def chooseCreativeFile(
        self,
    ) -> str:  # noqa: N802 - JS-facing API
        path, _ = QFileDialog.getOpenFileName(
            None,
            "Choose a creative project file",
            "",
            "Creative files "
            "(*.psd *.psb *.kra *.clip *.blend *.xcf *.txt *.md *.docx);;"
            "All files (*)",
        )

        return _json(
            {
                "selected": bool(path),
                "path": path or "",
            }
        )

    @Slot(result=str)
    def getCreativeWorkspaceState(
        self,
    ) -> str:  # noqa: N802 - JS-facing API
        try:
            return _json(
                self.creative_workspace.status()
            )

        except Exception as exc:
            return _json(
                {
                    "configured": False,
                    "error": f"{type(exc).__name__}: {exc}",
                    "files": [],
                }
            )

    @Slot(result=str)
    def chooseCreativeWorkspace(
        self,
    ) -> str:  # noqa: N802 - JS-facing API
        path = QFileDialog.getExistingDirectory(
            None,
            "Choose Unbeknownst / creative project folder",
            str(
                self.creative_workspace.root
                or ""
            ),
        )

        if not path:
            return _json(
                {
                    "selected": False,
                    **self.creative_workspace.status(),
                }
            )

        try:
            self.creative_workspace.set_root(
                path
            )

            self._publish_workspace_event(
                PresenceEventType.CREATIVE_CHANGED,
                "Creative workspace changed",
                importance=.56,
                metadata={
                    "configured": True,
                },
            )

            return _json(
                {
                    "selected": True,
                    **self.creative_workspace.status(),
                }
            )

        except Exception as exc:
            self.errorOccurred.emit(
                f"{type(exc).__name__}: {exc}"
            )

            return _json(
                {
                    "selected": False,
                    "configured": False,
                    "files": [],
                }
            )

    @Slot(str, result=str)
    def readCreativeTextFile(
        self,
        relative_path: str,
    ) -> str:  # noqa: N802 - JS-facing API
        try:
            return _json(
                {
                    "ok": True,
                    **self.creative_workspace.read_text(
                        relative_path
                    ),
                }
            )

        except Exception as exc:
            self.errorOccurred.emit(
                f"{type(exc).__name__}: {exc}"
            )

            return _json(
                {
                    "ok": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    @Slot(str, str, result=str)
    def saveCreativeTextFile(
        self,
        relative_path: str,
        content: str,
    ) -> str:  # noqa: N802 - JS-facing API
        try:
            result = self.creative_workspace.save_text(
                relative_path,
                content,
            )

            self._publish_workspace_event(
                PresenceEventType.CREATIVE_CHANGED,
                f"Creative text saved: {relative_path}",
                importance=.5,
                metadata={
                    "relative_path": str(relative_path)[:240],
                },
            )

            return _json(
                {
                    "ok": True,
                    **result,
                }
            )

        except Exception as exc:
            self.errorOccurred.emit(
                f"{type(exc).__name__}: {exc}"
            )

            return _json(
                {
                    "ok": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    @Slot(result=bool)
    def openCreativeWorkspaceFolder(
        self,
    ) -> bool:  # noqa: N802 - JS-facing API
        path = self.creative_workspace.root

        if path is None:
            self.errorOccurred.emit(
                "Choose a creative workspace in Studio first."
            )
            return False

        return bool(
            QDesktopServices.openUrl(
                QUrl.fromLocalFile(
                    str(path)
                )
            )
        )

    @Slot(result=bool)
    def openDataFolder(
        self,
    ) -> bool:  # noqa: N802 - JS-facing API
        if getattr(
            self.application,
            "authority",
            "",
        ) == "remote_mary_core":
            self.errorOccurred.emit(
                "Canonical Mary data is owned by the remote Core; "
                "Desktop does not keep a second authoritative data folder."
            )
            return False

        path = self.application.mary.config.paths.data

        path.mkdir(
            parents=True,
            exist_ok=True,
        )

        return bool(
            QDesktopServices.openUrl(
                QUrl.fromLocalFile(
                    str(path)
                )
            )
        )

    @Slot(result=bool)
    def openWorkspaceFolder(
        self,
    ) -> bool:  # noqa: N802 - JS-facing API
        path = self.application.mary.config.paths.workspace

        path.mkdir(
            parents=True,
            exist_ok=True,
        )

        return bool(
            QDesktopServices.openUrl(
                QUrl.fromLocalFile(
                    str(path)
                )
            )
        )

    @Slot()
    def minimizeWindow(
        self,
    ) -> None:  # noqa: N802
        self.minimizeRequested.emit()

    @Slot()
    def maximizeWindow(
        self,
    ) -> None:  # noqa: N802
        self.maximizeRequested.emit()

    @Slot()
    def closeWindow(
        self,
    ) -> None:  # noqa: N802
        self.closeRequested.emit()

    @Slot()
    def startWindowMove(
        self,
    ) -> None:  # noqa: N802
        self.windowMoveRequested.emit()

    def _emit_dashboard_state(
        self,
    ) -> None:
        """Refresh presentation state without making it turn authority."""
        try:
            payload = self.getDashboardState()
        except Exception as exc:
            print(
                "[MaryDesktop] dashboard projection unavailable: "
                f"{type(exc).__name__}: {exc}",
                flush=True,
            )
            return
        self.dashboardStateChanged.emit(payload)

    def _emit_character_state(
        self,
    ) -> None:
        """Best-effort UI projection; never abort a canonical conversation turn."""
        try:
            payload = self.getCharacterState()
        except Exception as exc:
            print(
                "[MaryDesktop] character projection unavailable: "
                f"{type(exc).__name__}: {exc}",
                flush=True,
            )
        else:
            self.characterStateChanged.emit(payload)

        self._emit_dashboard_state()

    @Slot()
    def save(
        self,
    ) -> None:
        try:
            self.application.save()

        except Exception as exc:
            self.errorOccurred.emit(
                f"{type(exc).__name__}: {exc}"
            )

    @Slot(result=str)
    def chooseCreatorImage(self) -> str:  # noqa: N802
        """Pick and normalize one image without exposing its filesystem path."""

        path, _ = QFileDialog.getOpenFileName(
            None,
            "Choose an image for Mary",
            "",
            "Images (*.jpg *.jpeg *.png *.webp)",
        )
        if not path:
            return _json({"ok": False, "cancelled": True})
        try:
            data = _prepare_creator_image(path)
        except Exception as exc:
            return _json({
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
            })
        self._creator_image_bytes = data
        return _json({
            "ok": True,
            "mime_type": "image/jpeg",
            "byte_count": len(data),
            "preview_data_url": (
                "data:image/jpeg;base64,"
                + base64.b64encode(data).decode("ascii")
            ),
            "raw_media_stored_by_core": False,
        })

    @Slot()
    def describeCreatorImage(self) -> None:  # noqa: N802
        if getattr(self.application, "authority", "") != "remote_mary_core":
            self.errorOccurred.emit(
                "Creator Lab vision requires canonical remote Mary Core on Desktop."
            )
            return
        if not self._creator_image_bytes:
            self.errorOccurred.emit("Choose a Creator Lab image first.")
            return
        if self._creator_image_thread is not None:
            self.errorOccurred.emit("Mary is already looking at a Creator Lab image.")
            return
        gateway = getattr(self.application, "gateway", None)
        if gateway is None:
            self.errorOccurred.emit("Mary Core gateway is unavailable.")
            return
        thread = QThread(self)
        worker = _CreatorImageVisionWorker(gateway, self._creator_image_bytes)
        worker.moveToThread(thread)
        self._creator_image_thread = thread
        self._creator_image_worker = worker
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_creator_image_finished)
        worker.failed.connect(self._on_creator_image_failed)
        thread.finished.connect(self._on_creator_image_thread_finished)
        thread.start()

    @Slot(str, str, str)
    def proposeCreatorSocial(
        self,
        brief: str,
        media_summary: str,
        tone: str,
    ) -> None:  # noqa: N802
        if getattr(self.application, "authority", "") != "remote_mary_core":
            self.errorOccurred.emit(
                "Creator Lab authoring requires canonical remote Mary Core."
            )
            return
        summary = " ".join(str(media_summary or "").split())[:12_000]
        if not summary:
            self.errorOccurred.emit("Visual grounding is required.")
            return
        if self._creator_social_thread is not None:
            self.errorOccurred.emit("Mary is already drafting in Creator Lab.")
            return
        gateway = getattr(self.application, "gateway", None)
        if gateway is None:
            self.errorOccurred.emit("Mary Core gateway is unavailable.")
            return
        thread = QThread(self)
        worker = _CreatorSocialWorker(
            gateway,
            str(brief or ""),
            summary,
            str(tone or "natural"),
        )
        worker.moveToThread(thread)
        self._creator_social_thread = thread
        self._creator_social_worker = worker
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_creator_social_finished)
        worker.failed.connect(self._on_creator_social_failed)
        thread.finished.connect(self._on_creator_social_thread_finished)
        thread.start()

    @Slot(str)
    def speakCreatorDraft(self, text: str) -> None:  # noqa: N802
        value = str(text or "").strip()[:12_000]
        if not value:
            self.errorOccurred.emit("Creator Lab draft is empty.")
            return
        if self._creator_voice_thread is not None:
            self.errorOccurred.emit("Creator Lab voice preview is already running.")
            return
        thread = QThread(self)
        worker = _CreatorDraftVoiceWorker(self.voice, self.audio_cache, value)
        worker.moveToThread(thread)
        self._creator_voice_thread = thread
        self._creator_voice_worker = worker
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_creator_voice_finished)
        worker.failed.connect(self._on_creator_voice_failed)
        thread.finished.connect(self._on_creator_voice_thread_finished)
        thread.start()

    @Slot(object)
    def _on_creator_image_finished(self, payload: object) -> None:
        self.creatorImageReady.emit(_json(dict(payload or {})))
        thread = self._creator_image_thread
        if thread is not None and thread.isRunning():
            thread.quit()

    @Slot(str)
    def _on_creator_image_failed(self, error: str) -> None:
        self.errorOccurred.emit(str(error))
        thread = self._creator_image_thread
        if thread is not None and thread.isRunning():
            thread.quit()

    @Slot()
    def _on_creator_image_thread_finished(self) -> None:
        self._creator_image_worker = None
        self._creator_image_thread = None

    @Slot(object)
    def _on_creator_social_finished(self, payload: object) -> None:
        self.creatorSocialReady.emit(_json(dict(payload or {})))
        thread = self._creator_social_thread
        if thread is not None and thread.isRunning():
            thread.quit()

    @Slot(str)
    def _on_creator_social_failed(self, error: str) -> None:
        self.errorOccurred.emit(str(error))
        thread = self._creator_social_thread
        if thread is not None and thread.isRunning():
            thread.quit()

    @Slot()
    def _on_creator_social_thread_finished(self) -> None:
        self._creator_social_worker = None
        self._creator_social_thread = None

    @Slot(object)
    def _on_creator_voice_finished(self, payload: object) -> None:
        self.creatorDraftVoiceReady.emit(_json(dict(payload or {})))
        thread = self._creator_voice_thread
        if thread is not None and thread.isRunning():
            thread.quit()

    @Slot(str)
    def _on_creator_voice_failed(self, error: str) -> None:
        self.errorOccurred.emit(str(error))
        thread = self._creator_voice_thread
        if thread is not None and thread.isRunning():
            thread.quit()

    @Slot()
    def _on_creator_voice_thread_finished(self) -> None:
        self._creator_voice_worker = None
        self._creator_voice_thread = None

    def close(
        self,
    ) -> None:
        self.presence_socket.stop()
        self.resident_hearing.disable()
        self.microphone.stop()
        presence_thread = self._presence_thread
        if presence_thread is not None and presence_thread.isRunning():
            presence_thread.quit()
            presence_thread.wait()

        speech_thread = self._speech_thread

        if (
            speech_thread is not None
            and speech_thread.isRunning()
        ):
            speech_thread.quit()
            speech_thread.wait()

        for creator_thread in (
            self._creator_image_thread,
            self._creator_social_thread,
            self._creator_voice_thread,
        ):
            if creator_thread is not None and creator_thread.isRunning():
                creator_thread.quit()
                creator_thread.wait()

        self._creator_image_bytes = b""
        self.audio_cache.cleanup()
        self.microphone.cleanup()

        thread = self._active_thread

        if (
            thread is not None
            and thread.isRunning()
        ):
            # Ask the pipeline to stop at the next stage boundary, then wait for
            # the in-flight synchronous provider call to return naturally.
            self.application.pipeline.cancel()
            thread.quit()
            thread.wait()

        self.application.close()

    @Slot(str)
    def _on_recording_ready(
        self,
        path: str,
    ) -> None:
        if self._speech_thread is not None:
            self.errorOccurred.emit(
                "Speech transcription is already active."
            )
            self.microphone.cleanup()
            return

        thread = QThread(
            self
        )

        worker = _TranscriptionWorker(
            self.stt,
            path,
        )

        worker.moveToThread(
            thread
        )

        self._speech_thread = thread
        self._speech_worker = worker

        thread.started.connect(
            worker.run
        )

        worker.finished.connect(
            self._on_transcription_finished
        )

        worker.failed.connect(
            self._on_transcription_failed
        )

        thread.finished.connect(
            self._on_speech_thread_finished
        )

        thread.start()

    @Slot(str)
    def _on_transcription_finished(
        self,
        text: str,
    ) -> None:
        value = str(
            text
            or ""
        ).strip()

        self.microphone.cleanup()

        self.listeningStateChanged.emit(
            "idle"
        )

        self._transition_conversation_state(
            DesktopConversationState.IDLE,
            reason="transcription_finished",
        )

        if value:
            self.transcriptionReady.emit(
                value
            )
        else:
            self.errorOccurred.emit(
                "No speech was detected in the recording."
            )

        self._finish_speech_thread()

    @Slot(str)
    def _on_transcription_failed(
        self,
        error: str,
    ) -> None:
        self.microphone.cleanup()

        self.listeningStateChanged.emit(
            "idle"
        )

        self._transition_conversation_state(
            DesktopConversationState.IDLE,
            reason="transcription_failed",
        )

        self.errorOccurred.emit(
            str(error)
        )

        self._finish_speech_thread()

    @Slot(str)
    def _on_microphone_error(
        self,
        error: str,
    ) -> None:
        self.listeningStateChanged.emit(
            "idle"
        )

        self._transition_conversation_state(
            DesktopConversationState.IDLE,
            reason="microphone_error",
        )

        self.errorOccurred.emit(
            str(error)
        )

    @Slot(str)
    def _on_microphone_state_changed(
        self,
        state: str,
    ) -> None:
        value = str(
            state
            or "idle"
        ).strip().lower()

        self.listeningStateChanged.emit(
            value
        )

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
    def _on_speech_thread_finished(
        self,
    ) -> None:
        self._speech_worker = None
        self._speech_thread = None
        self._resume_resident_hearing_if_idle()

    def _finish_speech_thread(
        self,
    ) -> None:
        thread = self._speech_thread

        if (
            thread is not None
            and thread.isRunning()
        ):
            thread.quit()

    def _transition_conversation_state(
        self,
        state: DesktopConversationState | str,
        *,
        reason: str,
    ) -> None:
        try:
            snapshot = self.conversation_runtime.transition(
                state,
                reason=reason,
            )

        except ValueError as exc:
            print(
                f"[MaryDesktop] conversation-state warning: {exc}",
                flush=True,
            )
            return

        # Keep the cross-client 13.1 realtime coordinator synchronized with
        # the already-proven desktop state machine. This remains presentation
        # coordination only and never mutates identity/memory.
        try:
            realtime = self.application.mary.realtime

            if snapshot.state == DesktopConversationState.SPEAKING:
                realtime.speech_started(
                    source="desktop_playback"
                )

            elif snapshot.state == DesktopConversationState.LISTENING:
                realtime.mark_listening(
                    True,
                    source="desktop_microphone",
                )

            elif snapshot.state == DesktopConversationState.TRANSCRIBING:
                realtime.mark_transcribing(
                    True,
                    source="desktop_stt",
                )

            elif snapshot.state == DesktopConversationState.INTERRUPTED:
                realtime.interrupt(
                    reason=snapshot.reason,
                    by_source="desktop",
                )

            elif snapshot.state == DesktopConversationState.IDLE:
                if (
                    realtime.status().get("phase")
                    == "speaking"
                ):
                    realtime.speech_ended(
                        reason=snapshot.reason
                    )
                else:
                    realtime.mark_listening(
                        False,
                        source="desktop_microphone",
                    )

                    realtime.mark_transcribing(
                        False,
                        source="desktop_stt",
                    )

        except Exception:
            pass

        print(
            f"[MaryDesktop] conversation state: "
            f"{snapshot.previous.value} -> "
            f"{snapshot.state.value} "
            f"({snapshot.reason})",
            flush=True,
        )

        self.conversationStateChanged.emit(
            _json(
                snapshot.to_dict()
            )
        )

        self.presence_socket.publish(
            "conversation_state",
            snapshot.to_dict(),
        )

        self._emit_character_state()

        if snapshot.state == DesktopConversationState.IDLE:
            self._resume_resident_hearing_if_idle()

    def _set_busy(
        self,
        value: bool,
    ) -> None:
        self._busy = bool(
            value
        )

        self.busyChanged.emit(
            self._busy
        )

    def _finalize_pending_turn_trace(
        self,
        *,
        reason: str,
    ) -> None:
        trace = self._pending_turn_trace

        if not trace:
            return

        timings = dict(
            trace.get("timings") or {}
        )

        submitted_at = (
            self._pending_turn_submitted_at
        )

        if submitted_at is not None:
            perceived_ms = round(
                (
                    monotonic()
                    - submitted_at
                )
                * 1000.0,
                2,
            )

            timings.setdefault(
                "perceived_ms",
                perceived_ms,
            )

            if reason == "voice_playback_started":
                timings.setdefault(
                    "playback_start_ms",
                    perceived_ms,
                )

        trace["timings"] = timings
        trace["completion_event"] = str(
            reason
        )

        self.ecosystem.record_turn(
            trace=trace
        )

        self.presence_socket.publish(
            "turn_trace",
            trace,
        )

        print(
            "[MaryDesktop] trace "
            f"provider={trace.get('provider', 'unknown')} "
            f"pipeline={timings.get('pipeline_ms', 'n/a')}ms "
            f"tts={timings.get('tts_synthesis_ms', 'n/a')}ms "
            f"ui={timings.get('ui_payload_ms', 'n/a')}ms "
            f"ready={timings.get('audio_ready_ms', 'n/a')}ms "
            f"perceived={timings.get('perceived_ms', 'n/a')}ms",
            flush=True,
        )

        self._pending_turn_trace = None
        self._pending_turn_submitted_at = None

        self._emit_dashboard_state()

    @Slot(object)
    def _on_presence_finished(self, payload: object) -> None:
        if not isinstance(payload, DesktopTurnPayload):
            self._finish_presence_thread()
            return
        payload_dict = payload.to_dict()
        runtime = dict(payload.runtime or {})
        delivery = dict(runtime.get("delivery_plan") or {})
        packet = dict(runtime.get("performance_packet") or {})
        provenance = dict(runtime.get("provenance") or {})
        self._last_feedback_context = {
            "user_text": "",
            "context_text": str(runtime.get("presence_context") or "Mary initiative")[:4000],
            "assistant_text": str(payload.canonical_text or payload.text),
            "source_kind": "mary_initiative",
            "input_authority": str(runtime.get("input_authority") or "environment_context_only"),
            "provider": str(provenance.get("provider") or "unknown"),
            "model": str(provenance.get("model") or "unknown"),
            "conversation_mode": "adaptive",
            "performance_context": str(packet.get("social_context") or "private"),
            "character_patterns": list(
                dict(delivery.get("metadata") or {}).get("performer_patterns", []) or []
            )[:12],
            "turn_id": str(runtime.get("turn_id") or ""),
        }
        self.messageReady.emit(_json(payload_dict))
        self.avatarStateChanged.emit(_json(payload.avatar))
        self._emit_character_state()
        voice = payload.voice
        if not bool(
            voice.get("enabled")
            and voice.get("status") == "success"
            and (voice.get("audio_url") or voice.get("audio_base64"))
        ):
            self._transition_conversation_state(
                DesktopConversationState.IDLE,
                reason="presence_finished_without_voice",
            )
        self._finish_presence_thread()

    @Slot(object)
    def _on_presence_silent(self, _payload: object) -> None:
        self._finish_presence_thread()

    @Slot(str)
    def _on_presence_failed(self, error: str) -> None:
        # Presence is optional.  A transient network/provider failure should not
        # interrupt the creator with an error toast every polling interval.
        print(f"[MaryDesktop] presence pulse failed: {error}", flush=True)
        self._finish_presence_thread()

    @Slot()
    def _on_presence_thread_finished(self) -> None:
        self._presence_worker = None
        self._presence_thread = None

    def _finish_presence_thread(self) -> None:
        thread = self._presence_thread
        if thread is not None and thread.isRunning():
            thread.quit()

    @Slot(object)
    def _on_turn_finished(
        self,
        payload: object,
    ) -> None:
        """Receive a successful turn on the GUI thread and release the UI."""

        if not isinstance(
            payload,
            DesktopTurnPayload,
        ):
            self._active_turn_submitted_at = None

            self._finish_thread()

            self._set_busy(
                False
            )

            self.errorOccurred.emit(
                "Mary's desktop worker returned "
                "an invalid response payload."
            )

            return

        self._set_busy(
            False
        )

        trace = dict(
            payload.runtime.get("trace")
            or {}
        )

        timings = dict(
            trace.get("timings")
            or {}
        )

        submitted_at = (
            self._active_turn_submitted_at
        )

        if submitted_at is not None:
            text_ready_ms = round(
                (
                    monotonic()
                    - submitted_at
                )
                * 1000.0,
                2,
            )

            timings[
                "text_ready_ms"
            ] = text_ready_ms

        trace[
            "timings"
        ] = timings

        self._pending_turn_trace = (
            trace
            or None
        )

        self._pending_turn_submitted_at = (
            submitted_at
        )

        self._active_turn_submitted_at = None

        payload_dict = (
            payload.to_dict()
        )

        payload_dict.setdefault(
            "runtime",
            {},
        )[
            "trace"
        ] = trace

        delivery = dict(payload.runtime.get("delivery_plan") or {})
        packet = dict(payload.runtime.get("performance_packet") or {})
        self._last_feedback_context = {
            "user_text": str(self._active_feedback_user_text or "")[:4000],
            "context_text": "",
            "assistant_text": str(payload.canonical_text or payload.text),
            "source_kind": "creator_turn",
            "input_authority": "creator",
            "provider": str(trace.get("provider") or "unknown"),
            "model": str(trace.get("model") or "unknown"),
            "conversation_mode": "adaptive",
            "performance_context": str(packet.get("social_context") or "private"),
            "character_patterns": list(
                dict(delivery.get("metadata") or {}).get("performer_patterns", []) or []
            )[:12],
            "turn_id": str(payload.runtime.get("turn_id") or ""),
        }
        self._active_feedback_user_text = ""

        self.messageReady.emit(
            _json(
                payload_dict
            )
        )

        self.avatarStateChanged.emit(
            _json(
                payload.avatar
            )
        )

        self._emit_character_state()

        voice = payload.voice

        voice_will_play = bool(
            voice.get("enabled")
            and voice.get("status") == "success"
            and (
                voice.get("audio_url")
                or voice.get("audio_base64")
            )
        )

        if not voice_will_play:
            self._finalize_pending_turn_trace(
                reason="text_ready"
            )

            self._transition_conversation_state(
                DesktopConversationState.IDLE,
                reason="turn_finished_without_voice",
            )

        avatar_error = str(
            payload.runtime.get(
                "avatar_error"
            )
            or ""
        ).strip()

        if avatar_error:
            print(
                f"[MaryDesktop] avatar presentation warning: "
                f"{avatar_error}",
                flush=True,
            )

        voice_error = str(
            payload.runtime.get(
                "voice_error"
            )
            or ""
        ).strip()

        if voice_error:
            print(
                f"[MaryDesktop] voice synthesis warning: "
                f"{voice_error}",
                flush=True,
            )

        self._finish_thread()

    @Slot(str)
    def _on_turn_failed(
        self,
        error: str,
    ) -> None:
        """Receive a failed turn on the GUI thread and always release input."""

        self._set_busy(
            False
        )

        self._active_turn_submitted_at = None
        self._active_feedback_user_text = ""

        self._transition_conversation_state(
            DesktopConversationState.IDLE,
            reason="turn_failed",
        )

        self.errorOccurred.emit(
            str(error)
        )

        self._finish_thread()

    @Slot()
    def _on_thread_finished(
        self,
    ) -> None:
        """Guard against a worker thread ending without a terminal signal."""

        if self._busy:
            self._set_busy(
                False
            )

            self._transition_conversation_state(
                DesktopConversationState.IDLE,
                reason="worker_stopped_without_response",
            )

            self.errorOccurred.emit(
                "Mary's desktop worker stopped "
                "without returning a response."
            )

        self._active_worker = None
        self._active_thread = None

    def _finish_thread(
        self,
    ) -> None:
        thread = self._active_thread

        if (
            thread is not None
            and thread.isRunning()
        ):
            thread.quit()