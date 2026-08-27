"""TurnMind -> dialogue projection for MaryV2.

This module is intentionally deterministic.  It does not generate language and
it does not own personality, emotion, relationship, or dialogue state.  It
projects the already-authoritative per-turn TurnMind snapshot into one bounded
contract describing how Mary's thought should become spoken dialogue.

The same plan is consumed by cognition/reflection and by the final expression
layer so text, voice and avatar are all looking at the same turn-level intent.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from mary.expression.response import ResponseType


def _clamp(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = float(default)
    return max(0.0, min(1.0, number))


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _clip(value: Any, limit: int = 220) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


@dataclass(frozen=True)
class DialoguePlan:
    """Bounded turn-level contract for Mary's spoken response."""

    mode: str
    drive: str
    stance: str
    tone: str
    relationship_mode: str
    emotional_color: str
    preferred_length: str
    opening_style: str
    ending_style: str
    pacing: str
    warmth: float
    playfulness: float
    directness: float
    independence: float
    expressiveness: float
    energy: float
    spontaneity: float
    intimacy: float
    theatricality: float
    allow_question: bool
    question_budget: int
    allow_opinion: bool
    allow_teasing: bool
    allow_fragments: bool
    allow_interjections: bool
    allow_thinking_aloud: bool
    initiative: dict[str, Any] = field(default_factory=dict)
    previous_expression: dict[str, Any] = field(default_factory=dict)
    directives: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "drive": self.drive,
            "stance": self.stance,
            "tone": self.tone,
            "relationship_mode": self.relationship_mode,
            "emotional_color": self.emotional_color,
            "preferred_length": self.preferred_length,
            "opening_style": self.opening_style,
            "ending_style": self.ending_style,
            "pacing": self.pacing,
            "warmth": round(self.warmth, 3),
            "playfulness": round(self.playfulness, 3),
            "directness": round(self.directness, 3),
            "independence": round(self.independence, 3),
            "expressiveness": round(self.expressiveness, 3),
            "energy": round(self.energy, 3),
            "spontaneity": round(self.spontaneity, 3),
            "intimacy": round(self.intimacy, 3),
            "theatricality": round(self.theatricality, 3),
            "allow_question": self.allow_question,
            "question_budget": int(self.question_budget),
            "allow_opinion": self.allow_opinion,
            "allow_teasing": self.allow_teasing,
            "allow_fragments": self.allow_fragments,
            "allow_interjections": self.allow_interjections,
            "allow_thinking_aloud": self.allow_thinking_aloud,
            "initiative": dict(self.initiative),
            "previous_expression": dict(self.previous_expression),
            "directives": list(self.directives),
            "authority": "derived_from_turn_mind",
            "persistence": "dialogue_context_only",
        }

    def prompt_view(self) -> dict[str, Any]:
        """Smaller form intended for generation/reflection prompts."""
        return {
            key: value
            for key, value in self.to_dict().items()
            if key not in {"previous_expression", "persistence"}
        }


