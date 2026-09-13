"""Bridge 13.17 cognition hints into Mary's existing presentation contract.

The output is presentation-only metadata suitable for DeliveryPlan/
PerformancePacket construction. It never claims an avatar action occurred and
never mutates emotion, character, relationship, or identity state.
"""
from __future__ import annotations

from typing import Any


_INTENT_OVERRIDES: dict[str, dict[str, Any]] = {
    "attend_to_user": {"gaze_style": "engaged"},
    "brighten_expression": {"avatar_expression": "bright"},
    "soften_expression": {"avatar_expression": "soft"},
    "firm_expression": {"avatar_expression": "focused"},
    "increase_gesture_energy": {"gesture_energy_delta": 0.18},
    "reduce_gesture_energy": {"gesture_energy_delta": -0.16},
    "controlled_emphasis": {"gesture_style": "controlled", "head_style": "steady"},
    "slower_delivery": {"pace_delta": -0.08, "pause_style": "thoughtful"},
    "lively_delivery": {"pace_delta": 0.07, "pause_style": "quick"},
    "brief_thinking_beat": {"reaction_style": "focus", "pre_speech_pause_ms": 180},
}


def delivery_overrides_from_cognitive_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Return bounded presentation overrides from 13.17 embodiment intents."""
    intents = [str(item).strip() for item in plan.get("embodiment_intents", []) if str(item).strip()]
    result: dict[str, Any] = {
        "source": "cognitive_character_runtime",
        "authority": "presentation_hint_only",
        "intents": list(dict.fromkeys(intents))[:12],
    }
    gesture_delta = 0.0
    pace_delta = 0.0
    for intent in result["intents"]:
        update = _INTENT_OVERRIDES.get(intent)
        if not update:
            continue
        gesture_delta += float(update.get("gesture_energy_delta", 0.0))
        pace_delta += float(update.get("pace_delta", 0.0))
        for key, value in update.items():
            if key not in {"gesture_energy_delta", "pace_delta"}:
                result[key] = value
    if gesture_delta:
        result["gesture_energy_delta"] = round(max(-0.4, min(0.4, gesture_delta)), 3)
    if pace_delta:
        result["pace_delta"] = round(max(-0.15, min(0.15, pace_delta)), 3)
    return result


def apply_cognitive_overrides(delivery: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    """Merge hints into a copy of an existing delivery mapping.

    Existing explicit delivery values remain the baseline; numeric deltas are
    applied within conservative presentation ranges.
    """
    merged = dict(delivery or {})
    overrides = delivery_overrides_from_cognitive_plan(plan)
    if "avatar_expression" in overrides:
        merged["avatar_expression"] = overrides["avatar_expression"]
    for key in ("gaze_style", "gesture_style", "head_style", "reaction_style", "pause_style"):
        if key in overrides:
            merged[key] = overrides[key]
    if "gesture_energy_delta" in overrides:
        try:
            current = float(merged.get("gesture_energy", merged.get("energy", 0.45)))
        except (TypeError, ValueError):
            current = 0.45
        merged["gesture_energy"] = round(max(0.0, min(1.0, current + overrides["gesture_energy_delta"])), 3)
    if "pace_delta" in overrides:
        try:
            current_pace = float(merged.get("pace", 1.0))
        except (TypeError, ValueError):
            current_pace = 1.0
        merged["pace"] = round(max(0.85, min(1.15, current_pace + overrides["pace_delta"])), 3)
    if "pre_speech_pause_ms" in overrides:
        metadata = dict(merged.get("metadata") or {})
        metadata["pre_speech_pause_ms"] = int(overrides["pre_speech_pause_ms"])
        metadata["cognitive_embodiment_intents"] = overrides["intents"]
        merged["metadata"] = metadata
    return merged
