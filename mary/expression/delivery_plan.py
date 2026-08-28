"""Provider-independent vocal/gesture delivery plan for Mary.

The plan is deliberately presentation-only.  It is derived from Mary's
canonical TurnMind/character state and can be consumed by any surface (desktop,
mobile, stream overlay, future Live2D/VRM clients) without becoming personality,
memory, or relationship authority.
"""
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

    # Stage 12 performer projection.  These are bounded presentation cues, not
    # new character facts.  A surface that cannot render them simply ignores
    # them while text/voice remain valid.
    gesture_style: str = "natural"
    gaze_style: str = "engaged"
    head_style: str = "natural"
    reaction_style: str = "none"
    performance_beats: tuple[dict[str, Any], ...] = ()
    interruptible: bool = True

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
            "gesture_style": self.gesture_style,
            "gaze_style": self.gaze_style,
            "head_style": self.head_style,
            "reaction_style": self.reaction_style,
            "performance_beats": [dict(item) for item in self.performance_beats],
            "interruptible": bool(self.interruptible),
            "rationale": self.rationale,
            "metadata": dict(self.metadata),
        }
