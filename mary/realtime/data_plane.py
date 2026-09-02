"""Bounded high-rate realtime data plane for MaryV2.

The existing AttentionBus remains the cognitive attention gate.  This data
plane is intentionally earlier and cheaper: audio/activity/chat/telemetry can
arrive here at high rate, be bounded/coalesced, and only meaningful summaries
need promotion into Attention/Presence.
"""
from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from threading import RLock
from typing import Any
import uuid


_SENSITIVE = {"audio", "audio_bytes", "raw_audio", "frame", "screenshot", "pixels", "base64", "token", "authorization", "secret", "password", "api_key"}


@dataclass(frozen=True)
class RealtimeDatum:
    kind: str
    source: str
    summary: str = ""
    salience: float = 0.0
    correlation_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: f"rt_{uuid.uuid4().hex[:12]}")
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["salience"] = round(max(0.0, min(1.0, float(self.salience))), 3)
        payload["summary"] = " ".join(str(self.summary).split())[:500]
        payload["metadata"] = {
            str(k)[:60]: (str(v)[:160] if not isinstance(v, (bool, int, float)) else v)
            for k, v in list(dict(self.metadata or {}).items())[:16]
            if str(k).casefold() not in _SENSITIVE and not isinstance(v, (bytes, bytearray, memoryview))
        }
        return payload


class RealtimeDataPlane:
    VERSION = "1"

    def __init__(self, *, capacity: int = 256) -> None:
        self.capacity = max(32, min(2048, int(capacity)))
        self._lock = RLock()
        self._items: deque[RealtimeDatum] = deque(maxlen=self.capacity)
        self._counts: dict[str, int] = {}

    def publish(self, datum: RealtimeDatum) -> RealtimeDatum:
        with self._lock:
            self._items.append(datum)
            self._counts[datum.kind] = int(self._counts.get(datum.kind, 0)) + 1
        return datum

    def recent(self, *, kind: str | None = None, limit: int = 32) -> list[RealtimeDatum]:
        with self._lock:
            items = list(self._items)
        if kind:
            normalized = str(kind).strip().casefold()
            items = [item for item in items if item.kind.casefold() == normalized]
        return items[-max(1, min(128, int(limit))):]

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "version": self.VERSION,
                "buffered": len(self._items),
                "capacity": self.capacity,
                "counts": dict(self._counts),
                "recent": [item.to_dict() for item in list(self._items)[-12:]],
                "policy": "high-rate ephemeral transport; promote summaries to Attention/Presence, never raw media to memory",
            }