class DialoguePlanner:
    """Translate TurnMind's existing state into one coherent dialogue plan."""

    _STANCE_BY_DRIVE = {
        "react": "responsive",
        "answer": "grounded_answer",
        "opine": "clear_personal_view",
        "disagree": "respectful_pushback",
        "reflect": "reflective",
        "ask": "genuine_curiosity",
        "tease": "playful_pushback",
        "think_aloud": "exploratory",
        "recall": "grounded_callback",
        "acknowledge": "warm_acknowledgment",
    }

    def plan(
        self,
        mind_state: Mapping[str, Any] | None,
        *,
        input_text: str = "",
    ) -> DialoguePlan:
        mind = _mapping(mind_state)
        disposition = _mapping(mind.get("disposition"))
        performance = _mapping(mind.get("performance"))
        continuity = _mapping(mind.get("continuity"))
        relationship = _mapping(mind.get("relationship"))
        emotion = _mapping(mind.get("emotion"))
        conversation = _mapping(mind.get("conversation"))
        engagement = _mapping(mind.get("conversation_engagement"))
        initiative = _mapping(mind.get("conversation_initiative"))

        drive = str(continuity.get("drive") or "react").strip().lower()
        mode = str(disposition.get("mode") or "conversation")
        emotional_color = str(
            emotion.get("turn_primary")
            or emotion.get("primary")
            or performance.get("emotional_color")
            or "neutral"
        ).strip().lower()

        familiarity = str(disposition.get("familiarity") or relationship.get("familiarity") or "developing")
        relationship_mode = {
            "new": "light_familiarity",
            "developing": "growing_familiarity",
            "familiar": "established_familiarity",
        }.get(familiarity.lower(), familiarity.lower() or "growing_familiarity")

        warmth = _clamp(disposition.get("warmth"), 0.7)
        playfulness = _clamp(disposition.get("playfulness"), 0.6)
        directness = _clamp(disposition.get("directness"), 0.7)
        independence = _clamp(disposition.get("independence"), 0.6)
        expressiveness = _clamp(disposition.get("expressiveness"), 0.7)
        energy = _clamp(performance.get("energy"), 0.5)
        spontaneity = _clamp(performance.get("spontaneity"), 0.5)
        intimacy = _clamp(performance.get("intimacy"), warmth)
        theatricality = _clamp(performance.get("theatricality"), 0.35)

        allow_question = bool(
            engagement.get(
                "allow_follow_up_question",
                continuity.get("allow_follow_up_question", True),
            )
        )
        raw_budget = engagement.get("question_budget")
        try:
            question_budget = max(0, min(1, int(raw_budget))) if raw_budget is not None else (1 if allow_question else 0)
        except (TypeError, ValueError):
            question_budget = 1 if allow_question else 0
        if not allow_question:
            question_budget = 0

        stance = self._STANCE_BY_DRIVE.get(drive, "responsive")
        tone = self._tone(
            emotional_color=emotional_color,
            playfulness=playfulness,
            warmth=warmth,
            drive=drive,
        )

        previous_expression = _mapping(conversation.get("last_mary_expression"))
        previous_view = {
            key: previous_expression.get(key)
            for key in (
                "tone",
                "stance",
                "drive",
                "delivery_profile",
                "energy",
                "warmth",
                "pace",
            )
            if previous_expression.get(key) not in (None, "", [], {})
        }

        initiative_view: dict[str, Any] = {}
        if initiative:
            initiative_view = {
                "permission": initiative.get("permission"),
                "grounded_gap": _mapping(initiative.get("grounded_gap")),
                "agency_orientation": _mapping(initiative.get("agency_orientation")),
                "guidance": _clip(initiative.get("guidance"), 260),
            }
            initiative_view = {
                key: value
                for key, value in initiative_view.items()
                if value not in (None, "", [], {})
            }

        preferred_length = str(disposition.get("preferred_length") or "medium")
        opening_style = str(performance.get("opening_style") or "natural_entry")
        ending_style = str(performance.get("ending_style") or "natural_landing")
        pacing = str(performance.get("pacing") or "natural_conversational")

        directives = [
            "Carry Mary's actual viewpoint through the line; do not flatten it into neutral assistant prose.",
            "React to Unbe's current words before advice, explanation, or task framing.",
            "Let relationship familiarity affect ease and openness without inventing intimacy or history.",
            "Let emotion color wording and cadence rather than naming the emotion unless the topic calls for it.",
            "Keep cognition and expression aligned: the spoken line should preserve the reasoning stance, not replace it with a generic polite summary.",
            "Use the previous expression only for continuity; do not mechanically repeat its opening, imagery, slang, or delivery profile.",
        ]
        if ending_style == "clean_statement" or not allow_question:
            directives.append("Let the response land as a statement; do not append a reflexive follow-up question.")
        if initiative_view:
            directives.append("One grounded initiative beat is allowed when it genuinely advances this thread; do not hijack the user's topic.")
        if preferred_length == "micro":
            directives.append("Keep this to one compact spoken beat, normally one or two sentences.")
        if mode == "task_collaboration":
            directives.append("Stay recognizably Mary while prioritizing precision and usefulness over decorative character performance.")

        return DialoguePlan(
            mode=mode,
            drive=drive,
            stance=stance,
            tone=tone,
            relationship_mode=relationship_mode,
            emotional_color=emotional_color,
            preferred_length=preferred_length,
            opening_style=opening_style,
            ending_style=ending_style,
            pacing=pacing,
            warmth=warmth,
            playfulness=playfulness,
            directness=directness,
            independence=independence,
            expressiveness=expressiveness,
            energy=energy,
            spontaneity=spontaneity,
            intimacy=intimacy,
            theatricality=theatricality,
            allow_question=allow_question,
            question_budget=question_budget,
            allow_opinion=bool(disposition.get("allow_opinion", True)),
            allow_teasing=bool(disposition.get("allow_teasing", False)),
            allow_fragments=bool(performance.get("allow_fragments", True)),
            allow_interjections=bool(performance.get("allow_interjections", True)),
            allow_thinking_aloud=bool(performance.get("allow_thinking_aloud", True)),
            initiative=initiative_view,
            previous_expression=previous_view,
            directives=tuple(directives),
        )

    @staticmethod
    def response_type(text: str, plan: Mapping[str, Any] | None) -> ResponseType:
        """Classify the structured dialogue response without another model call."""
        data = _mapping(plan)
        drive = str(data.get("drive") or "").lower()
        mode = str(data.get("mode") or "").lower()
        content = str(text or "").strip()

        if not content:
            return ResponseType.SILENCE
        if drive == "ask" or (content.endswith("?") and content.count("?") == 1):
            return ResponseType.QUESTION
        if drive == "reflect":
            return ResponseType.REFLECTION
        if mode == "task_collaboration" and len(content.split()) >= 28:
            return ResponseType.EXPLANATION
        return ResponseType.STATEMENT

    @staticmethod
    def expression_trace(
        plan: Mapping[str, Any] | None,
        delivery: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        """Tiny session-only trace that can feed the next TurnMind turn."""
        data = _mapping(plan)
        delivered = _mapping(delivery)
        return {
            "drive": data.get("drive"),
            "stance": data.get("stance"),
            "tone": data.get("tone"),
            "emotional_color": data.get("emotional_color"),
            "preferred_length": data.get("preferred_length"),
            "ending_style": data.get("ending_style"),
            "delivery_profile": delivered.get("profile"),
            "energy": delivered.get("energy"),
            "warmth": delivered.get("warmth"),
            "pace": delivered.get("pace"),
            "authority": "session_expression_trace",
        }

    @staticmethod
    def _tone(*, emotional_color: str, playfulness: float, warmth: float, drive: str) -> str:
        if emotional_color in {"concern", "sadness", "loneliness", "disappointment"}:
            return "soft_grounded"
        if emotional_color in {"frustration", "anger"}:
            return "firm_controlled"
        if emotional_color in {"joy", "excitement", "surprise", "pride"}:
            return "bright_alive"
        if emotional_color in {"warmth", "affection", "love", "appreciation", "gratitude"}:
            return "warm_close"
        if drive == "tease" or playfulness >= 0.78:
            return "light_playful"
        if drive in {"reflect", "think_aloud"}:
            return "thoughtful"
        if warmth >= 0.72:
            return "warm_direct"
        return "natural_direct"
