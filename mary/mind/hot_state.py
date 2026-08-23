"""Small in-RAM projection of character state needed constantly in dialogue."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from time import monotonic
from typing import Any


@dataclass
class HotMindState:
    """Bounded process-local state cached for low-latency character decisions.

    This state is never authoritative.  It can be rebuilt from Mary's existing
    systems at any time and therefore must never be the sole source of a durable
    fact, identity claim, or relationship fact.
    """

    values: dict[str, Any] = field(default_factory=dict)
    refreshed_at: float = 0.0
    refresh_count: int = 0

    def refresh(self, mary: Any) -> dict[str, Any]:
        creator_profile: dict[str, Any] = {}
        try:
            creator_profile = dict(mary.user_model.current_profile())
        except Exception:
            pass

        emotion: dict[str, Any] = {}
        try:
            emotion = dict(mary.emotion.state.to_dict())
        except Exception:
            pass

        recent_dialogue: list[dict[str, Any]] = []
        try:
            recent_dialogue = list(mary.dialogue.messages_for_llm(limit=6))
        except Exception:
            pass

        active_goals: list[dict[str, Any]] = []
        try:
            for goal in list(mary.agency.goals.get_active_goals())[:6]:
                active_goals.append(goal.to_dict() if hasattr(goal, "to_dict") else dict(goal))
        except Exception:
            pass

        curiosities: list[dict[str, Any]] = []
        try:
            for item in list(mary.agency.curiosities.get_exploring_curiosities())[:4]:
                curiosities.append(dict(item))
        except Exception:
            pass

        self.values = {
            "mary_name": str(getattr(mary.identity, "name", "Mary") or "Mary"),
            "creator_name": str(getattr(mary.user_model, "name", "Unbe") or "Unbe"),
            "creator_profile": creator_profile,
            "emotion": emotion,
            "recent_dialogue": recent_dialogue,
            "active_goals": active_goals,
            "curiosities": curiosities,
            "dialogue_turn": int(getattr(getattr(mary.dialogue, "state", None), "turn_number", 0) or 0),
        }
        self.refreshed_at = monotonic()
        self.refresh_count += 1
        return self.snapshot()

    def snapshot(self) -> dict[str, Any]:
        return deepcopy(self.values)

    def status(self) -> dict[str, Any]:
        return {
            "loaded": bool(self.values),
            "refresh_count": self.refresh_count,
            "keys": sorted(self.values.keys()),
        }
