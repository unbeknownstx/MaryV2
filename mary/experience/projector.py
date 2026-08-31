"""Build a stable, presentation-only Mary experience snapshot.

The projector is intentionally pure. It reads the dashboard/trace projections
that already exist, whitelists a small number of fields, and derives UI cues.
It never writes state and never treats a provider/model as Mary.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .models import ExperienceCue, ExperienceSnapshot
from .palette import theme_for


def _map(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _path(root: Mapping[str, Any], *parts: str, default: Any = None) -> Any:
    current: Any = root
    for part in parts:
        if not isinstance(current, Mapping):
            return default
        current = current.get(part)
    return default if current is None else current


def _text(*values: Any, default: str = "") -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return default


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _memory_count(dashboard: Mapping[str, Any]) -> int:
    # Dashboard state nests the live memory projection under ``live``; accept
    # older/direct shapes too so this presentation endpoint stays compatible.
    live = _map(dashboard.get("live"))
    character = _map(live.get("character"))
    if character.get("memory_count") is not None:
        return max(0, _int(character.get("memory_count")))

    memory = _map(live.get("memory") or dashboard.get("memory"))
    counts = _map(memory.get("counts"))
    if counts:
        # Only canonical memory kinds are summed; this avoids double counting a
        # future aggregate ``total`` entry.
        keys = ("episodic", "semantic", "working")
        return sum(max(0, _int(counts.get(key))) for key in keys if counts.get(key) is not None)
    if any(key in memory for key in ("episodic", "semantic", "working")):
        return sum(max(0, _int(memory.get(key))) for key in ("episodic", "semantic", "working"))
    for key in ("total", "count", "memory_count"):
        if key in memory:
            return max(0, _int(memory.get(key)))
    return 0


def _relationship(dashboard: Mapping[str, Any]) -> tuple[str, float]:
    relationship = _map(dashboard.get("relationship"))
    label = _text(
        relationship.get("label"),
        relationship.get("stage"),
        relationship.get("status"),
        _path(dashboard, "live", "relationship", "label"),
        default="Developing",
    )
    strength = _float(
        relationship.get("strength", relationship.get("closeness", relationship.get("trust", relationship.get("score", 0.0))))
    )
    if strength > 1.0:
        strength = strength / 100.0
    return label, _clamp(strength)


def _latency(trace: Mapping[str, Any]) -> float | None:
    for key in ("total_ms", "latency_ms", "pipeline_ms", "elapsed_ms"):
        if trace.get(key) is not None:
            value = _float(trace.get(key), -1.0)
            return value if value >= 0 else None
    timings = _map(trace.get("timings"))
    for key in ("total_ms", "pipeline_ms"):
        if timings.get(key) is not None:
            value = _float(timings.get(key), -1.0)
            return value if value >= 0 else None
    return None


def build_experience_snapshot(
    dashboard: Mapping[str, Any] | None,
    trace: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    dashboard = _map(dashboard)
    trace = _map(trace)

    live = _map(dashboard.get("live"))
    character = _map(live.get("character"))
    emotion = _map(dashboard.get("emotion"))
    core = _map(dashboard.get("core"))
    mobile = _map(dashboard.get("mobile"))
    turnmind = _map(trace.get("turn_mind") or trace.get("turnmind"))
    delivery = _map(trace.get("delivery") or trace.get("delivery_plan"))
    performance = _map(trace.get("performance_packet"))

    interaction_state = _text(
        character.get("runtime_status"),
        character.get("status"),
        live.get("status"),
        trace.get("interaction_state"),
        default="idle",
    ).lower()
    mood = _text(emotion.get("primary"), character.get("mood"), turnmind.get("mood"), default="neutral")
    energy = _text(character.get("energy"), turnmind.get("energy"), default="calm")

    conversation_id = _text(
        trace.get("conversation_id"),
        mobile.get("conversation_id"),
        default="creator-primary",
    )
    conversation_label = _text(trace.get("conversation"), mobile.get("conversation_label"), default="Main")

    relationship_label, relationship_strength = _relationship(dashboard)
    memory_count = _memory_count(dashboard)

    provider = _text(trace.get("provider"), _path(trace, "provenance", "provider"), default="—")
    model = _text(trace.get("model"), _path(trace, "provenance", "model"), default="—")
    lane = _text(trace.get("lane"), turnmind.get("lane"), default="adaptive")
    active_task = _text(character.get("current_task"), character.get("task"), live.get("current_task"), dashboard.get("current_task"), default="")

    expression = _text(
        delivery.get("avatar_expression"),
        performance.get("expression"),
        turnmind.get("expression"),
        default=mood,
    ).lower()
    gesture = _text(delivery.get("gesture_style"), performance.get("gesture"), default="natural").lower()
    gaze = _text(delivery.get("gaze_style"), performance.get("gaze"), default="engaged").lower()

    theme = theme_for(mood=mood, interaction_state=interaction_state, energy=energy)
    cues: list[ExperienceCue] = [
        ExperienceCue("interaction", interaction_state, 0.85 if interaction_state != "idle" else 0.25, "live"),
        ExperienceCue("emotion", mood, _clamp(_float(emotion.get("intensity"), 0.45)), "emotion"),
    ]
    if relationship_label:
        cues.append(ExperienceCue("relationship", relationship_label, relationship_strength, "relationship"))
    if memory_count:
        cues.append(ExperienceCue("continuity", f"{memory_count} indexed memories", min(1.0, memory_count / 50.0), "memory"))
    if provider and provider != "—":
        cues.append(ExperienceCue("runtime", provider, 0.2, "trace", model))

    snapshot = ExperienceSnapshot(
        version="1.0",
        authority="presentation_projection_only",
        identity_owner="mary_core",
        interaction_state=interaction_state,
        mood=mood,
        energy=energy,
        conversation_id=conversation_id,
        conversation_label=conversation_label,
        relationship_label=relationship_label,
        relationship_strength=relationship_strength,
        memory_count=memory_count,
        active_task=active_task,
        provider=provider,
        model=model,
        lane=lane,
        latency_ms=_latency(trace),
        expression=expression,
        gesture=gesture,
        gaze=gaze,
        theme=theme,
        cues=tuple(cues),
        metadata={
            "architecture": _text(core.get("architecture"), default="13.2"),
            "core_online": core.get("ok", True) is not False,
            "mobile_authority": _text(mobile.get("authority"), default="mary_core"),
            "character_records": _int(_path(dashboard, "character_sourcebook", "records", default=0)),
        },
    )
    return snapshot.to_dict()
