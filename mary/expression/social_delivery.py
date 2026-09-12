"""Provider-neutral social delivery direction for MaryV2 13.8.

The planner projects already-authoritative emotional/relational state into
bounded performance hints. Providers may interpret supported fields but cannot
invent Mary's relationship mode or emotional truth.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


@dataclass(frozen=True)
class SocialDeliveryEnvelope:
    warmth: float
    playfulness: float
    intimacy: float
    energy: float
    pace: float
    pause_density: float
    teasing: float
    softness: float
    relationship_mode: str
    privacy_scope: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["authority"] = "delivery_projection_only"
        return payload


class SocialDeliveryPlanner:
    BASE_BY_MODE = {
        "friend": (0.50, 0.35, 0.10),
        "close": (0.68, 0.50, 0.28),
        "romantic": (0.82, 0.58, 0.68),
        "partner": (0.90, 0.62, 0.82),
    }

    def build(self, *, relationship_mode: str, emotional_state: Any | None = None, privacy_scope: str = "private", teasing_allowed: bool = True) -> SocialDeliveryEnvelope:
        mode = relationship_mode if relationship_mode in self.BASE_BY_MODE else "friend"
        warmth, playfulness, intimacy = self.BASE_BY_MODE[mode]
        valence = _clamp((float(getattr(emotional_state, "valence", 0.0)) + 1.0) / 2.0)
        arousal = _clamp(float(getattr(emotional_state, "arousal", 0.35)))
        intensity = _clamp(float(getattr(emotional_state, "intensity", 0.35)))
        if privacy_scope != "private":
            intimacy *= 0.35
            warmth *= 0.92
            playfulness *= 0.90
        warmth = _clamp(warmth * 0.80 + valence * 0.20)
        energy = _clamp(0.25 + arousal * 0.55 + intensity * 0.20)
        return SocialDeliveryEnvelope(
            warmth=warmth,
            playfulness=_clamp(playfulness),
            intimacy=_clamp(intimacy),
            energy=energy,
            pace=_clamp(0.38 + energy * 0.42),
            pause_density=_clamp(0.70 - energy * 0.45),
            teasing=_clamp(playfulness * (0.75 if teasing_allowed else 0.0)),
            softness=_clamp(warmth * 0.55 + intimacy * 0.35 - arousal * 0.10),
            relationship_mode=mode,
            privacy_scope=privacy_scope,
        )
