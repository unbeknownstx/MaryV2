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

from PySide6.QtCore import QObject, QThread, Signal, Slot, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFileDialog

from mary.runtime.application import MaryApplication
from mary.desktop.voice import DesktopVoiceEngine
from mary.desktop.audio_cache import DesktopAudioCache
from mary.desktop.microphone import DesktopMicrophoneRecorder
from mary.desktop.stt import DesktopSpeechToText
from mary.desktop.dashboard import build_desktop_dashboard_state
from mary.desktop.integrations import DesktopIntegrationRegistry
from mary.desktop.projects import CreativeWorkspaceManager
from mary.desktop.turn_trace import build_turn_trace
from mary.ecosystem import MaryEcosystem
from mary.presence import PresenceEventType
from mary.presence.websocket_server import LocalPresenceWebSocket
from mary.conversation import ConversationLane, classify_conversation_lane
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
        audio_cache: DesktopAudioCache | None = None,
    ) -> None:
        super().__init__()
        self.application = application
        self.text = text
        self.voice = voice
        self.audio_cache = audio_cache

    @Slot()
    def run(self) -> None:
        started = monotonic()
        print("[MaryDesktop] turn started", flush=True)

        try:
            pipeline_started = monotonic()
            result = self.application.run(self.text)
            pipeline_ms = (monotonic() - pipeline_started) * 1000.0

            if not result.success:
                raise RuntimeError(
                    result.error or "Mary's pipeline did not complete."
                )

            response_text = str(result.output or "")
            mary = self.application.mary
            pipeline_values = dict(getattr(result, "metadata", {}).get("pipeline_values", {}) or {})
            cognitive_cycle = pipeline_values.get("cognitive_cycle")
            cycle_metadata = dict(getattr(cognitive_cycle, "metadata", {}) or {})
            delivery_plan = dict(cycle_metadata.get("delivery_plan", {}) or {})

            # Avatar presentation is best-effort. A visual-state defect must
            # never swallow an otherwise valid conversation response.
            avatar_error: str | None = None
            avatar_started = monotonic()
            try:
                mary.avatar.sync_emotion()
                avatar_state = mary.avatar.controller.present(
                    text=response_text,
                    speaking=False,
                    metadata={"surface": "desktop", "delivery_plan": delivery_plan},
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
            if self.audio_cache is not None and voice_payload.get("status") == "success":
                voice_payload = self.audio_cache.stage(voice_payload)
            spoken_text = str(voice_payload.get("spoken_text") or "").strip()
            display_text = spoken_text or response_text
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
            trace.setdefault("timings", {}).setdefault("voice_total_ms", round(voice_ms, 2))

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
                    "trace": trace,
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
    characterStateChanged = Signal(str)
    dashboardStateChanged = Signal(str)
    voicePlaybackStopRequested = Signal()
    minimizeRequested = Signal()
    maximizeRequested = Signal()
    closeRequested = Signal()
    windowMoveRequested = Signal()

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
        self.audio_cache = DesktopAudioCache()
        self.stt = DesktopSpeechToText.from_environment()
        self.microphone = DesktopMicrophoneRecorder()
        self.integrations = DesktopIntegrationRegistry()
        self.creative_workspace = CreativeWorkspaceManager()
        self.ecosystem = MaryEcosystem(self.application.mary)
        self.presence_socket = LocalPresenceWebSocket(self.ecosystem.snapshot)
        self.presence_socket.start()
        self._active_turn_submitted_at: float | None = None
        self._pending_turn_trace: dict[str, Any] | None = None
        self._pending_turn_submitted_at: float | None = None
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
            # Typed input is also a valid barge-in. Finalize perceived latency
            # for the interrupted voice turn before the next turn owns timing.
            self._finalize_pending_turn_trace(reason="interrupted")
            # Stop browser playback first, then begin the new canonical Mary turn.
            self._transition_conversation_state(
                DesktopConversationState.INTERRUPTED,
                reason="typed_barge_in",
            )
            self.voicePlaybackStopRequested.emit()

        self._active_turn_submitted_at = monotonic()
        lane = classify_conversation_lane(value)
        presentation_state = (
            DesktopConversationState.RESPONDING
            if lane.lane in {ConversationLane.SOCIAL_INSTANT, ConversationLane.CONVERSATION}
            else DesktopConversationState.THINKING
        )
        self._transition_conversation_state(
            presentation_state,
            reason=f"message_submitted:{lane.lane.value}",
        )
        self._set_busy(True)

        thread = QThread(self)
        worker = _ConversationWorker(self.application, value, self.voice, self.audio_cache)
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
        if self._busy or state in {DesktopConversationState.RESPONDING, DesktopConversationState.THINKING}:
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
            # Barge-in is authoritative here. Finalize the previous perceived
            # trace before microphone ownership replaces the speaking state.
            self._finalize_pending_turn_trace(reason="microphone_barge_in")
            # Browser playback is told to stop, then the microphone becomes the
            # active side of the conversation.
            self._transition_conversation_state(
                DesktopConversationState.INTERRUPTED,
                reason="microphone_barge_in",
            )
            self.voicePlaybackStopRequested.emit()

        self.microphone.start()

    @Slot()
    def stopListening(self) -> None:  # noqa: N802 - JS-facing API
        self.microphone.stop()

    @Slot(str)
    def voicePlaybackStage(self, stage: str) -> None:  # noqa: N802 - JS-facing API
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
        key = key_map.get(str(stage or "").strip().lower())
        if not key:
            return
        timings = dict(trace.get("timings") or {})
        timings.setdefault(key, round((monotonic() - submitted_at) * 1000.0, 2))
        trace["timings"] = timings

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
        self._finalize_pending_turn_trace(reason="voice_playback_started")
        self._transition_conversation_state(
            DesktopConversationState.SPEAKING,
            reason="voice_playback_started",
        )

    @Slot()
    def voicePlaybackFinished(self) -> None:  # noqa: N802 - JS-facing API
        self._finalize_pending_turn_trace(reason="voice_playback_finished")
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
                "presence_socket": self.presence_socket.status(),
                "realtime": mary.realtime.status(),
                "nodes": mary.node_registry.snapshot(),
            }
        )

    @Slot(result=str)
    def getAvatarState(self) -> str:  # noqa: N802 - JS-facing API
        return _json(self.application.mary.avatar.state.to_dict())

    @Slot(result=str)
    def getCharacterState(self) -> str:  # noqa: N802 - JS-facing API
        return _json(
            self.application.mary.live_state(
                runtime_status=self.conversation_runtime.state.value,
            )
        )

    @Slot(result=str)
    def getDashboardState(self) -> str:  # noqa: N802 - JS-facing API
        payload = build_desktop_dashboard_state(
            self.application.mary,
            runtime_status=self.conversation_runtime.state.value,
        )
        payload["ecosystem"] = self.ecosystem.snapshot()
        try:
            payload["mind"] = self.application.mary.mind.status()
        except Exception as exc:
            payload["mind"] = {"enabled": False, "error": f"{type(exc).__name__}: {exc}"}
        payload["realtime"] = self.application.mary.realtime.status()
        payload["nodes"] = self.application.mary.node_registry.snapshot()
        payload["retrieval"] = self.application.mary.mind.retrieval.status()
        payload["perception"] = self.application.mary.perception_director.snapshot()
        return _json(payload)

    @Slot(result=str)
    def getEcosystemState(self) -> str:  # noqa: N802
        return _json(self.ecosystem.snapshot())

    @Slot(result=str)
    def getMindStatus(self) -> str:  # noqa: N802
        try:
            return _json(self.application.mary.mind.status())
        except Exception as exc:
            return _json({"enabled": False, "error": f"{type(exc).__name__}: {exc}"})

    @Slot(result=str)
    def rebuildCognitiveReservoir(self) -> str:  # noqa: N802
        """Rebuild only Mary's derived local index; canonical state is untouched."""
        try:
            count = int(self.application.mary.mind.rebuild_reservoir())
            self.dashboardStateChanged.emit(self.getDashboardState())
            return _json({"ok": True, "records": count, "status": self.application.mary.mind.status()})
        except Exception as exc:
            return _json({"ok": False, "error": f"{type(exc).__name__}: {exc}"})

    @Slot(result=str)
    def getLastTurnTrace(self) -> str:  # noqa: N802
        """Return display-safe timing/provider metadata for the latest desktop turn."""
        return _json(self.ecosystem.metrics.last_turn())

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
    def addCommandItem(self, title: str, kind: str = "task") -> str:  # noqa: N802
        try:
            item = self.ecosystem.command.add(title, kind=kind or "task")
            self._publish_workspace_event(
                PresenceEventType.COMMAND_CHANGED,
                f"Command Center added {item.get('kind', 'item')}: {item.get('title', '')}",
                importance=.58,
                metadata={"item_id": item.get("id"), "status": item.get("status")},
            )
            self.dashboardStateChanged.emit(self.getDashboardState())
            return _json({"ok": True, "item": item})
        except Exception as exc:
            self.errorOccurred.emit(f"{type(exc).__name__}: {exc}")
            return _json({"ok": False, "error": str(exc)})

    @Slot(str, str, result=str)
    def updateCommandStatus(self, item_id: str, status: str) -> str:  # noqa: N802
        try:
            item = self.ecosystem.command.update(item_id, status=status)
            self._publish_workspace_event(
                PresenceEventType.COMMAND_CHANGED,
                f"Command Center updated {item.get('title', 'an item')} to {item.get('status', status)}",
                importance=.54,
                metadata={"item_id": item.get("id"), "status": item.get("status")},
            )
            self.dashboardStateChanged.emit(self.getDashboardState())
            return _json({"ok": True, "item": item})
        except Exception as exc:
            self.errorOccurred.emit(f"{type(exc).__name__}: {exc}")
            return _json({"ok": False, "error": str(exc)})

    @Slot(int, str, result=str)
    def startFocus(self, minutes: int, task: str = "") -> str:  # noqa: N802
        try:
            state = self.ecosystem.focus.start(minutes, task=task)
            self._publish_workspace_event(
                PresenceEventType.FOCUS_CHANGED,
                f"Focus started for {int(minutes)} minutes" + (f" on {task}" if task else ""),
                importance=.44,
                metadata={"active": True, "minutes": int(minutes)},
            )
            self.dashboardStateChanged.emit(self.getDashboardState())
            return _json({"ok": True, "focus": state})
        except Exception as exc:
            return _json({"ok": False, "error": str(exc)})

    @Slot(result=str)
    def stopFocus(self) -> str:  # noqa: N802
        state = self.ecosystem.focus.stop()
        self._publish_workspace_event(
            PresenceEventType.FOCUS_CHANGED,
            "Focus session stopped",
            importance=.42,
            metadata={"active": False},
        )
        self.dashboardStateChanged.emit(self.getDashboardState())
        return _json({"ok": True, "focus": state})

    @Slot(str, str, result=str)
    def createStudyProject(self, title: str, objective: str = "") -> str:  # noqa: N802
        try:
            project = self.ecosystem.study.create_project(title, objective=objective)
            self._publish_workspace_event(
                PresenceEventType.STUDY_CHANGED,
                f"Study project created: {project.get('title', title)}",
                importance=.58,
                metadata={"project_id": project.get("id")},
            )
            self.dashboardStateChanged.emit(self.getDashboardState())
            return _json({"ok": True, "project": project})
        except Exception as exc:
            return _json({"ok": False, "error": str(exc)})

    @Slot(str, str, str, result=str)
    def addStudyCard(self, project_id: str, prompt: str, answer: str) -> str:  # noqa: N802
        try:
            card = self.ecosystem.study.add_card(project_id, prompt, answer)
            self._publish_workspace_event(
                PresenceEventType.STUDY_CHANGED,
                "A study card was added",
                importance=.46,
                metadata={"project_id": project_id, "card_id": card.get("id")},
            )
            self.dashboardStateChanged.emit(self.getDashboardState())
            return _json({"ok": True, "card": card})
        except Exception as exc:
            return _json({"ok": False, "error": str(exc)})

    @Slot(str, str, int, result=str)
    def reviewStudyCard(self, project_id: str, card_id: str, score: int) -> str:  # noqa: N802
        try:
            card = self.ecosystem.study.review(project_id, card_id, score)
            self._publish_workspace_event(
                PresenceEventType.STUDY_CHANGED,
                f"A study review was scored {int(score)}/5",
                importance=.5,
                metadata={"project_id": project_id, "card_id": card_id, "score": int(score)},
            )
            self.dashboardStateChanged.emit(self.getDashboardState())
            return _json({"ok": True, "card": card})
        except Exception as exc:
            return _json({"ok": False, "error": str(exc)})

    @Slot(str, result=str)
    def personalSearch(self, query: str) -> str:  # noqa: N802
        try:
            return _json({"ok": True, "results": self.ecosystem.search.search(query)})
        except Exception as exc:
            return _json({"ok": False, "error": str(exc), "results": []})

    @Slot(result=str)
    def chooseSearchRoot(self) -> str:  # noqa: N802
        path = QFileDialog.getExistingDirectory(None, "Choose a folder Mary may search", "")
        if not path:
            return _json({"selected": False})
        self.ecosystem.add_search_root(path)
        self.dashboardStateChanged.emit(self.getDashboardState())
        return _json({"selected": True, "path": path, "roots": [str(x) for x in self.ecosystem.search.roots]})

    @Slot(str, result=bool)
    def markNoticeRead(self, notice_id: str) -> bool:  # noqa: N802
        changed = self.ecosystem.inbox.mark_read(notice_id, True)
        if changed:
            self.dashboardStateChanged.emit(self.getDashboardState())
        return changed

    @Slot(str, str, result=str)
    def createResearchThread(self, title: str, question: str = "") -> str:  # noqa: N802
        try:
            thread = self.ecosystem.research.create(title, question=question)
            self._publish_workspace_event(
                PresenceEventType.PROJECT_CHANGED,
                f"Research thread created: {thread.get('title', title)}",
                importance=.57,
                metadata={"thread_id": thread.get("id")},
            )
            self.dashboardStateChanged.emit(self.getDashboardState())
            return _json({"ok": True, "thread": thread})
        except Exception as exc:
            return _json({"ok": False, "error": str(exc)})

    @Slot(str, str, str, result=str)
    def playArcade(self, key: str, payload: str = "", unused: str = "") -> str:  # noqa: N802
        try:
            return _json({"ok": True, **self.ecosystem.arcade.play(key, payload)})
        except Exception as exc:
            return _json({"ok": False, "error": str(exc)})

    @Slot(result=str)
    def getIdleAction(self) -> str:  # noqa: N802
        focus_active = bool(self.ecosystem.focus.snapshot().get("active"))
        maintenance = {}
        try:
            maintenance = self.application.mary.mind.maintenance()
        except Exception as exc:
            maintenance = {"error": f"{type(exc).__name__}: {exc}"}
        payload = self.ecosystem.presence.idle_tick(focus_active=focus_active)
        payload["mind_maintenance"] = maintenance
        return _json(payload)

    @Slot(result=str)
    def getIntegrationState(self) -> str:  # noqa: N802 - JS-facing API
        self.integrations.refresh()
        return _json({"creative_apps": self.integrations.status()})

    @Slot(result=str)
    def getYouTubeStatus(self) -> str:  # noqa: N802
        return _json(self.ecosystem.youtube.status())

    @Slot(str, result=str)
    def searchYouTube(self, query: str) -> str:  # noqa: N802
        try:
            results = self.ecosystem.youtube.search(query)
            self._publish_workspace_event(
                PresenceEventType.MEDIA_CHANGED,
                f"YouTube search requested: {str(query or '').strip()[:120]}",
                importance=.38,
                metadata={"result_count": len(results), "source": "youtube_data_api"},
            )
            return _json({"ok": True, "results": results, "status": self.ecosystem.youtube.status()})
        except Exception as exc:
            return _json({"ok": False, "error": str(exc), "results": [], "status": self.ecosystem.youtube.status()})

    @Slot(str, str, result=str)
    def saveYouTubeToResearch(self, title: str, url: str) -> str:  # noqa: N802
        try:
            thread = self.ecosystem.research.create(str(title or "YouTube research"), question=str(url or ""))
            self._publish_workspace_event(
                PresenceEventType.PROJECT_CHANGED,
                f"Saved YouTube result to research: {thread.get('title', title)}",
                importance=.48,
                metadata={"thread_id": thread.get("id"), "source": "youtube"},
            )
            self.dashboardStateChanged.emit(self.getDashboardState())
            return _json({"ok": True, "thread": thread})
        except Exception as exc:
            return _json({"ok": False, "error": str(exc)})

    @Slot(str, result=bool)
    def openExternalUrl(self, url: str) -> bool:  # noqa: N802 - JS-facing API
        value = str(url or "").strip()
        parsed = QUrl(value)
        if parsed.scheme().lower() not in {"http", "https"} or not parsed.host():
            self.errorOccurred.emit("Only http(s) links can be opened from Mary's media panel.")
            return False
        return bool(QDesktopServices.openUrl(parsed))

    @Slot(str, str, result=bool)
    def launchCreativeApp(self, key: str, file_path: str = "") -> bool:  # noqa: N802
        try:
            self.integrations.launch(key, file_path=file_path or None)
            return True
        except Exception as exc:
            self.errorOccurred.emit(f"{type(exc).__name__}: {exc}")
            return False

    @Slot(result=str)
    def chooseMediaFile(self) -> str:  # noqa: N802 - JS-facing API
        path, _ = QFileDialog.getOpenFileName(
            None,
            "Choose music or audio for Mary",
            "",
            "Audio (*.mp3 *.wav *.ogg *.m4a *.flac);;All files (*)",
        )
        if not path:
            return _json({"selected": False})
        resolved = QUrl.fromLocalFile(path)
        return _json({"selected": True, "path": path, "url": resolved.toString()})

    @Slot(result=str)
    def chooseCreativeFile(self) -> str:  # noqa: N802 - JS-facing API
        path, _ = QFileDialog.getOpenFileName(
            None,
            "Choose a creative project file",
            "",
            "Creative files (*.psd *.psb *.kra *.clip *.blend *.xcf *.txt *.md *.docx);;All files (*)",
        )
        return _json({"selected": bool(path), "path": path or ""})

    @Slot(result=str)
    def getCreativeWorkspaceState(self) -> str:  # noqa: N802 - JS-facing API
        try:
            return _json(self.creative_workspace.status())
        except Exception as exc:
            return _json({"configured": False, "error": f"{type(exc).__name__}: {exc}", "files": []})

    @Slot(result=str)
    def chooseCreativeWorkspace(self) -> str:  # noqa: N802 - JS-facing API
        path = QFileDialog.getExistingDirectory(
            None,
            "Choose Unbeknownst / creative project folder",
            str(self.creative_workspace.root or ""),
        )
        if not path:
            return _json({"selected": False, **self.creative_workspace.status()})
        try:
            self.creative_workspace.set_root(path)
            self._publish_workspace_event(
                PresenceEventType.CREATIVE_CHANGED,
                "Creative workspace changed",
                importance=.56,
                metadata={"configured": True},
            )
            return _json({"selected": True, **self.creative_workspace.status()})
        except Exception as exc:
            self.errorOccurred.emit(f"{type(exc).__name__}: {exc}")
            return _json({"selected": False, "configured": False, "files": []})

    @Slot(str, result=str)
    def readCreativeTextFile(self, relative_path: str) -> str:  # noqa: N802 - JS-facing API
        try:
            return _json({"ok": True, **self.creative_workspace.read_text(relative_path)})
        except Exception as exc:
            self.errorOccurred.emit(f"{type(exc).__name__}: {exc}")
            return _json({"ok": False, "error": f"{type(exc).__name__}: {exc}"})

    @Slot(str, str, result=str)
    def saveCreativeTextFile(self, relative_path: str, content: str) -> str:  # noqa: N802 - JS-facing API
        try:
            result = self.creative_workspace.save_text(relative_path, content)
            self._publish_workspace_event(
                PresenceEventType.CREATIVE_CHANGED,
                f"Creative text saved: {relative_path}",
                importance=.5,
                metadata={"relative_path": str(relative_path)[:240]},
            )
            return _json({"ok": True, **result})
        except Exception as exc:
            self.errorOccurred.emit(f"{type(exc).__name__}: {exc}")
            return _json({"ok": False, "error": f"{type(exc).__name__}: {exc}"})

    @Slot(result=bool)
    def openCreativeWorkspaceFolder(self) -> bool:  # noqa: N802 - JS-facing API
        path = self.creative_workspace.root
        if path is None:
            self.errorOccurred.emit("Choose a creative workspace in Studio first.")
            return False
        return bool(QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))))

    @Slot(result=bool)
    def openDataFolder(self) -> bool:  # noqa: N802 - JS-facing API
        path = self.application.mary.config.paths.data
        path.mkdir(parents=True, exist_ok=True)
        return bool(QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))))

    @Slot(result=bool)
    def openWorkspaceFolder(self) -> bool:  # noqa: N802 - JS-facing API
        path = self.application.mary.config.paths.workspace
        path.mkdir(parents=True, exist_ok=True)
        return bool(QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))))

    @Slot()
    def minimizeWindow(self) -> None:  # noqa: N802
        self.minimizeRequested.emit()

    @Slot()
    def maximizeWindow(self) -> None:  # noqa: N802
        self.maximizeRequested.emit()

    @Slot()
    def closeWindow(self) -> None:  # noqa: N802
        self.closeRequested.emit()

    @Slot()
    def startWindowMove(self) -> None:  # noqa: N802
        self.windowMoveRequested.emit()

    def _emit_character_state(self) -> None:
        self.characterStateChanged.emit(self.getCharacterState())
        self.dashboardStateChanged.emit(self.getDashboardState())

    @Slot()
    def save(self) -> None:
        try:
            self.application.save()
        except Exception as exc:
            self.errorOccurred.emit(f"{type(exc).__name__}: {exc}")

    def close(self) -> None:
        self.presence_socket.stop()
        self.microphone.stop()
        self.audio_cache.cleanup()
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
        # Keep the cross-client 13.1 realtime coordinator synchronized with
        # the already-proven desktop state machine. This remains presentation
        # coordination only and never mutates identity/memory.
        try:
            realtime = self.application.mary.realtime
            if snapshot.state == DesktopConversationState.SPEAKING:
                realtime.speech_started(source="desktop_playback")
            elif snapshot.state == DesktopConversationState.LISTENING:
                realtime.mark_listening(True, source="desktop_microphone")
            elif snapshot.state == DesktopConversationState.TRANSCRIBING:
                realtime.mark_transcribing(True, source="desktop_stt")
            elif snapshot.state == DesktopConversationState.INTERRUPTED:
                realtime.interrupt(reason=snapshot.reason, by_source="desktop")
            elif snapshot.state == DesktopConversationState.IDLE:
                if realtime.status().get("phase") == "speaking":
                    realtime.speech_ended(reason=snapshot.reason)
                else:
                    realtime.mark_listening(False, source="desktop_microphone")
                    realtime.mark_transcribing(False, source="desktop_stt")
        except Exception:
            pass

        print(
            f"[MaryDesktop] conversation state: "
            f"{snapshot.previous.value} -> {snapshot.state.value} "
            f"({snapshot.reason})",
            flush=True,
        )
        self.conversationStateChanged.emit(_json(snapshot.to_dict()))
        self.presence_socket.publish("conversation_state", snapshot.to_dict())
        self._emit_character_state()

    def _set_busy(self, value: bool) -> None:
        self._busy = bool(value)
        self.busyChanged.emit(self._busy)

    def _finalize_pending_turn_trace(self, *, reason: str) -> None:
        trace = self._pending_turn_trace
        if not trace:
            return
        timings = dict(trace.get("timings") or {})
        submitted_at = self._pending_turn_submitted_at
        if submitted_at is not None:
            perceived_ms = round((monotonic() - submitted_at) * 1000.0, 2)
            timings.setdefault("perceived_ms", perceived_ms)
            if reason == "voice_playback_started":
                timings.setdefault("playback_start_ms", perceived_ms)
        trace["timings"] = timings
        trace["completion_event"] = str(reason)
        self.ecosystem.record_turn(trace=trace)
        self.presence_socket.publish("turn_trace", trace)
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
        self.dashboardStateChanged.emit(self.getDashboardState())

    @Slot(object)
    def _on_turn_finished(self, payload: object) -> None:
        """Receive a successful turn on the GUI thread and release the UI."""

        if not isinstance(payload, DesktopTurnPayload):
            self._active_turn_submitted_at = None
            self._finish_thread()
            self._set_busy(False)
            self.errorOccurred.emit(
                "Mary's desktop worker returned an invalid response payload."
            )
            return

        self._set_busy(False)
        trace = dict(payload.runtime.get("trace") or {})
        timings = dict(trace.get("timings") or {})
        submitted_at = self._active_turn_submitted_at
        if submitted_at is not None:
            text_ready_ms = round((monotonic() - submitted_at) * 1000.0, 2)
            timings["text_ready_ms"] = text_ready_ms
        trace["timings"] = timings
        self._pending_turn_trace = trace or None
        self._pending_turn_submitted_at = submitted_at
        self._active_turn_submitted_at = None

        payload_dict = payload.to_dict()
        payload_dict.setdefault("runtime", {})["trace"] = trace
        self.messageReady.emit(_json(payload_dict))
        self.avatarStateChanged.emit(_json(payload.avatar))
        self._emit_character_state()

        voice = payload.voice
        voice_will_play = bool(
            voice.get("enabled")
            and voice.get("status") == "success"
            and (voice.get("audio_url") or voice.get("audio_base64"))
        )
        if not voice_will_play:
            self._finalize_pending_turn_trace(reason="text_ready")
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
        self._active_turn_submitted_at = None
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
