"""Ephemeral cross-surface awareness for one canonical Mary.

Multiple clients may be connected to Mary Core at once.  This ledger keeps a
small, bounded set of *stage notes* so a turn on one surface can know what Mary
was just doing elsewhere without merging every client transcript or creating a
second conversation/memory authority.

The notes are process-local and intentionally lossy.  Durable conversation and
memory remain owned by their existing canonical systems.
"""
from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from threading import RLock
from typing import Any
import uuid

from mary.runtime.turn_observability import record_turn_stage

_SENSITIVE = {"token", "authorization", "api_key", "secret", "password", "audio", "image", "frame", "screenshot"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clip(value: Any, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]


@dataclass(frozen=True)
class SurfaceNote:
    surface: str
    direction: str
    role: str
    summary: str
    conversation_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    visibility: str = "private"
    note_id: str = field(default_factory=lambda: f"surface_note_{uuid.uuid4().hex[:12]}")
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["surface"] = _clip(self.surface, 80)
        payload["direction"] = _clip(self.direction, 24)
        payload["role"] = _clip(self.role, 40)
        payload["summary"] = _clip(self.summary, 420)
        payload["conversation_id"] = _clip(self.conversation_id, 120)
        payload["visibility"] = "public" if str(self.visibility).strip().lower() == "public" else "private"
        payload["metadata"] = {
            _clip(key, 48): _clip(value, 120)
            for key, value in list(dict(self.metadata or {}).items())[:8]
            if str(key).casefold() not in _SENSITIVE
        }
        return payload


class CrossSurfaceAwareness:
    """Bounded stage-note ledger shared by every client of one Mary Core."""

    VERSION = "1"

    def __init__(self, *, capacity: int = 96) -> None:
        self.capacity = max(16, min(512, int(capacity)))
        self._notes: deque[SurfaceNote] = deque(maxlen=self.capacity)
        self._lock = RLock()

    def record(
        self,
        *,
        surface: str,
        direction: str,
        role: str,
        summary: str,
        conversation_id: str = "",
        metadata: dict[str, Any] | None = None,
        visibility: str = "private",
    ) -> SurfaceNote | None:
        text = _clip(summary, 420)
        if not text:
            return None
        direction_value = str(direction or "event").strip().lower()
        if direction_value not in {"inbound", "outbound", "event"}:
            direction_value = "event"
        note = SurfaceNote(
            surface=_clip(surface or "unknown", 80),
            direction=direction_value,
            role=_clip(role or "unknown", 40),
            summary=text,
            conversation_id=_clip(conversation_id, 120),
            metadata=dict(metadata or {}),
            visibility="public" if str(visibility or "private").strip().lower() == "public" else "private",
        )
        with self._lock:
            # Coalesce exact adjacent echoes from a reconnect/replay.
            if self._notes:
                last = self._notes[-1]
                if (
                    last.surface == note.surface
                    and last.direction == note.direction
                    and last.role == note.role
                    and last.summary == note.summary
                ):
                    record_turn_stage(
                        "cross_surface_awareness", status="skipped", elapsed_ms=0.0, outcome="coalesced"
                    )
                    return last
            self._notes.append(note)
        record_turn_stage(
            "cross_surface_awareness", status="success", elapsed_ms=0.0, outcome="recorded"
        )
        return note

    def elsewhere(
        self,
        current_surface: str,
        *,
        limit: int = 4,
        current_visibility: str = "private",
    ) -> list[dict[str, Any]]:
        current = str(current_surface or "").strip().casefold()
        public_stage = str(current_visibility or "private").strip().casefold() == "public"
        with self._lock:
            chosen = [
                item for item in reversed(self._notes)
                if item.surface.strip().casefold() != current
                and (not public_stage or str(item.visibility).strip().casefold() == "public")
            ][: max(1, min(12, int(limit)))]
        chosen.reverse()
        return [item.to_dict() for item in chosen]

    def recent(self, *, limit: int = 12) -> list[dict[str, Any]]:
        with self._lock:
            return [item.to_dict() for item in list(self._notes)[-max(1, min(48, int(limit))):]]

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            count = len(self._notes)
        return {
            "version": self.VERSION,
            "count": count,
            "recent": self.recent(limit=12),
            "policy": (
                "ephemeral cross-surface stage notes only; durable conversation, memory, "
                "identity and relationship remain canonical elsewhere; private notes never flow into a public stage"
            ),
        }
