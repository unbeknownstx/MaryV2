"""User-perceived realtime latency milestones.

Backend completion time is not the same as character responsiveness. These
helpers record bounded per-turn milestones such as first visible reaction and
first audio without becoming a second tracing authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

VERSION = "13.70"


@dataclass(frozen=True)
class ExperienceLatency:
    turn_id: str
    started_ms: float
    first_token_ms: float | None = None
    first_visible_reaction_ms: float | None = None
    first_audio_ms: float | None = None
    completed_ms: float | None = None
    version: str = VERSION
    authority: str = "derived_observability"

    def _delta(self, value: float | None) -> float | None:
        if value is None:
            return None
        return round(max(0.0, float(value) - float(self.started_ms)), 2)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["ttft_ms"] = self._delta(self.first_token_ms)
        payload["time_to_first_visible_reaction_ms"] = self._delta(self.first_visible_reaction_ms)
        payload["time_to_first_audio_ms"] = self._delta(self.first_audio_ms)
        payload["turn_total_ms"] = self._delta(self.completed_ms)
        return payload
