"""Deterministic expression director shared by voice and avatar presentation.

Mary's delivery is now downstream of the same TurnMind-derived dialogue plan
used by cognition.  Emotional state still colors a restrained conversational
baseline, but text/voice/avatar no longer guess independently about how a turn
should feel.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

from mary.expression.emotion import Emotion, EmotionalState
from .delivery_plan import DeliveryPlan


class ExpressionDirector:
    """Map represented TurnMind state + speech act into bounded delivery.

    The director never infers hidden creator emotion. It uses Mary's represented
    emotional state, already-selected dialogue act/lane, literal response cues,
    and the derived dialogue plan. The dialogue plan is context-only and cannot
    create personality or identity facts.
    """

    def plan(
        self,
        *,
        input_text: str,
        response_text: str,
        emotional_state: EmotionalState | None,
        conversation_lane: str = "conversation",
        dialogue_act: str | None = None,
        mind_state: Mapping[str, Any] | None = None,
    ) -> DeliveryPlan:
        emotion = emotional_state.primary if emotional_state is not None else Emotion.NEUTRAL
        intensity = _clamp(getattr(emotional_state, "intensity", 0.0), 0.0, 1.0)
        response = str(response_text or "")
        lane = str(conversation_lane or "conversation").lower()
        act = str(dialogue_act or "").lower()

        mind = dict(mind_state) if isinstance(mind_state, Mapping) else {}
        dialogue_plan = (
            dict(mind.get("dialogue_plan", {}) or {})
            if isinstance(mind.get("dialogue_plan", {}), Mapping)
            else {}
        )

        # Natural baseline: Mary is talking to someone familiar, not auditioning
        # for a dramatic role. Personality should come mostly from what Mary says;
        # delivery adds subtle embodied color.
        profile = "conversational"
        energy = 0.38
        warmth = 0.50
        pace = 1.00
        stability = 0.54
        style = 0.025
        emphasis = 0.15
        avatar = "neutral"
        gesture = 0.18
        pause_style = "natural"
        rationale = "restrained conversational baseline"

        # First blend the TurnMind-derived acting contract. This is deliberately
        # moderate: it aligns surfaces with cognition without creating a second
        # performance persona or turning scalar personality fields into theater.
        if dialogue_plan:
            plan_energy = _clamp(dialogue_plan.get("energy", 0.5), 0.0, 1.0)
            plan_warmth = _clamp(dialogue_plan.get("warmth", 0.55), 0.0, 1.0)
            spontaneity = _clamp(dialogue_plan.get("spontaneity", 0.5), 0.0, 1.0)
            intimacy = _clamp(dialogue_plan.get("intimacy", 0.5), 0.0, 1.0)
            theatricality = _clamp(dialogue_plan.get("theatricality", 0.35), 0.0, 1.0)
            expressiveness = _clamp(dialogue_plan.get("expressiveness", 0.7), 0.0, 1.0)

            energy = _lerp(energy, 0.24 + (0.50 * plan_energy), 0.38)
            warmth = _lerp(warmth, 0.30 + (0.60 * plan_warmth), 0.40)
            stability = _lerp(stability, 0.61 - (0.14 * spontaneity), 0.32)
            style = _lerp(style, 0.012 + (0.045 * theatricality), 0.32)
            emphasis = _lerp(emphasis, 0.10 + (0.22 * expressiveness), 0.30)
            gesture = _lerp(gesture, 0.10 + (0.25 * expressiveness), 0.32)

            # Intimacy is expressed mostly as warmth and slightly calmer pacing,
            # never as unsupported relational claims.
            warmth = min(0.90, warmth + (0.07 * intimacy))

            pacing = str(dialogue_plan.get("pacing") or "").lower()
            if pacing == "lively":
                pace = _lerp(pace, 1.045, 0.45)
                gesture = min(0.42, gesture + 0.03)
            elif pacing == "soft_deliberate":
                pace = _lerp(pace, 0.945, 0.48)
                gesture = max(0.10, gesture - 0.025)
                pause_style = "thoughtful"

            tone = str(dialogue_plan.get("tone") or "").lower()
            if tone == "bright_alive":
                profile = "bright"
            elif tone == "soft_grounded":
                profile = "soft"
            elif tone == "firm_controlled":
                profile = "firm"
            elif tone == "warm_close":
                profile = "warm"
            elif tone == "light_playful":
                profile = "playful"
            elif tone == "thoughtful":
                profile = "thoughtful"

            rationale += "; TurnMind dialogue plan blended"

            # Session-only previous expression smooths abrupt delivery jumps on
            # neutral/low-intensity turns. Strong current emotion always wins.
            previous = dialogue_plan.get("previous_expression", {})
            if isinstance(previous, Mapping) and previous and intensity < 0.50:
                previous_energy = previous.get("energy")
                previous_warmth = previous.get("warmth")
                previous_pace = previous.get("pace")
                if previous_energy is not None:
                    energy = _lerp(energy, _clamp(previous_energy, 0.0, 1.0), 0.10)
                if previous_warmth is not None:
                    warmth = _lerp(warmth, _clamp(previous_warmth, 0.0, 1.0), 0.10)
                try:
                    previous_pace_number = float(previous_pace)
                except (TypeError, ValueError):
                    previous_pace_number = None
                if previous_pace_number is not None:
                    pace = _lerp(pace, previous_pace_number, 0.08)
                rationale += "; session expression continuity"

        # Ordinary conversation gets deliberately low emotional gain. Strong
        # states can still become visibly expressive, but they blend into the
        # baseline instead of replacing it wholesale.
        influence = 0.08 + (0.24 * intensity)
        if lane == "thinking":
            influence = min(0.28, influence + 0.04)
            pace = _lerp(pace, 0.96, 0.45)
            gesture = _lerp(gesture, 0.14, 0.45)
            pause_style = "thoughtful"

        target = _emotion_target(emotion)
        if target is not None:
            (
                target_profile,
                target_energy,
                target_warmth,
                target_pace,
                target_stability,
                target_style,
                target_emphasis,
                target_avatar,
                target_gesture,
            ) = target
            if intensity >= 0.58:
                profile = target_profile
            energy = _lerp(energy, target_energy, influence)
            warmth = _lerp(warmth, target_warmth, influence)
            pace = _lerp(pace, target_pace, influence)
            stability = _lerp(stability, target_stability, influence)
            style = _lerp(style, target_style, influence)
            emphasis = _lerp(emphasis, target_emphasis, influence)
            gesture = _lerp(gesture, target_gesture, influence)
            if intensity >= 0.42:
                avatar = target_avatar
            if emotion in {
                Emotion.CONCERN,
                Emotion.SADNESS,
                Emotion.DISAPPOINTMENT,
                Emotion.LONELINESS,
            } and intensity >= 0.65:
                warmth = max(warmth, 0.72)
            rationale += f"; {emotion.value} blended at {influence:.2f} gain"

        # Short social turns should be easier, not more performed.
        if lane == "social_instant" or act in {"greet", "react", "laugh", "thanks_response"}:
            if emotion not in {Emotion.CONCERN, Emotion.SADNESS, Emotion.ANGER}:
                profile = "playful"
            energy = min(0.58, energy + 0.05)
            pace = min(1.04, max(pace, 1.00))
            emphasis = min(0.28, emphasis + 0.03)
            gesture = min(0.30, gesture + 0.04)
            rationale += "; restrained social beat"

        if re.search(r"(?:😂|😭|\blol\b|\blmao\b|\bhaha+\b|\bhehe+\b)", response, flags=re.I):
            profile = "amused"
            energy = max(energy, 0.56)
            stability = min(stability, 0.48)
            style = max(style, 0.04)
            emphasis = max(emphasis, 0.22)
            avatar = "happy"
            gesture = max(gesture, 0.26)
            rationale += "; explicit amusement"

        if "!" in response:
            energy = min(0.72, energy + 0.02)
            emphasis = min(0.38, emphasis + 0.02)

        return DeliveryPlan(
            profile=profile,
            energy=_clamp(energy, 0.0, 1.0),
            warmth=_clamp(warmth, 0.0, 1.0),
            pace=_clamp(pace, 0.88, 1.10),
            stability=_clamp(stability, 0.40, 0.68),
            style=_clamp(style, 0.0, 0.09),
            emphasis=_clamp(emphasis, 0.0, 0.45),
            pause_style=pause_style,
            avatar_expression=avatar,
            gesture_energy=_clamp(gesture, 0.0, 0.45),
            rationale=rationale,
            metadata={
                "emotion": emotion.value,
                "emotion_intensity": intensity,
                "emotion_gain": round(influence, 3),
                "lane": lane,
                "dialogue_act": act or None,
                "performance_mode": "natural_conversation",
                "restraint": 0.82,
                "turn_mind_dialogue_plan": bool(dialogue_plan),
                "dialogue_stance": dialogue_plan.get("stance") if dialogue_plan else None,
                "dialogue_tone": dialogue_plan.get("tone") if dialogue_plan else None,
                "dialogue_drive": dialogue_plan.get("drive") if dialogue_plan else None,
            },
        )


def _emotion_target(emotion: Emotion) -> tuple[str, float, float, float, float, float, float, str, float] | None:
    if emotion in {Emotion.JOY, Emotion.EXCITEMENT, Emotion.SURPRISE, Emotion.PRIDE}:
        return ("bright", 0.72, 0.66, 1.04, 0.47, 0.065, 0.36, "happy", 0.40)
    if emotion in {Emotion.WARMTH, Emotion.AFFECTION, Emotion.LOVE, Emotion.APPRECIATION, Emotion.GRATITUDE}:
        return ("warm", 0.48, 0.80, 0.98, 0.55, 0.035, 0.24, "happy", 0.26)
    if emotion in {Emotion.CONCERN, Emotion.SADNESS, Emotion.DISAPPOINTMENT, Emotion.LONELINESS}:
        return ("soft", 0.28, 0.72, 0.94, 0.58, 0.025, 0.18, "sad", 0.16)
    if emotion in {Emotion.FRUSTRATION, Emotion.ANGER}:
        return ("firm", 0.60, 0.34, 1.00, 0.57, 0.045, 0.34, "angry", 0.34)
    if emotion in {Emotion.CURIOSITY, Emotion.CONFUSION}:
        return ("thoughtful", 0.39, 0.55, 0.97, 0.55, 0.03, 0.20, "neutral", 0.20)
    return None


def _lerp(start: float, end: float, amount: float) -> float:
    return float(start) + ((float(end) - float(start)) * _clamp(amount, 0.0, 1.0))


def _clamp(value: Any, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = minimum
    return max(minimum, min(maximum, number))
