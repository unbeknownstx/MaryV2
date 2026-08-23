"""Provider-independent vocal/gesture delivery plan for Mary."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DeliveryPlan:
    profile: str = "neutral"
    energy: float = 0.45
    warmth: float = 0.55
    pace: float = 1.0
    stability: float = 0.42
    style: float = 0.11
    emphasis: float = 0.35
    pause_style: str = "conversational"
    avatar_expression: str = "neutral"
    gesture_energy: float = 0.35
    rationale: str = "neutral delivery"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "energy": round(float(self.energy), 3),
            "warmth": round(float(self.warmth), 3),
            "pace": round(float(self.pace), 3),
            "stability": round(float(self.stability), 3),
            "style": round(float(self.style), 3),
            "emphasis": round(float(self.emphasis), 3),
            "pause_style": self.pause_style,
            "avatar_expression": self.avatar_expression,
            "gesture_energy": round(float(self.gesture_energy), 3),
            "rationale": self.rationale,
            "metadata": dict(self.metadata),
        }
