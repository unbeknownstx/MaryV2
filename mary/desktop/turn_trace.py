"""Display-safe performance trace extraction for Mary Desktop turns.

This module intentionally contains no prompt or response bodies.  It translates
existing pipeline/cognition metadata into a bounded developer-facing trace that
can be shown in the desktop diagnostics surface without becoming Mary memory.
"""
from __future__ import annotations

from typing import Any, Mapping


def _ms(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return round(max(0.0, float(value)), 2)
    except (TypeError, ValueError):
        return None


def _safe_attempts(raw: Any, timing_raw: Any = None) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    timings = list(timing_raw or [])
    for index, item in enumerate(list(raw or [])[:12]):
        if not isinstance(item, Mapping):
            continue
        timing = timings[index] if index < len(timings) and isinstance(timings[index], Mapping) else {}
        result.append(
            {
                "provider": str(item.get("provider") or "unknown"),
                "status": str(item.get("status") or "unknown"),
                "elapsed_ms": _ms(timing.get("elapsed_ms")),
                "call_ms": _ms(timing.get("call_ms")),
            }
        )
    return result


def build_turn_trace(
    result: Any,
    *,
    pipeline_ms: float,
    avatar_ms: float,
    voice_payload: Mapping[str, Any] | None,
    worker_total_ms: float,
) -> dict[str, Any]:
    """Create a bounded trace from one completed canonical Mary pipeline turn."""

    values = dict(getattr(result, "metadata", {}).get("pipeline_values", {}) or {})
    cycle = values.get("cognitive_cycle")
    reasoning = getattr(cycle, "reasoning", None)
    reflection = getattr(cycle, "reflection", None)
    reasoning_meta = dict(getattr(reasoning, "metadata", {}) or {})
    reflection_meta = dict(getattr(reflection, "metadata", {}) or {})
    cycle_meta = dict(getattr(cycle, "metadata", {}) or {})
    cognition_timings = dict(cycle_meta.get("timings", {}) or {})
    voice_timings = dict((voice_payload or {}).get("timings", {}) or {})
    attempts = _safe_attempts(
        reasoning_meta.get("provider_attempts"),
        reasoning_meta.get("provider_attempt_timings"),
    )
    usage = dict(reasoning_meta.get("usage", {}) or {})

    provider_call_ms = None
    for attempt in reversed(attempts):
        if attempt.get("status") == "success" and attempt.get("call_ms") is not None:
            provider_call_ms = attempt["call_ms"]
            break

    timings: dict[str, float] = {}
    for name, value in {
        **cognition_timings,
        **voice_timings,
        "pipeline_ms": pipeline_ms,
        "avatar_ms": avatar_ms,
        "worker_total_ms": worker_total_ms,
        "provider_call_ms": provider_call_ms,
    }.items():
        number = _ms(value)
        if number is not None:
            timings[str(name)] = number

    return {
        "turn_id": str(getattr(result, "turn_id", "") or ""),
        "provider": str(reasoning_meta.get("provider") or "local/system"),
        "model": str(reasoning_meta.get("model") or "n/a"),
        "generation_purpose": str(reasoning_meta.get("generation_purpose") or "default/task"),
        "conversation_lane": str((reasoning_meta.get("conversation_lane") or {}).get("lane") or "n/a"),
        "reflection_mode": str(reflection_meta.get("mode") or "n/a"),
        "local_mind": dict(cycle_meta.get("local_mind", {}) or {}),
        "delivery_plan": dict(cycle_meta.get("delivery_plan", {}) or {}),
        "finish_reason": str(reasoning_meta.get("finish_reason") or "n/a"),
        "attempts": attempts,
        "usage": {
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "reasoning_tokens": usage.get("reasoning_tokens"),
        },
        "voice": {
            "enabled": bool((voice_payload or {}).get("enabled")),
            "provider": str((voice_payload or {}).get("provider") or "off"),
            "status": str((voice_payload or {}).get("status") or "unknown"),
        },
        "timings": timings,
    }
