"""Deterministic character-behavior utility layer.

This is the game-AI side of Mary: cheap state-based decisions about whether to
animate, make a tiny local sound, surface a represented pending thought as a
candidate, or simply stay quiet.  It never creates thoughts or facts.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import random
from typing import Any


class CharacterBehaviorAction(str, Enum):
    QUIET = "quiet"
    IDLE_ANIMATION = "idle_animation"
    IDLE_SOUND = "idle_sound"
    CHECK_IN = "check_in"
    THOUGHT_CANDIDATE = "thought_candidate"


@dataclass(frozen=True)
class CharacterBehaviorDecision:
    action: CharacterBehaviorAction
    score: float
    reason: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["action"] = self.action.value
        return result


class CharacterBehaviorEngine:
    """Small utility selector; silence remains the default valid outcome."""

    def __init__(self, seed: int | None = None) -> None:
        self.random = random.Random(seed)

    def idle_decision(
        self,
        *,
        focus_active: bool,
        pending_thoughts: list[dict[str, Any]],
        idle_action: dict[str, Any],
    ) -> CharacterBehaviorDecision:
        if focus_active:
            return CharacterBehaviorDecision(
                CharacterBehaviorAction.IDLE_ANIMATION,
                .95,
                "focus mode keeps Mary present without verbal interruption",
                {"idle": idle_action, "focus_quiet": True},
            )

        # A pending thought may become eligible for later initiative, but the
        # idle layer never speaks it automatically. Presence/initiative must
        # separately decide whether and when it is appropriate to bring up.
        grounded = [
            item for item in pending_thoughts
            if isinstance(item, dict) and not item.get("used") and str(item.get("text") or "").strip()
        ]
        if grounded:
            top = max(grounded, key=lambda item: float(item.get("importance", 0.0) or 0.0))
            importance = max(0.0, min(1.0, float(top.get("importance", 0.0) or 0.0)))
            if importance >= .82 and self.random.random() < .08:
                return CharacterBehaviorDecision(
                    CharacterBehaviorAction.THOUGHT_CANDIDATE,
                    importance,
                    "a represented pending thought is salient enough to remain available for initiative",
                    {"thought_id": top.get("id"), "context": top.get("context"), "source": top.get("source")},
                )

        kind = str(idle_action.get("kind") or "animation")
        if kind == "sound":
            return CharacterBehaviorDecision(
                CharacterBehaviorAction.IDLE_SOUND,
                .35,
                "cheap local ambience",
                {"idle": idle_action},
            )
        if kind == "phrase":
            return CharacterBehaviorDecision(
                CharacterBehaviorAction.CHECK_IN,
                .18,
                "rare grounded presence check-in",
                {"idle": idle_action},
            )
        return CharacterBehaviorDecision(
            CharacterBehaviorAction.IDLE_ANIMATION,
            .55,
            "cheap game-character idle motion",
            {"idle": idle_action},
        )
