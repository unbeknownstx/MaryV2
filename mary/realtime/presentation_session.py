"""Unified presentation-session coordination for MaryV2.

Presentation sessions are ephemeral. They tie one Mary output to all presentation
side effects (TTS, captions, mouth motion, avatar speaking state, overlays) so a
barge-in or superseding response invalidates the entire old output atomically.
They never own identity, memory, relationship state, or cognition.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Callable
import uuid

CancelCallback = Callable[[str], None]


@dataclass
class PresentationSession:
    id: str = field(default_factory=lambda: f"presentation_{uuid.uuid4().hex[:12]}")
    turn_id: str | None = None
    source: str = "mary"
    active: bool = True
    reason: str = "active"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["metadata"] = {
            str(k)[:60]: str(v)[:160]
            for k, v in list(dict(self.metadata or {}).items())[:12]
            if str(k).casefold() not in {"token", "authorization", "api_key", "secret", "password"}
        }
        return out


class PresentationSessionManager:
    VERSION = "1"

    def __init__(self) -> None:
        self._lock = RLock()
        self._active: PresentationSession | None = None
        self._cancel: dict[str, list[CancelCallback]] = {}
        self._stats = {"started": 0, "finished": 0, "interrupted": 0, "stale_callbacks": 0}

    def start(self, *, turn_id: str | None = None, source: str = "mary", metadata: dict[str, Any] | None = None) -> PresentationSession:
        with self._lock:
            if self._active is not None and self._active.active:
                self._invalidate_locked(self._active.id, "superseded")
            session = PresentationSession(turn_id=turn_id, source=str(source or "mary")[:60], metadata=dict(metadata or {}))
            self._active = session
            self._cancel[session.id] = []
            self._stats["started"] += 1
            return session

    def accepts(self, session_id: str | None) -> bool:
        with self._lock:
            return bool(session_id and self._active is not None and self._active.active and self._active.id == str(session_id))

    def register_cancel(self, session_id: str, callback: CancelCallback) -> bool:
        with self._lock:
            if not self.accepts(session_id):
                self._stats["stale_callbacks"] += 1
                return False
            self._cancel.setdefault(str(session_id), []).append(callback)
            return True

    def finish(self, session_id: str | None = None, *, reason: str = "completed") -> bool:
        with self._lock:
            active = self._active
            if active is None:
                return False
            if session_id and active.id != str(session_id):
                self._stats["stale_callbacks"] += 1
                return False
            active.active = False
            active.reason = str(reason or "completed")[:160]
            self._cancel.pop(active.id, None)
            self._active = None
            self._stats["finished"] += 1
            return True

    def interrupt(self, *, reason: str = "barge_in") -> str | None:
        with self._lock:
            if self._active is None:
                return None
            sid = self._active.id
            self._invalidate_locked(sid, reason)
            self._stats["interrupted"] += 1
            return sid

    def _invalidate_locked(self, session_id: str, reason: str) -> None:
        active = self._active
        callbacks = list(self._cancel.pop(session_id, []))
        if active is not None and active.id == session_id:
            active.active = False
            active.reason = str(reason or "cancelled")[:160]
            self._active = None
        for callback in callbacks:
            try:
                callback(str(reason or "cancelled"))
            except Exception:
                continue

    @property
    def active(self) -> PresentationSession | None:
        with self._lock:
            return self._active

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "version": self.VERSION,
                "active": self._active.to_dict() if self._active else None,
                "stats": dict(self._stats),
                "covers": ["tts", "captions", "avatar_state", "mouth_animation", "stream_overlays"],
                "authority": "ephemeral presentation coordination only",
            }
