"""Planning layer for Mary's current-culture/world awareness.

WorldPulse deliberately does not access the network itself.  It tells an
approved research client which topical lanes are stale and what bounded search
queries would refresh them.  Retrieved results must still enter WorldContext as
source-attributed ephemeral items.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Any


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class WorldPulseLane:
    lane: str
    query: str
    refresh_hours: float
    ttl_hours: float
    priority: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_DEFAULT_LANES = (
    WorldPulseLane("internet_culture", "current internet culture memes and creator trends", 6.0, 18.0, .70),
    WorldPulseLane("games", "current popular games gaming releases and gaming community trends", 12.0, 36.0, .65),
    WorldPulseLane("anime", "current anime releases popular anime and anime community trends", 24.0, 72.0, .50),
    WorldPulseLane("music", "current music releases popular songs and music culture trends", 24.0, 72.0, .45),
    WorldPulseLane("film_tv", "current movies television streaming releases and entertainment trends", 24.0, 72.0, .45),
    WorldPulseLane("art_creator", "current digital art animation creator tools and creator community trends", 24.0, 72.0, .55),
    WorldPulseLane("technology_ai", "current AI technology developer tools and major product developments", 12.0, 36.0, .60),
    WorldPulseLane("general_news", "major current news people are likely to discuss today", 8.0, 24.0, .40),
)


class WorldPulsePlanner:
    """Ephemeral freshness ledger for explicit/approved world refreshes."""

    VERSION = "1"

    def __init__(self, lanes: tuple[WorldPulseLane, ...] = _DEFAULT_LANES) -> None:
        self._lock = RLock()
        self.lanes = {item.lane: item for item in lanes}
        self._last_refresh: dict[str, datetime] = {}

    def mark_refreshed(self, lane: str, *, when: datetime | None = None) -> None:
        name = str(lane or "").strip().casefold()
        if name not in self.lanes:
            return
        with self._lock:
            self._last_refresh[name] = when or _now()

    def due(self, *, limit: int = 8, force: bool = False) -> list[dict[str, Any]]:
        now = _now()
        candidates: list[tuple[float, WorldPulseLane, datetime | None]] = []
        with self._lock:
            refreshed = dict(self._last_refresh)
        for lane in self.lanes.values():
            last = refreshed.get(lane.lane)
            stale = force or last is None or now >= last + timedelta(hours=max(.25, lane.refresh_hours))
            if not stale:
                continue
            age_bonus = 1.0 if last is None else min(1.0, max(0.0, (now - last).total_seconds() / 86400.0))
            candidates.append((lane.priority + age_bonus * .15, lane, last))
        candidates.sort(key=lambda item: item[0], reverse=True)
        output = []
        for _, lane, last in candidates[: max(1, min(16, int(limit)))]:
            output.append({
                **lane.to_dict(),
                "last_refresh": last.isoformat() if last else None,
                "authority": "research_plan_only",
            })
        return output

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            refreshed = {key: value.isoformat() for key, value in self._last_refresh.items()}
        return {
            "version": self.VERSION,
            "lanes": [item.to_dict() for item in self.lanes.values()],
            "last_refresh": refreshed,
            "due": self.due(limit=8),
            "policy": "planner only; network research requires an explicit approved research path",
        }
