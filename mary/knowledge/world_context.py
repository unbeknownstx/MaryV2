"""Bounded, source-attributed current-world context for MaryV2.

World context is intentionally ephemeral.  It helps Mary understand current
culture/news/games/memes without converting today's internet into permanent
identity, preference, or knowledge truth.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Any
import uuid


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class WorldContextItem:
    topic: str
    summary: str
    source: str
    lane: str = "general"
    confidence: float = 0.5
    ttl_hours: float = 24.0
    url: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: f"world_{uuid.uuid4().hex[:12]}")
    observed_at: str = field(default_factory=lambda: _now().isoformat())

    @property
    def expires_at(self) -> datetime:
        try:
            observed = datetime.fromisoformat(self.observed_at.replace("Z", "+00:00"))
        except Exception:
            observed = _now()
        return observed + timedelta(hours=max(0.25, min(24 * 30, float(self.ttl_hours))))

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["topic"] = self.topic[:180]
        payload["summary"] = " ".join(self.summary.split())[:1000]
        payload["source"] = self.source[:180]
        payload["lane"] = self.lane[:60]
        payload["confidence"] = round(max(0.0, min(1.0, float(self.confidence))), 3)
        payload["url"] = self.url[:500]
        payload["expires_at"] = self.expires_at.isoformat()
        payload["metadata"] = {
            str(k)[:60]: str(v)[:180]
            for k, v in list(dict(self.metadata or {}).items())[:12]
            if str(k).casefold() not in {"token", "authorization", "api_key", "secret", "password"}
        }
        return payload


class WorldContextStore:
    VERSION = "1"

    def __init__(self, *, capacity: int = 256) -> None:
        self.capacity = max(32, min(2048, int(capacity)))
        self._lock = RLock()
        self._items: list[WorldContextItem] = []

    def _prune_locked(self) -> None:
        now = _now()
        self._items[:] = [item for item in self._items if item.expires_at > now][-self.capacity :]

    def ingest(self, item: WorldContextItem) -> WorldContextItem:
        with self._lock:
            self._prune_locked()
            fingerprint = (item.lane.casefold(), item.topic.casefold(), item.source.casefold())
            self._items[:] = [
                existing for existing in self._items
                if (existing.lane.casefold(), existing.topic.casefold(), existing.source.casefold()) != fingerprint
            ]
            self._items.append(item)
            self._items[:] = self._items[-self.capacity :]
        return item

    def replace_lane(self, lane: str, items: list[WorldContextItem]) -> None:
        normalized = str(lane).casefold()
        with self._lock:
            self._prune_locked()
            self._items[:] = [item for item in self._items if item.lane.casefold() != normalized]
            for item in items[: self.capacity]:
                self._items.append(item)
            self._items[:] = self._items[-self.capacity :]

    def relevant(self, query: str, *, limit: int = 8) -> list[WorldContextItem]:
        terms = {term.casefold() for term in str(query).split() if len(term) > 2}
        with self._lock:
            self._prune_locked()
            items = list(self._items)
        scored: list[tuple[float, WorldContextItem]] = []
        for item in items:
            haystack = f"{item.topic} {item.summary} {item.lane}".casefold()
            lexical = sum(1.0 for term in terms if term in haystack)
            if lexical <= 0:
                continue
            scored.append((lexical + item.confidence * .25, item))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [item for _, item in scored[: max(1, int(limit))]]

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            self._prune_locked()
            items = list(self._items)
        lanes: dict[str, int] = {}
        for item in items:
            lanes[item.lane] = int(lanes.get(item.lane, 0)) + 1
        return {
            "version": self.VERSION,
            "count": len(items),
            "lanes": lanes,
            "recent": [item.to_dict() for item in items[-20:]],
            "authority": "ephemeral_external_context_only",
            "policy": "current-world awareness expires; it never mutates character canon or creator truth automatically",
        }
