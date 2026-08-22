"""Bounded ephemeral event bus.  Presence events are context, not memory."""
from __future__ import annotations
from collections import deque
from typing import Iterable
from .events import PresenceEvent

class LiveContextBus:
    def __init__(self, limit: int = 200) -> None:
        self.events: deque[PresenceEvent] = deque(maxlen=max(20, int(limit)))
    def publish(self, event: PresenceEvent) -> None: self.events.append(event)
    def recent(self, limit: int = 30, *, sources: Iterable[str] | None = None) -> list[PresenceEvent]:
        allowed = {str(x) for x in sources} if sources else None
        values = [e for e in self.events if allowed is None or e.source in allowed]
        return values[-max(1, int(limit)):]
    def snapshot(self, limit: int = 20) -> list[dict]: return [e.to_dict() for e in self.recent(limit)]
