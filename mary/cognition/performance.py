"""MaryV2 conversational performance planning.

The performance director does not invent facts or create a second personality.
It translates Mary's already-connected turn state into *how* the current line
should be performed: energy, pacing, spontaneity, emphasis, and conversational
texture. Reasoning still owns what Mary thinks; this layer helps that thought
sound like character dialogue instead of polished assistant prose.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


@dataclass(frozen=True)
class PerformancePlan:
    """Provider-independent acting direction for one Mary turn."""

    mode: str
    energy: float
    spontaneity: float
    theatricality: float
    intimacy: float
    pacing: str
    emotional_color: str
    opening_style: str
    ending_style: str
    allow_fragments: bool = True
    allow_interjections: bool = True
    allow_thinking_aloud: bool = True
    avoid_polished_assistant_cadence: bool = True
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "energy": self.energy,
            "spontaneity": self.spontaneity,
            "theatricality": self.theatricality,
            "intimacy": self.intimacy,
            "pacing": self.pacing,
            "emotional_color": self.emotional_color,
            "opening_style": self.opening_style,
            "ending_style": self.ending_style,
            "allow_fragments": self.allow_fragments,
            "allow_interjections": self.allow_interjections,
            "allow_thinking_aloud": self.allow_thinking_aloud,
            "avoid_polished_assistant_cadence": self.avoid_polished_assistant_cadence,
            "notes": list(self.notes),
        }


class PerformanceDirector:
    """Resolve acting direction from Mary's current turn state."""

    def plan(
        self,
        *,
        disposition: dict[str, Any],
        emotion: dict[str, Any],
        continuity: dict[str, Any],
    ) -> PerformancePlan:
        drive = str(continuity.get("drive", "react")).lower()
        emotion_name = str(emotion.get("turn_primary", emotion.get("primary", "neutral"))).lower()
        intensity = _clamp(emotion.get("turn_intensity", emotion.get("intensity", 0.0)) or 0.0)

        expressiveness = _clamp(disposition.get("expressiveness", 0.8))
        playfulness = _clamp(disposition.get("playfulness", 0.7))
        warmth = _clamp(disposition.get("warmth", 0.8))
        familiarity = str(disposition.get("familiarity", "developing"))
        mode = str(disposition.get("mode", "conversation"))

        energy = 0.46 + (0.26 * intensity) + (0.10 * expressiveness)
        spontaneity = 0.42 + (0.20 * playfulness)
        theatricality = 0.34 + (0.26 * expressiveness)
        intimacy = 0.45 + (0.25 * warmth)

        if familiarity == "familiar":
            intimacy += 0.12
        elif familiarity == "new":
            intimacy -= 0.08

        if drive in {"react", "tease"}:
            energy += 0.10
            spontaneity += 0.12
        elif drive in {"opine", "disagree"}:
            energy += 0.05
            theatricality += 0.08
        elif drive == "recall":
            spontaneity -= 0.08
            theatricality -= 0.05
        elif drive == "ask":
            spontaneity += 0.05

        if emotion_name in {"joy", "excitement", "surprise", "pride"}:
            energy += 0.12
            spontaneity += 0.06
        elif emotion_name in {"warmth", "appreciation", "affection", "gratitude", "love"}:
            energy -= 0.03
            intimacy += 0.15
            spontaneity += 0.03
        elif emotion_name in {"concern", "sadness", "loneliness", "disappointment"}:
            energy -= 0.10
            intimacy += 0.10
        elif emotion_name in {"frustration", "anger"}:
            energy += 0.07
            theatricality += 0.05

        energy = _clamp(energy)
        spontaneity = _clamp(spontaneity)
        theatricality = _clamp(theatricality)
        intimacy = _clamp(intimacy)

        if energy >= 0.72:
            pacing = "lively"
        elif energy <= 0.40:
            pacing = "soft_deliberate"
        else:
            pacing = "natural_conversational"

        opening_style = {
            "react": "immediate_reaction",
            "opine": "thought_then_position",
            "disagree": "clear_pushback",
            "recall": "direct_callback",
            "ask": "genuine_curiosity",
            "reflect": "brief_thoughtful_beat",
        }.get(drive, "natural_entry")

        ending_style = (
            "clean_statement"
            if not bool(continuity.get("allow_follow_up_question", True))
            else "natural_landing"
        )

        notes = (
            "Write spoken character dialogue, not an essay or support response.",
            "Let sentence length vary; short fragments and beats are welcome when natural.",
            "Use contractions and conversational punctuation. Do not narrate stage directions.",
            "Embodiment beats explanation: sound amused, skeptical, proud, curious, or concerned instead of naming the emotion.",
            "Do not force perfect grammar when a natural spoken fragment is stronger.",
            "Do not add a question merely to keep the conversation going.",
            "Prefer one memorable Mary-specific reaction over polished generic helpfulness.",
        )

        return PerformancePlan(
            mode=mode,
            energy=round(energy, 3),
            spontaneity=round(spontaneity, 3),
            theatricality=round(theatricality, 3),
            intimacy=round(intimacy, 3),
            pacing=pacing,
            emotional_color=emotion_name,
            opening_style=opening_style,
            ending_style=ending_style,
            notes=notes,
        )
