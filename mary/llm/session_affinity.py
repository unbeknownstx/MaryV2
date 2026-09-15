"""Bounded process-local model affinity for conversational continuity.

Affinity is a routing hint, never identity or memory. It stores only opaque
session/model identifiers and expires automatically.
"""
from __future__ import annotations

from dataclasses import dataclass
import time

VERSION = "13.61"

@dataclass
class _Affinity:
    model_id: str
    expires_at: float

class SessionAffinityBook:
    def __init__(self, ttl_seconds: float = 1800.0, max_sessions: int = 256) -> None:
        self.ttl_seconds = max(30.0, min(10800.0, float(ttl_seconds)))
        self.max_sessions = max(8, min(2048, int(max_sessions)))
        self._items: dict[str, _Affinity] = {}

    def get(self, session_id: str, *, now: float | None = None) -> str | None:
        key = str(session_id).strip()[:128]
        if not key: return None
        current = time.monotonic() if now is None else float(now)
        item = self._items.get(key)
        if item is None: return None
        if item.expires_at <= current:
            self._items.pop(key, None)
            return None
        return item.model_id

    def set(self, session_id: str, model_id: str, *, now: float | None = None) -> None:
        key, model = str(session_id).strip()[:128], str(model_id).strip()[:192]
        if not key or not model: return
        current = time.monotonic() if now is None else float(now)
        if key not in self._items and len(self._items) >= self.max_sessions:
            oldest = min(self._items, key=lambda k: self._items[k].expires_at)
            self._items.pop(oldest, None)
        self._items[key] = _Affinity(model, current + self.ttl_seconds)

    def clear(self, session_id: str | None = None) -> None:
        if session_id is None: self._items.clear()
        else: self._items.pop(str(session_id).strip()[:128], None)

    def snapshot(self) -> dict[str, object]:
        return {"version": VERSION, "active_sessions": len(self._items), "authority": "routing_hint_only", "content_retained": False}
