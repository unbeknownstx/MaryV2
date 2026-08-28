"""Remote Desktop compatibility view over the canonical Mary Core.

This module exists to let the mature Desktop bridge migrate to the Mary Protocol
without constructing a second MaryApplication.  It is deliberately a
presentation/client adapter, not a state owner.

Canonical identity, memory, relationship, workspace, cognition, and growth stay
on the remote Core.  Desktop-local capabilities (voice playback, microphone,
filesystem search, YouTube lookup, creative apps, UI telemetry) stay on the
Desktop machine.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from types import SimpleNamespace
from typing import Any

from mary.avatar import AvatarBridge
from mary.expression.emotion import Emotion, EmotionalState
from mary.integrations.youtube import YouTubeSearch
from mary.productivity import PersonalSearch, RuntimeMetrics
from mary.productivity.arcade import MaryArcade
from mary.runtime.gateway import RemoteMaryGateway
from mary.skills import SkillRegistry


@dataclass
class _RemotePipelineResult:
    success: bool
    output: str
    turn_id: str
    elapsed: float
    metadata: dict[str, Any]
    error: str | None = None


class _RemotePipelineView:
    def __init__(self, gateway: RemoteMaryGateway) -> None:
        self.gateway = gateway

    def cancel(self) -> None:
        try:
            self.gateway.runtime_action(
                "realtime.interrupt",
                {"reason": "desktop_cancel"},
            )
        except Exception:
            pass


class _RemoteRealtimeView:
    def __init__(self, gateway: RemoteMaryGateway) -> None:
        self.gateway = gateway

    def status(self) -> dict[str, Any]:
        return dict(self.gateway.conversation().get("realtime", {}) or {})

    def speech_started(self, *, turn_id: str | None = None, source: str = "desktop") -> None:
        self.gateway.runtime_action(
            "realtime.speech_started",
            {"turn_id": turn_id, "source": source},
        )

    def speech_ended(self, *, reason: str = "speech_finished") -> None:
        self.gateway.runtime_action(
            "realtime.speech_ended",
            {"reason": reason},
        )

    def interrupt(self, *, reason: str = "desktop_barge_in", by_source: str = "desktop") -> None:
        self.gateway.runtime_action(
            "realtime.interrupt",
            {"reason": reason, "by_source": by_source},
        )

    def mark_listening(self, value: bool, *, source: str = "desktop_microphone") -> None:
        self.gateway.runtime_action(
            "realtime.listening",
            {"active": bool(value), "source": source},
        )

    def mark_transcribing(self, value: bool, *, source: str = "desktop_stt") -> None:
        self.gateway.runtime_action(
            "realtime.transcribing",
            {"active": bool(value), "source": source},
        )


class _RemoteNodeRegistryView:
    def __init__(self, gateway: RemoteMaryGateway) -> None:
        self.gateway = gateway

    def snapshot(self) -> dict[str, Any]:
        return dict(self.gateway.state().get("nodes", {}) or {})


class _RemoteRetrievalView:
    def __init__(self, gateway: RemoteMaryGateway) -> None:
        self.gateway = gateway

    def status(self) -> dict[str, Any]:
        return dict(self.gateway.state().get("retrieval", {}) or {})


class _RemoteMindView:
    def __init__(self, gateway: RemoteMaryGateway) -> None:
        self.gateway = gateway
        self.retrieval = _RemoteRetrievalView(gateway)

    def status(self) -> dict[str, Any]:
        return dict(self.gateway.state().get("mind", {}) or {})

    def rebuild_reservoir(self) -> int:
        payload = self.gateway.runtime_action("mind.rebuild_reservoir")
        return int(payload.get("records", 0) or 0)

    def maintenance(self) -> dict[str, Any]:
        return dict(self.gateway.runtime_action("mind.maintenance") or {})


class _RemotePerceptionView:
    def __init__(self, gateway: RemoteMaryGateway) -> None:
        self.gateway = gateway

    def snapshot(self) -> dict[str, Any]:
        return dict(self.gateway.state().get("perception", {}) or {})


class _RemoteEmotionView:
    def __init__(self) -> None:
        self.state = EmotionalState()

    def update(self, payload: dict[str, Any] | None) -> None:
        values = dict(payload or {})
        raw_primary = str(values.get("primary") or "neutral").strip().lower()
        try:
            primary = Emotion(raw_primary)
        except ValueError:
            primary = Emotion.NEUTRAL
        self.state = EmotionalState(
            primary=primary,
            intensity=float(values.get("intensity", 0.0) or 0.0),
            valence=float(values.get("valence", 0.0) or 0.0),
            arousal=float(values.get("arousal", 0.0) or 0.0),
            confidence=float(values.get("confidence", 1.0) or 1.0),
        )


class _RemoteMaryView:
    """Display/capability projection of remote Mary; never an identity owner."""

    def __init__(
        self,
        gateway: RemoteMaryGateway,
        *,
        project_root: Path,
    ) -> None:
        self.gateway = gateway
        self.emotion = _RemoteEmotionView()
        self.avatar = AvatarBridge(emotion_manager=self.emotion)
        self.avatar.ready()
        self.realtime = _RemoteRealtimeView(gateway)
        self.node_registry = _RemoteNodeRegistryView(gateway)
        self.mind = _RemoteMindView(gateway)
        self.perception_director = _RemotePerceptionView(gateway)
        self.config = SimpleNamespace(
            paths=SimpleNamespace(
                root=project_root,
                workspace=Path(
                    str(
                        Path.home()
                        / "MaryV2Workspace"
                    )
                ),
                data=project_root / "data",
            )
        )

    def status(self) -> dict[str, Any]:
        live = self.live_state()
        character = dict(live.get("character", {}) or {})
        model = dict(live.get("model", {}) or {})
        return {
            "name": character.get("name", "Mary"),
            "cognition": {
                "llm": model.get("provider", "remote/core"),
                "model": model.get("model", "n/a"),
            },
        }

    def live_state(self, *, runtime_status: str | None = None) -> dict[str, Any]:
        # runtime_status is presentation-local and does not mutate canonical Core state.
        state = dict(self.gateway.state().get("mary", {}) or {})
        if runtime_status:
            character = dict(state.get("character", {}) or {})
            character["status"] = str(runtime_status)
            state["character"] = character
        return state

    def update_from_display_hints(self, hints: dict[str, Any] | None, text: str) -> None:
        values = dict(hints or {})
        self.emotion.update(dict(values.get("emotion", {}) or {}))
        try:
            self.avatar.sync_emotion(self.emotion.state)
            self.avatar.controller.present(
                text=text,
                speaking=False,
                metadata={
                    "surface": "desktop",
                    "authority": "remote_mary_core",
                    "delivery_plan": dict(values.get("delivery_plan", {}) or {}),
                },
            )
        except Exception:
            pass


class _CommandView:
    def __init__(self, gateway: RemoteMaryGateway) -> None:
        self.gateway = gateway

    def add(self, title: str, *, kind: str = "task", priority: int = 2, notes: str = ""):
        return self.gateway.workspace_action(
            "command.add",
            {"title": title, "kind": kind, "priority": priority, "notes": notes},
        )["item"]

    def update(self, item_id: str, **changes):
        return self.gateway.workspace_action(
            "command.update",
            {"item_id": item_id, **changes},
        )["item"]


class _FocusView:
    def __init__(self, gateway: RemoteMaryGateway) -> None:
        self.gateway = gateway

    def snapshot(self):
        return dict(self.gateway.workspace().get("focus", {}) or {})

    def start(self, minutes: int, *, task: str = ""):
        return self.gateway.workspace_action(
            "focus.start",
            {"minutes": int(minutes), "task": task},
        )["focus"]

    def stop(self, *, completed: bool = True):
        return self.gateway.workspace_action(
            "focus.stop",
            {"completed": bool(completed)},
        )["focus"]


class _StudyView:
    def __init__(self, gateway: RemoteMaryGateway) -> None:
        self.gateway = gateway

    def create_project(self, title: str, *, objective: str = ""):
        return self.gateway.workspace_action(
            "study.create_project",
            {"title": title, "objective": objective},
        )["project"]

    def add_card(self, project_id: str, prompt: str, answer: str, *, tags=None):
        return self.gateway.workspace_action(
            "study.add_card",
            {"project_id": project_id, "prompt": prompt, "answer": answer, "tags": list(tags or [])},
        )["card"]

    def review(self, project_id: str, card_id: str, score: int):
        return self.gateway.workspace_action(
            "study.review_card",
            {"project_id": project_id, "card_id": card_id, "score": int(score)},
        )["card"]


class _ResearchView:
    def __init__(self, gateway: RemoteMaryGateway) -> None:
        self.gateway = gateway

    def create(self, title: str, *, question: str = ""):
        return self.gateway.workspace_action(
            "research.create_thread",
            {"title": title, "question": question},
        )["thread"]

    def add_note(self, thread_id: str, text: str, *, source: str = "", url: str = ""):
        return self.gateway.workspace_action(
            "research.add_note",
            {"thread_id": thread_id, "text": text, "source": source, "url": url},
        )["note"]


class _InboxView:
    def __init__(self, gateway: RemoteMaryGateway) -> None:
        self.gateway = gateway

    def mark_read(self, notice_id: str, read: bool = True):
        return bool(
            self.gateway.workspace_action(
                "inbox.mark_read",
                {"notice_id": notice_id, "read": bool(read)},
            ).get("changed")
        )


class _PresenceView:
    def __init__(self, gateway: RemoteMaryGateway) -> None:
        self.gateway = gateway

    def snapshot(self):
        return dict(self.gateway.workspace().get("presence", {}) or {})

    def idle_tick(self, *, focus_active: bool = False):
        try:
            return self.gateway.runtime_action(
                "presence.idle_tick",
                {"focus_active": bool(focus_active)},
            )
        except Exception:
            return {
                "action": {"name": "idle", "duration": 0},
                "behavior": {},
                "mode": "quiet",
                "focus_quiet": bool(focus_active),
                "authority": "remote_core_compatibility_fallback",
            }

    def pulse(
        self,
        *,
        surface_visible: bool = True,
        focus_active: bool | None = None,
        conversation_id: str = "creator-primary",
    ) -> dict[str, Any]:
        """Ask canonical Core for at most one grounded Mary initiative.

        This is deliberately a cheap poll: Core returns silence without a model
        call unless Presence arbitration (or represented curiosity) clears.
        """

        values: dict[str, Any] = {
            "surface": "desktop",
            "surface_visible": bool(surface_visible),
            "conversation_id": str(conversation_id or "creator-primary"),
        }
        if focus_active is not None:
            values["focus_active"] = bool(focus_active)
        return dict(self.gateway.runtime_action("presence.pulse", values) or {})


class _RemoteEcosystemView:
    """Desktop compatibility surface over canonical workspace + local capabilities."""

    def __init__(
        self,
        gateway: RemoteMaryGateway,
        *,
        project_root: Path,
    ) -> None:
        self.gateway = gateway
        self.command = _CommandView(gateway)
        self.focus = _FocusView(gateway)
        self.study = _StudyView(gateway)
        self.research = _ResearchView(gateway)
        self.inbox = _InboxView(gateway)
        self.presence = _PresenceView(gateway)
        self.metrics = RuntimeMetrics()
        self.youtube = YouTubeSearch()
        self.arcade = MaryArcade()
        self.skills = SkillRegistry()
        workspace_root = Path.home() / "MaryV2Workspace"
        roots = [path for path in (workspace_root, project_root) if path.exists()]
        self.search = PersonalSearch(roots)

    def add_search_root(self, path: str | Path) -> None:
        self.search.add_root(path)

    def workspace_snapshot(self) -> dict[str, Any]:
        return dict(self.gateway.workspace() or {})

    def snapshot(self) -> dict[str, Any]:
        shared = self.workspace_snapshot()
        return {
            **shared,
            "arcade": {"games": self.arcade.games()},
            "metrics": self.metrics.snapshot(),
            "last_turn": self.metrics.last_turn(),
            "skills": self.skills.snapshot(),
            "external": {"youtube": self.youtube.status()},
            "paths": {"search_roots": [str(path) for path in self.search.roots]},
            "semantics": {
                **dict(shared.get("semantics", {}) or {}),
                "desktop_projection": "canonical workspace plus device-local capabilities",
            },
        }

    def publish_workspace_event(self, *args, **kwargs) -> dict[str, Any]:
        # Canonical workspace mutations already publish Presence on Core.
        return {"ok": True, "authority": "remote_mary_core"}

    def record_turn(self, *, elapsed: float | None = None, trace: dict[str, Any] | None = None) -> None:
        if elapsed is not None:
            self.metrics.record("mary_turn", elapsed)
        if trace:
            self.metrics.record_turn_trace(trace)


class RemoteMaryApplicationView:
    """Presentation compatibility adapter; never a MaryApplication owner."""

    authority = "remote_mary_core"

    def __init__(
        self,
        gateway: RemoteMaryGateway,
        *,
        project_root: Path,
        conversation_id: str = "creator-primary",
    ) -> None:
        self.gateway = gateway
        self.device_id = gateway.device_id
        self.project_root = Path(project_root).resolve()
        self.conversation_id = str(conversation_id or "creator-primary")
        self.mary = _RemoteMaryView(gateway, project_root=self.project_root)
        self.ecosystem = _RemoteEcosystemView(gateway, project_root=self.project_root)
        self.pipeline = _RemotePipelineView(gateway)
        self.state = SimpleNamespace(to_dict=lambda: dict(self.gateway.state().get("runtime", {}) or {}))

    def run(self, text: str, *, metadata: dict[str, Any] | None = None) -> _RemotePipelineResult:
        values = dict(metadata or {})
        conversation_id = str(values.get("conversation_id") or self.conversation_id)
        requested_mode = values.get("requested_mode")
        voice_input = bool(values.get("voice_input", False))
        started = monotonic()
        response = self.gateway.turn(
            text,
            conversation_id=conversation_id,
            requested_mode=str(requested_mode) if requested_mode else None,
            voice_input=voice_input,
        )
        elapsed = monotonic() - started
        hints = dict(response.display_hints or {})
        self.mary.update_from_display_hints(hints, response.text)

        reasoning = SimpleNamespace(metadata={
            **dict(response.provenance or {}),
            "generation_purpose": dict(response.provenance or {}).get("route") or "remote/core",
        })
        reflection = SimpleNamespace(metadata={"mode": "remote/core"})
        cycle = SimpleNamespace(
            reasoning=reasoning,
            reflection=reflection,
            metadata={
                "delivery_plan": dict(hints.get("delivery_plan", {}) or {}),
                "performance_packet": dict(hints.get("performance_packet", {}) or {}),
                "performance_context": dict(hints.get("performance_context", {}) or {}),
                "dialogue_plan": dict(hints.get("dialogue_plan", {}) or {}),
                "timings": dict(hints.get("timings", {}) or {}),
            },
        )

        return _RemotePipelineResult(
            success=True,
            output=response.text,
            turn_id=response.turn_id,
            elapsed=elapsed,
            metadata={
                "pipeline_values": {"cognitive_cycle": cycle},
                "realtime": dict(hints.get("realtime", {}) or {}),
                "authority": "remote_mary_core",
            },
        )

    def dashboard_state(self, *, runtime_status: str = "idle") -> dict[str, Any]:
        try:
            payload = dict(self.gateway.dashboard() or {})
        except Exception:
            state = self.gateway.state()
            payload = {
                "live": dict(state.get("mary", {}) or {}),
                "mind": dict(state.get("mind", {}) or {}),
                "nodes": dict(state.get("nodes", {}) or {}),
                "retrieval": dict(state.get("retrieval", {}) or {}),
                "perception": dict(state.get("perception", {}) or {}),
                "realtime": dict(self.gateway.conversation().get("realtime", {}) or {}),
            }

        live = dict(payload.get("live", {}) or {})
        if live:
            character = dict(live.get("character", {}) or {})
            character["status"] = str(runtime_status)
            live["character"] = character
            payload["live"] = live
        payload["ecosystem"] = self.ecosystem.snapshot()
        payload["authority"] = {
            "mode": "remote_mary_core",
            "device_id": self.gateway.device_id,
            "surface": "desktop",
        }
        return payload

    def save(self) -> None:
        # Core-owned state persists on Core; Desktop must not write a local copy.
        return None

    def close(self) -> None:
        # Closing a client must never shut down canonical Mary Core.
        return None
