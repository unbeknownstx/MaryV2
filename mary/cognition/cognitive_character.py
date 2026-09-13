"""Coordinate cognition and expression for one Mary turn.

This module does not own identity, memory, relationship state, tools, or model
authorization. It converts authoritative turn state into a compact plan for how
much cognition a turn deserves and how that cognition should be expressed.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any


def _safe_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


@dataclass(frozen=True)
class CognitiveCharacterPlan:
    cognitive_mode: str
    reasoning_depth: str
    latency_priority: str
    knowledge_breadth: str
    explanation_style: str
    preferred_length: str
    technical_register: str
    conversational_register: str
    local_preference: float
    escalation_allowed: bool
    embodiment_intents: tuple[str, ...]
    continuity_intents: tuple[str, ...]
    instructions: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "cognitive_mode": self.cognitive_mode,
            "reasoning_depth": self.reasoning_depth,
            "latency_priority": self.latency_priority,
            "knowledge_breadth": self.knowledge_breadth,
            "explanation_style": self.explanation_style,
            "preferred_length": self.preferred_length,
            "technical_register": self.technical_register,
            "conversational_register": self.conversational_register,
            "local_preference": self.local_preference,
            "escalation_allowed": self.escalation_allowed,
            "embodiment_intents": list(self.embodiment_intents),
            "continuity_intents": list(self.continuity_intents),
            "instructions": list(self.instructions),
        }


class CognitiveCharacterRuntime:
    """Produce provider-independent cognition and expression policy.

    The runtime can consume either explicit turn fields or Mary's existing
    ``TurnMindState``/prompt-view mapping. Provider choice remains downstream
    in the router and resource governor; this module only expresses cognitive
    need and presentation intent.
    """

    _DEEP = re.compile(
        r"\b(?:analy[sz]e|architecture|debug|design|plan|compare|strategy|research|"
        r"review|audit|implement|build|develop|rewrite|chapter|story|system)\b",
        re.IGNORECASE,
    )
    _QUICK = re.compile(
        r"\b(?:what(?:'s| is)|who(?:'s| is)|when|where|how much|convert|calculate|"
        r"recipe|definition|meaning)\b",
        re.IGNORECASE,
    )
    _RELATIONAL = re.compile(
        r"\b(?:i feel|i think|mary|remember|yesterday|talk|what do you think|"
        r"your take|together)\b",
        re.IGNORECASE,
    )

    def plan_from_turn_state(self, turn_state: Any) -> CognitiveCharacterPlan:
        """Build from Mary's canonical per-turn state without taking ownership.

        ``TurnMindState`` is preferred, but a plain mapping remains supported
        for diagnostics/tests and future remote surfaces.
        """

        if isinstance(turn_state, dict):
            state = dict(turn_state)
        else:
            prompt_view = getattr(turn_state, "prompt_view", None)
            if callable(prompt_view):
                state = _safe_dict(prompt_view())
            else:
                to_dict = getattr(turn_state, "to_dict", None)
                state = _safe_dict(to_dict()) if callable(to_dict) else {}

        input_text = str(
            getattr(turn_state, "input_text", None)
            or state.get("input_text")
            or ""
        )
        return self.plan(
            input_text=input_text,
            relationship=_safe_dict(state.get("relationship")),
            disposition=_safe_dict(state.get("disposition")),
            performance=_safe_dict(state.get("performance")),
            emotion=_safe_dict(state.get("emotion")),
            continuity=_safe_dict(state.get("continuity")),
        )

    def plan(
        self,
        *,
        input_text: str,
        relationship: dict[str, Any],
        disposition: dict[str, Any],
        performance: dict[str, Any],
        emotion: dict[str, Any],
        continuity: dict[str, Any],
    ) -> CognitiveCharacterPlan:
        text = " ".join(str(input_text or "").split())
        words = max(1, len(text.split()))

        # TurnMind exposes provenance-filtered creator state as current_profile.
        # user_profile is retained as an adapter alias for remote/older callers.
        user_profile = _safe_dict(relationship.get("current_profile"))
        if not user_profile:
            user_profile = _safe_dict(relationship.get("user_profile"))
        communication = _safe_dict(user_profile.get("communication_style"))
        preferred_length = str(communication.get("preferred_length") or disposition.get("preferred_length") or "natural")
        explanation_style = str(communication.get("explanation_style") or "adaptive")
        technical_register = str(communication.get("technical_register") or "adaptive")
        conversational_register = str(communication.get("conversational_register") or "familiar_natural")

        if self._DEEP.search(text) or words >= 45:
            cognitive_mode = "deliberate"
            reasoning_depth = "deep"
            knowledge_breadth = "broad"
            latency_priority = "quality_first"
            local_preference = 0.42
        elif self._QUICK.search(text) and words <= 24:
            cognitive_mode = "direct"
            reasoning_depth = "light"
            knowledge_breadth = "targeted"
            latency_priority = "fast"
            local_preference = 0.76
        elif self._RELATIONAL.search(text):
            cognitive_mode = "relational"
            reasoning_depth = "moderate"
            knowledge_breadth = "contextual"
            latency_priority = "responsive"
            local_preference = 0.82
        else:
            cognitive_mode = "balanced"
            reasoning_depth = "moderate"
            knowledge_breadth = "targeted"
            latency_priority = "responsive"
            local_preference = 0.68

        emotional_color = str(performance.get("emotional_color") or emotion.get("turn_primary") or "neutral").lower()
        pacing = str(performance.get("pacing", "natural_conversational"))
        embodiment = ["attend_to_user"]
        if emotional_color in {"joy", "excitement", "surprise", "pride"}:
            embodiment += ["brighten_expression", "increase_gesture_energy"]
        elif emotional_color in {"concern", "sadness", "warmth", "affection", "gratitude"}:
            embodiment += ["soften_expression", "reduce_gesture_energy"]
        elif emotional_color in {"frustration", "anger"}:
            embodiment += ["firm_expression", "controlled_emphasis"]
        if pacing == "soft_deliberate":
            embodiment.append("slower_delivery")
        elif pacing == "lively":
            embodiment.append("lively_delivery")
        if cognitive_mode == "deliberate":
            embodiment.append("brief_thinking_beat")

        continuity_intents: list[str] = []
        if str(continuity.get("drive", "")) == "recall":
            continuity_intents.append("acknowledge_shared_history")
        if self._RELATIONAL.search(text):
            continuity_intents.append("preserve_conversational_thread")

        return CognitiveCharacterPlan(
            cognitive_mode=cognitive_mode,
            reasoning_depth=reasoning_depth,
            latency_priority=latency_priority,
            knowledge_breadth=knowledge_breadth,
            explanation_style=explanation_style[:64],
            preferred_length=preferred_length[:32],
            technical_register=technical_register[:64],
            conversational_register=conversational_register[:64],
            local_preference=local_preference,
            escalation_allowed=True,
            embodiment_intents=tuple(dict.fromkeys(embodiment)),
            continuity_intents=tuple(dict.fromkeys(continuity_intents)),
            instructions=(
                "Use as much reasoning as the task needs without making every reply sound like a lecture.",
                "Keep Mary as the speaker even when external or local models provide computation.",
                "Adapt explanation to represented communication preferences.",
                "Prefer the smallest sufficient cognitive resource and escalate for genuinely harder work.",
                "Do not expose internal routing or model identity unless runtime details are requested.",
                "Embodiment intents guide presentation only and do not claim that a physical action occurred.",
            ),
        )
