"""Deterministic performer director shared by voice and avatar presentation.

Mary's words, voice and body must feel like one character.  The director is the
presentation bridge between canonical TurnMind state and the current surface:
it does not invent personality, infer hidden creator emotion, or decide what
Mary believes.  It translates the stance already selected by TurnMind into a
bounded performance score that voice/VRM/Live2D clients can render.

Stage 12 keeps a restrained fallback for generic/unknown context, but when Mary
has an explicit active character pattern (banter, affection, excitement,
disagreement, embarrassment, etc.) the performance becomes visibly legible
instead of flattening every turn into the same neutral delivery.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

from mary.expression.emotion import Emotion, EmotionalState
from .delivery_plan import DeliveryPlan


class ExpressionDirector:
    """Map represented TurnMind state + speech act into bounded performance."""

    def plan(
        self,
        *,
        input_text: str,
        response_text: str,
        emotional_state: EmotionalState | None,
        conversation_lane: str = "conversation",
        dialogue_act: str | None = None,
        mind_state: Mapping[str, Any] | None = None,
        social_context: str = "private",
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
        character_expression = (
            dict(mind.get("character_expression", {}) or {})
            if isinstance(mind.get("character_expression", {}), Mapping)
            else {}
        )
        patterns = _active_pattern_names(character_expression)
        stage_context = str(social_context or "private").strip().lower()
        if stage_context not in {"private", "casual", "focus", "stream", "performance"}:
            stage_context = "private"

        # Safe fallback for surfaces/tests that have no TurnMind character
        # contract.  This preserves the old natural-conversation calibration.
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
        gesture_style = "natural"
        gaze_style = "engaged"
        head_style = "natural"
        reaction_style = "none"
        performance_mode = "natural_conversation"
        restraint = 0.82
        rationale = "restrained conversational fallback"

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
            tone_profile = {
                "bright_alive": "bright",
                "bright_animated": "bright",
                "soft_grounded": "soft",
                "quiet_grounded": "soft",
                "firm_controlled": "firm",
                "firm_grounded": "firm",
                "clear_serious": "firm",
                "controlled_edge": "firm",
                "warm_close": "warm",
                "light_playful": "playful",
                "thoughtful": "thoughtful",
                "thoughtful_direct": "thoughtful",
            }.get(tone)
            if tone_profile:
                profile = tone_profile

            rationale += "; TurnMind dialogue plan blended"

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

        # The Stage 12 performer layer.  These rules do not decide content;
        # they make already-selected Mary behavior perceivable in voice/body.
        if patterns:
            performance_mode = "embodied_character"
            restraint = 0.56
            (
                profile,
                energy,
                warmth,
                pace,
                stability,
                style,
                emphasis,
                avatar,
                gesture,
                pause_style,
                gesture_style,
                gaze_style,
                head_style,
                reaction_style,
                restraint,
                performer_reason,
            ) = _apply_character_performance(
                patterns=patterns,
                profile=profile,
                energy=energy,
                warmth=warmth,
                pace=pace,
                stability=stability,
                style=style,
                emphasis=emphasis,
                avatar=avatar,
                gesture=gesture,
                pause_style=pause_style,
                gesture_style=gesture_style,
                gaze_style=gaze_style,
                head_style=head_style,
                reaction_style=reaction_style,
                restraint=restraint,
            )
            rationale += f"; {performer_reason}"

        # Represented emotion colors the performance after character selection.
        # Serious states deliberately override playful presentation.
        influence = 0.08 + (0.24 * intensity)
        if patterns:
            influence = min(0.40, 0.12 + (0.28 * intensity))
        if lane == "thinking":
            influence = min(0.32, influence + 0.04)
            pace = _lerp(pace, 0.96, 0.45)
            gesture = _lerp(gesture, 0.14, 0.45)
            pause_style = "thoughtful"
            if "playful_banter" not in patterns:
                head_style = "thoughtful"

        # Social context changes projection, not identity. Stream/performance
        # modes project the same Mary more clearly; focus mode quiets the stage.
        # Serious character patterns still win below, so "stream mode" never
        # turns grief or a moral boundary into forced entertainment.
        if stage_context == "focus":
            energy *= 0.82
            gesture *= 0.64
            style *= 0.72
            emphasis *= 0.82
            restraint = max(restraint, 0.82)
            rationale += "; focus context quiets performance"
        elif stage_context == "casual":
            energy = min(1.0, energy * 1.04)
            gesture = min(1.0, gesture * 1.05)
            rationale += "; casual context adds ease"
        elif stage_context in {"stream", "performance"}:
            energy = min(1.0, energy * (1.10 if stage_context == "stream" else 1.12))
            gesture = min(1.0, gesture * 1.18)
            emphasis = min(1.0, emphasis * 1.10)
            style = min(1.0, style * 1.10)
            restraint = min(restraint, 0.58)
            rationale += f"; {stage_context} context increases readable projection"

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
                gesture_style = "soft"
                gaze_style = "soft"
                head_style = "quiet"
            if emotion in {Emotion.ANGER, Emotion.FRUSTRATION} and intensity >= 0.58:
                gesture_style = "firm"
                gaze_style = "direct"
                head_style = "still"
            rationale += f"; {emotion.value} blended at {influence:.2f} gain"

        # Short social turns should feel immediate.  With a real Mary character
        # contract they may be visibly playful; without one retain old restraint.
        if lane == "social_instant" or act in {"greet", "react", "laugh", "thanks_response"}:
            if emotion not in {Emotion.CONCERN, Emotion.SADNESS, Emotion.ANGER}:
                profile = "playful"
            if patterns:
                energy = min(0.72, energy + 0.08)
                pace = min(1.075, max(pace, 1.01))
                emphasis = min(0.40, emphasis + 0.05)
                gesture = min(0.50, gesture + 0.06)
                if gesture_style == "natural":
                    gesture_style = "quick"
                restraint = min(restraint, 0.52)
                rationale += "; embodied social beat"
            else:
                energy = min(0.58, energy + 0.05)
                pace = min(1.04, max(pace, 1.00))
                emphasis = min(0.28, emphasis + 0.03)
                gesture = min(0.30, gesture + 0.04)
                rationale += "; restrained social beat"

        if re.search(r"(?:😂|😭|\blol\b|\blmao\b|\bhaha+\b|\bhehe+\b)", response, flags=re.I):
            profile = "amused"
            energy = max(energy, 0.56 if not patterns else 0.64)
            stability = min(stability, 0.48)
            style = max(style, 0.04 if not patterns else 0.065)
            emphasis = max(emphasis, 0.22 if not patterns else 0.30)
            avatar = "happy"
            gesture = max(gesture, 0.26 if not patterns else 0.38)
            gesture_style = "amused"
            head_style = "amused"
            reaction_style = "laugh"
            rationale += "; explicit amusement"

        if "!" in response:
            energy = min(0.78 if patterns else 0.72, energy + 0.02)
            emphasis = min(0.48 if patterns else 0.38, emphasis + 0.02)

        # Serious character contexts suppress a lively carry-over even if the
        # previous turn was playful.
        if any(name in patterns for name in {"moral_boundary", "grief_or_hurt", "anger"}):
            restraint = max(restraint, 0.66)
            if "grief_or_hurt" in patterns:
                avatar = "sad"
                gesture_style = "soft"
                gaze_style = "soft"
                head_style = "quiet"
            elif "moral_boundary" in patterns or "anger" in patterns:
                gesture_style = "firm"
                gaze_style = "direct"
                head_style = "still"

        final_profile = profile
        final_energy = _clamp(energy, 0.0, 1.0)
        final_warmth = _clamp(warmth, 0.0, 1.0)
        final_pace = _clamp(pace, 0.88, 1.10)
        final_stability = _clamp(stability, 0.34 if patterns else 0.40, 0.68)
        final_style = _clamp(style, 0.0, 0.16 if patterns else 0.09)
        final_emphasis = _clamp(emphasis, 0.0, 0.55 if patterns else 0.45)
        final_gesture = _clamp(gesture, 0.0, 0.56 if patterns else 0.45)

        beats = _performance_beats(
            response,
            profile=final_profile,
            avatar=avatar,
            gesture_style=gesture_style,
            gaze_style=gaze_style,
            head_style=head_style,
            energy=final_energy,
            warmth=final_warmth,
            patterns=patterns,
        )

        return DeliveryPlan(
            profile=final_profile,
            energy=final_energy,
            warmth=final_warmth,
            pace=final_pace,
            stability=final_stability,
            style=final_style,
            emphasis=final_emphasis,
            pause_style=pause_style,
            avatar_expression=avatar,
            gesture_energy=final_gesture,
            gesture_style=gesture_style,
            gaze_style=gaze_style,
            head_style=head_style,
            reaction_style=reaction_style,
            performance_beats=tuple(beats),
            interruptible=True,
            rationale=rationale,
            metadata={
                "emotion": emotion.value,
                "emotion_intensity": intensity,
                "emotion_gain": round(influence, 3),
                "lane": lane,
                "dialogue_act": act or None,
                "performance_mode": performance_mode,
                "social_context": stage_context,
                "restraint": round(restraint, 3),
                "performer_patterns": patterns,
                "turn_mind_dialogue_plan": bool(dialogue_plan),
                "dialogue_stance": dialogue_plan.get("stance") if dialogue_plan else None,
                "dialogue_tone": dialogue_plan.get("tone") if dialogue_plan else None,
                "dialogue_drive": dialogue_plan.get("drive") if dialogue_plan else None,
                "authority": "turn_mind_presentation_projection",
                "persistence": "none",
            },
        )


def _active_pattern_names(character_expression: Mapping[str, Any]) -> list[str]:
    names: list[str] = []
    for item in list(character_expression.get("active_patterns", []) or []):
        if isinstance(item, Mapping):
            name = str(item.get("name") or "").strip().lower()
        else:
            name = str(item or "").strip().lower()
        if name and name not in names:
            names.append(name)
    return names[:5]


def _apply_character_performance(
    *,
    patterns: list[str],
    profile: str,
    energy: float,
    warmth: float,
    pace: float,
    stability: float,
    style: float,
    emphasis: float,
    avatar: str,
    gesture: float,
    pause_style: str,
    gesture_style: str,
    gaze_style: str,
    head_style: str,
    reaction_style: str,
    restraint: float,
) -> tuple[str, float, float, float, float, float, float, str, float, str, str, str, str, str, float, str]:
    p = set(patterns)
    reason = "active Mary character performance"

    # Highest-severity contexts first.  They intentionally stop flirt/banter
    # from bleeding into grief, moral boundaries, or pressure.
    if "grief_or_hurt" in p:
        return (
            "soft", min(energy, 0.34), max(warmth, 0.72), min(pace, 0.95),
            max(stability, 0.57), min(style, 0.04), min(emphasis, 0.22), "sad",
            min(gesture, 0.18), "thoughtful", "soft", "soft", "quiet", "quiet",
            0.84, "grief/hurt quiets the performer layer",
        )
    if "moral_boundary" in p:
        return (
            "firm", max(energy, 0.46), min(warmth, 0.48), min(pace, 1.00),
            max(stability, 0.57), min(style, 0.05), max(emphasis, 0.30), avatar,
            max(gesture, 0.28), "controlled", "firm", "direct", "still", "boundary",
            0.72, "moral boundary makes Mary controlled and direct",
        )
    if "pressure" in p and "excitement" not in p:
        return (
            "focused", max(energy, 0.45), warmth, min(pace, 1.01),
            max(stability, 0.55), min(style, 0.05), max(emphasis, 0.27), avatar,
            max(gesture, 0.24), "compressed", "focused", "direct", "still", "focus",
            0.70, "pressure compresses performance into function",
        )
    if "anger" in p:
        return (
            "firm", max(energy, 0.55), min(warmth, 0.45), pace,
            max(stability, 0.55), min(style, 0.06), max(emphasis, 0.34), "angry",
            max(gesture, 0.30), "controlled", "firm", "direct", "still", "edge",
            0.70, "anger gives Mary a controlled edge",
        )

    # Social performer modes.  These are what make Mary's authored wit,
    # affection and flirtiness visible instead of only present in prompt text.
    if "embarrassment" in p:
        return (
            "flustered", max(energy, 0.48), max(warmth, 0.68), min(pace, 1.02),
            min(stability, 0.46), max(style, 0.075), max(emphasis, 0.27), "surprised",
            max(gesture, 0.31), "quick", "flustered", "glance_away", "flustered", "fluster",
            0.44, "represented embarrassment gets a small visible crack in confidence",
        )
    if "affection" in p:
        return (
            "warm_playful", max(energy, 0.42), max(warmth, 0.82), min(pace, 0.99),
            min(stability, 0.50), max(style, 0.055), max(emphasis, 0.23), "happy",
            max(gesture, 0.27), "soft", "soft", "soft", "tilt", "soft_smile",
            0.48, "affection becomes warm, familiar and lightly playful",
        )
    if "playful_banter" in p:
        return (
            "teasing", max(energy, 0.57), max(warmth, 0.60), max(pace, 1.035),
            min(stability, 0.45), max(style, 0.085), max(emphasis, 0.30), "happy",
            max(gesture, 0.39), "quick", "tease", "direct", "tilt", "smirk",
            0.38, "playful banter gets quick timing and visible teasing",
        )
    if "excitement" in p:
        return (
            "bright", max(energy, 0.68), max(warmth, 0.66), max(pace, 1.045),
            min(stability, 0.45), max(style, 0.075), max(emphasis, 0.34), "happy",
            max(gesture, 0.45), "lively", "animated", "engaged", "animated", "spark",
            0.40, "genuine excitement raises energy and motion",
        )

    if "authority_or_control" in p or "disagreement" in p:
        return (
            "confident", max(energy, 0.45), warmth, pace,
            max(stability, 0.53), min(max(style, 0.035), 0.07), max(emphasis, 0.27), avatar,
            max(gesture, 0.27), "measured", "firm", "direct", "steady", "position",
            0.58, "owned position reads as confident rather than neutral assistance",
        )
    if "philosophical_exchange" in p or "uncertainty" in p:
        return (
            "thoughtful", max(energy, 0.40), max(warmth, 0.56), min(pace, 0.985),
            max(stability, 0.52), min(max(style, 0.035), 0.065), max(emphasis, 0.22), "neutral",
            max(gesture, 0.24), "thoughtful", "thoughtful", "engaged", "thoughtful", "consider",
            0.58, "thoughtful exchange gets visible consideration without lecture mode",
        )
    if "milestone" in p:
        return (
            "bright", max(energy, 0.61), max(warmth, 0.68), max(pace, 1.025),
            min(stability, 0.47), max(style, 0.06), max(emphasis, 0.30), "happy",
            max(gesture, 0.38), "lively", "celebrate", "engaged", "animated", "celebrate",
            0.42, "shared milestone gets a real visible reaction",
        )
    if "creative_aesthetic" in p:
        return (
            "engaged", max(energy, 0.49), max(warmth, 0.58), pace,
            min(stability, 0.50), max(style, 0.055), max(emphasis, 0.24), avatar,
            max(gesture, 0.30), pause_style, "engaged", "engaged", "natural", "interest",
            0.52, "creative/aesthetic talk makes Mary's taste visibly engaged",
        )
    if "close_connection" in p:
        return (
            profile, max(energy, 0.43), max(warmth, 0.62), pace,
            min(stability, 0.51), max(style, 0.04), max(emphasis, 0.20), avatar,
            max(gesture, 0.24), pause_style, "familiar", "engaged", "natural", reaction_style,
            0.60, "close familiarity relaxes Mary's formal restraint",
        )

    return (
        profile, energy, warmth, pace, stability, style, emphasis, avatar, gesture,
        pause_style, gesture_style, gaze_style, head_style, reaction_style, restraint, reason,
    )


def _performance_beats(
    text: str,
    *,
    profile: str,
    avatar: str,
    gesture_style: str,
    gaze_style: str,
    head_style: str,
    energy: float,
    warmth: float,
    patterns: list[str],
) -> list[dict[str, Any]]:
    """Create at most three timing-relative presentation beats.

    The score is deliberately independent of exact audio timing.  Surfaces map
    0..1 fractions onto whatever duration they actually have (ElevenLabs audio,
    device TTS, captions, etc.).
    """
    value = " ".join(str(text or "").split()).strip()
    if not value:
        return []

    chunks = [part.strip() for part in re.split(r"(?<=[.!?])\s+", value) if part.strip()]
    if len(chunks) > 3:
        # Preserve a beginning, middle and landing rather than making the avatar
        # jitter for every sentence in a long answer.
        middle = " ".join(chunks[1:-1])
        chunks = [chunks[0], middle, chunks[-1]]
    if not chunks:
        chunks = [value]

    # Sarcasm/teasing often lives in the *landing*, even when the text is only
    # one sentence.  Split the presentation score rather than the transcript so
    # a renderer can hold a dry face/gaze for most of the line and let the smirk
    # appear at the end.  No words are changed and surfaces without beat support
    # simply ignore this refinement.
    if len(chunks) == 1 and "playful_banter" in set(patterns):
        return [
            {
                "start": 0.0,
                "end": 0.76,
                "expression": "neutral",
                "gesture_style": "tease",
                "gaze_style": gaze_style,
                "head_style": "tilt",
                "energy": round(_clamp(energy, 0.0, 1.0), 3),
                "warmth": round(_clamp(warmth, 0.0, 1.0), 3),
                "role": "opening",
            },
            {
                "start": 0.76,
                "end": 1.0,
                "expression": "happy",
                "gesture_style": "amused",
                "gaze_style": gaze_style,
                "head_style": "amused",
                "energy": round(_clamp(min(1.0, energy + 0.04), 0.0, 1.0), 3),
                "warmth": round(_clamp(warmth, 0.0, 1.0), 3),
                "role": "landing",
            },
        ]

    lengths = [max(1, len(chunk)) for chunk in chunks]
    total = float(sum(lengths))
    cursor = 0.0
    beats: list[dict[str, Any]] = []
    p = set(patterns)

    for index, length in enumerate(lengths):
        start = cursor / total
        cursor += length
        end = cursor / total
        expression = avatar
        beat_gesture = gesture_style
        beat_head = head_style
        beat_gaze = gaze_style
        beat_energy = energy

        if "playful_banter" in p:
            # A dry/teasing opener followed by the smile landing reads more like
            # sarcasm than holding a happy face for the entire line.
            expression = "neutral" if index == 0 else "happy"
            beat_head = "tilt" if index == 0 else "amused"
            beat_gesture = "tease" if index == 0 else "amused"
        elif "embarrassment" in p:
            expression = "surprised" if index == 0 else "happy"
            beat_gaze = "glance_away" if index == 0 else "engaged"
        elif "affection" in p:
            expression = "happy"
            beat_head = "tilt" if index == 0 else "soft"
            beat_energy = min(beat_energy, 0.58)
        elif "philosophical_exchange" in p or "uncertainty" in p:
            expression = "neutral"
            beat_head = "thoughtful"
        elif "moral_boundary" in p or "anger" in p:
            beat_head = "still"
            beat_gaze = "direct"
        elif "excitement" in p or "milestone" in p:
            expression = "happy"
            beat_head = "animated"

        beats.append({
            "start": round(start, 3),
            "end": round(end, 3),
            "expression": expression,
            "gesture_style": beat_gesture,
            "gaze_style": beat_gaze,
            "head_style": beat_head,
            "energy": round(_clamp(beat_energy, 0.0, 1.0), 3),
            "warmth": round(_clamp(warmth, 0.0, 1.0), 3),
            "role": "opening" if index == 0 else ("landing" if index == len(lengths) - 1 else "develop"),
        })
    return beats


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
