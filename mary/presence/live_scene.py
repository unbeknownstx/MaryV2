"""Ephemeral situational-awareness model for MaryV2.

``LiveScene`` answers a deliberately narrow question: *what is happening
right now?*  It is not memory, personality, relationship authority, or a
second Mary state owner.  It is a bounded projection over realtime/presence
signals so cognition, streaming, voice and avatar presentation can share the
same current context.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Mapping


_RAW_MEDIA_KEYS = {
    "audio", "audio_bytes", "raw_audio", "image", "frame", "screenshot",
    "raw_image", "pixels", "base64", "token", "authorization", "api_key",
    "password", "secret",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _bounded(value: Any, *, limit: int = 500) -> Any:
    if isinstance(value, str):
        return value[:limit]
    if isinstance(value, (bool, int, float)) or value is None:
        return value
    if isinstance(value, Mapping):
        return {
            str(k)[:60]: _bounded(v, limit=160)
            for k, v in list(value.items())[:16]
            if str(k).casefold() not in _RAW_MEDIA_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [_bounded(item, limit=120) for item in list(value)[:16]]
    return str(value)[:limit]


@dataclass(frozen=True)
class SceneParticipant:
    participant_id: str
    role: str
    display_name: str = ""
    speaking: bool = False
    attention: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["attention"] = round(max(0.0, min(1.0, float(self.attention))), 3)
        data["metadata"] = _bounded(self.metadata)
        return data


@dataclass(frozen=True)
class SceneEvent:
    event_id: str
    kind: str
    source: str
    summary: str
    importance: float = 0.5
    created_at: str = field(default_factory=_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id[:120],
            "kind": self.kind[:80],
            "source": self.source[:80],
            "summary": " ".join(self.summary.split())[:700],
            "importance": round(max(0.0, min(1.0, float(self.importance))), 3),
            "created_at": self.created_at,
            "metadata": _bounded(self.metadata),
        }


class LiveScene:
    """Thread-safe bounded process-local scene state.

    The scene may be reconstructed from Presence/Attention events at any time.
    Nothing here is a durable claim about Mary or the creator.
    """

    VERSION = "1"

    def __init__(self, *, event_capacity: int = 48) -> None:
        self._lock = RLock()
        self.event_capacity = max(8, min(200, int(event_capacity)))
        self.mode = "companion"
        self.activity = ""
        self.project = ""
        self.workspace = ""
        self.selected_asset = ""
        self.floor_owner = "none"
        self.mary_target = ""
        self.mary_goal = ""
        self.realtime_phase = "idle"
        self.environment: dict[str, Any] = {}
        self.participants: dict[str, SceneParticipant] = {}
        self._events: list[SceneEvent] = []
        self.updated_at = _now()

    def _touch(self) -> None:
        self.updated_at = _now()

    def set_mode(self, mode: str) -> None:
        with self._lock:
            self.mode = (str(mode or "companion").strip().lower() or "companion")[:40]
            self._touch()

    def set_floor(self, owner: str, *, realtime_phase: str | None = None) -> None:
        normalized = str(owner or "none").strip().lower()
        if normalized not in {"none", "creator", "mary", "chat", "other"}:
            normalized = "other"
        with self._lock:
            self.floor_owner = normalized
            if realtime_phase is not None:
                self.realtime_phase = str(realtime_phase or "idle")[:40]
            self._touch()

    def set_context(
        self,
        *,
        activity: str | None = None,
        project: str | None = None,
        workspace: str | None = None,
        selected_asset: str | None = None,
        mary_target: str | None = None,
        mary_goal: str | None = None,
    ) -> None:
        with self._lock:
            if activity is not None:
                self.activity = str(activity)[:160]
            if project is not None:
                self.project = str(project)[:160]
            if workspace is not None:
                self.workspace = str(workspace)[:160]
            if selected_asset is not None:
                self.selected_asset = str(selected_asset)[:320]
            if mary_target is not None:
                self.mary_target = str(mary_target)[:120]
            if mary_goal is not None:
                self.mary_goal = str(mary_goal)[:300]
            self._touch()

    def set_environment(self, key: str, value: Any) -> None:
        normalized = str(key or "").strip()[:80]
        if not normalized or normalized.casefold() in _RAW_MEDIA_KEYS:
            return
        with self._lock:
            self.environment[normalized] = _bounded(value, limit=240)
            if len(self.environment) > 32:
                oldest = next(iter(self.environment))
                self.environment.pop(oldest, None)
            self._touch()

    def upsert_participant(self, participant: SceneParticipant) -> None:
        with self._lock:
            self.participants[participant.participant_id[:120]] = participant
            if len(self.participants) > 64:
                # Keep the creator and Mary if present; otherwise discard the
                # oldest insertion. Chat participant detail belongs elsewhere.
                for key in list(self.participants):
                    if key not in {"creator", "mary"}:
                        self.participants.pop(key, None)
                        break
            self._touch()

    def observe(
        self,
        *,
        event_id: str,
        kind: str,
        source: str,
        summary: str,
        importance: float = 0.5,
        metadata: Mapping[str, Any] | None = None,
    ) -> SceneEvent:
        event = SceneEvent(
            event_id=str(event_id or "")[:120],
            kind=str(kind or "event")[:80],
            source=str(source or "unknown")[:80],
            summary=str(summary or "")[:700],
            importance=importance,
            metadata=dict(metadata or {}),
        )
        with self._lock:
            self._events.append(event)
            self._events[:] = self._events[-self.event_capacity :]
            self._apply_event_hints(event)
            self._touch()
        return event

    def _apply_event_hints(self, event: SceneEvent) -> None:
        meta = dict(event.metadata or {})
        kind = event.kind.casefold()
        if kind in {"foreground_app", "obs_scene"}:
            self.environment[kind] = event.summary[:240]
        if kind in {"project_changed", "creative_changed"}:
            project = meta.get("project") or meta.get("project_name") or meta.get("title")
            if project:
                self.project = str(project)[:160]
        if kind in {"creator_speech", "creator_text"}:
            self.floor_owner = "creator"
        if kind in {"twitch_mention", "stream_mention"}:
            self.mary_target = str(meta.get("display_name") or meta.get("author") or "chat")[:120]

    def recent_events(self, limit: int = 16) -> list[dict[str, Any]]:
        with self._lock:
            return [item.to_dict() for item in self._events[-max(1, min(48, int(limit))):]]

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "version": self.VERSION,
                "mode": self.mode,
                "activity": self.activity,
                "project": self.project,
                "workspace": self.workspace,
                "selected_asset": self.selected_asset,
                "floor_owner": self.floor_owner,
                "realtime_phase": self.realtime_phase,
                "mary_target": self.mary_target,
                "mary_goal": self.mary_goal,
                "participants": {
                    key: value.to_dict()
                    for key, value in list(self.participants.items())[:32]
                },
                "environment": _bounded(self.environment),
                "recent_events": [item.to_dict() for item in self._events[-16:]],
                "updated_at": self.updated_at,
                "authority": "ephemeral_context_only",
                "persistence": "none",
                "semantics": "situational awareness; never identity, memory, relationship, or creator truth",
            }
