"""Bounded process-local tracker for user-perceived response milestones."""
from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
from typing import Any

from .experience_latency import ExperienceLatency


@dataclass
class _TurnMilestones:
    started_ms: float
    first_token_ms: float | None = None
    first_visible_reaction_ms: float | None = None
    first_audio_ms: float | None = None
    completed_ms: float | None = None


class ExperienceLatencyTracker:
    VERSION = "13.71"

    def __init__(self, capacity: int = 128) -> None:
        self.capacity = max(16, min(2048, int(capacity)))
        self._items: dict[str, _TurnMilestones] = {}
        self._order: list[str] = []

    @staticmethod
    def now_ms() -> float:
        return monotonic() * 1000.0

    def start(self, turn_id: str, *, at_ms: float | None = None) -> None:
        key = str(turn_id or "").strip()[:240]
        if not key:
            raise ValueError("turn_id is required")
        self._items[key] = _TurnMilestones(self.now_ms() if at_ms is None else float(at_ms))
        self._order.append(key)
        while len(self._order) > self.capacity:
            expired = self._order.pop(0)
            self._items.pop(expired, None)

    def mark(self, turn_id: str, milestone: str, *, at_ms: float | None = None) -> None:
        key = str(turn_id or "").strip()[:240]
        item = self._items.get(key)
        if item is None:
            raise KeyError(key)
        field = {
            "first_token": "first_token_ms",
            "first_visible_reaction": "first_visible_reaction_ms",
            "first_audio": "first_audio_ms",
            "completed": "completed_ms",
        }.get(str(milestone or "").strip().lower())
        if field is None:
            raise ValueError("unsupported experience milestone")
        if getattr(item, field) is None:
            setattr(item, field, self.now_ms() if at_ms is None else float(at_ms))

    def get(self, turn_id: str) -> dict[str, Any]:
        key = str(turn_id or "").strip()[:240]
        item = self._items.get(key)
        if item is None:
            raise KeyError(key)
        return ExperienceLatency(turn_id=key, **item.__dict__).to_dict()

    def status(self) -> dict[str, Any]:
        recent = [self.get(key) for key in self._order[-12:] if key in self._items]
        return {
            "version": self.VERSION,
            "count": len(self._items),
            "recent": recent,
            "authority": "derived_observability",
            "persistence": "process_local",
        }
