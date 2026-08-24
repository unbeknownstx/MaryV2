"""Display-safe performance trace extraction for Mary Desktop turns.

This module intentionally contains no prompt or response bodies.  It translates
existing pipeline/cognition metadata into a bounded developer-facing trace that
can be shown in the desktop diagnostics surface without becoming Mary memory.
"""
from __future__ import annotations

from math import isfinite
from typing import Any, Mapping


_RESPONSE_CLASSES = {
    "precision_local",
    "social_low_risk",
    "open_conversation",
    "thinking_required",
}
_RESPONSE_ENGINES = {
    "local_composer_v2",
    "conversation_generation",
    "task_generation",
    "reasoning_generation",
    "expert_consultation",
    "research_synthesis",
    "deterministic_system",
}
_LANES = {"social_instant", "conversation", "thinking", "expert"}
_DIALOGUE_ACTS = {
    "greet",
    "acknowledge",
    "thanks_response",
    "goodbye",
    "laugh",
    "react",
    "status",
    "known_fact",
    "known_preference",
    "opine",
    "ask",
    "answer",
    "follow_up",
    "clarify",
    "stay_quiet",
    "escalate",
}
_TARGET_LENGTHS = {"micro", "brief", "short", "medium", "long"}
_LOCAL_TIMING_KEYS = (
    "classification_ms",
    "local_composer_ms",
    "local_audit_ms",
    "shadow_ms",
)


def _ms(value: Any) -> float | None:
    try:
        if value is None:
            return None
        number = float(value)
        if not isfinite(number):
            return None
        return round(max(0.0, number), 2)
    except (TypeError, ValueError):
        return None


def _bounded_text(value: Any, *, limit: int = 240) -> str:
    if value is None or isinstance(value, (Mapping, list, tuple, set)):
        return ""
    enum_value = getattr(value, "value", value)
    return " ".join(str(enum_value).split()).strip()[:limit]


def _lane_name(value: Any) -> str:
    source = value.get("lane") if isinstance(value, Mapping) else value
    lane = _bounded_text(source, limit=32).lower()
    return lane if lane in _LANES else "n/a"


def _safe_lane_summary(value: Any) -> dict[str, Any]:
    lane = _lane_name(value)
    if lane == "n/a":
        return {}
    source = value if isinstance(value, Mapping) else {}
    result: dict[str, Any] = {"lane": lane}
    try:
        latency_target_ms = int(source.get("latency_target_ms"))
    except (TypeError, ValueError):
        latency_target_ms = 0
    if latency_target_ms > 0:
        result["latency_target_ms"] = min(latency_target_ms, 120_000)
    if "allow_model_revision" in source:
        result["allow_model_revision"] = bool(source.get("allow_model_revision"))
    return result


def _safe_plan_summary(value: Any) -> dict[str, Any]:
    """Project non-semantic delivery hints from a canonical local plan."""

    if not isinstance(value, Mapping):
        return {}
    result: dict[str, Any] = {}
    act = _bounded_text(
        value.get("act") or value.get("dialogue_act"),
        limit=48,
    ).lower()
    if act in _DIALOGUE_ACTS:
        result["act"] = act
    if "local" in value:
        result["local"] = bool(value.get("local"))
    target_length = _bounded_text(value.get("target_length"), limit=32).lower()
    if target_length in _TARGET_LENGTHS:
        result["target_length"] = target_length
    return result


def _safe_local_mind_summary(value: Any) -> dict[str, Any]:
    """Allowlist diagnostics; never copy plan slots or semantic values."""

    if not isinstance(value, Mapping):
        return {}
    result: dict[str, Any] = {}
    response_class = _bounded_text(value.get("response_class"), limit=40).lower()
    if response_class in _RESPONSE_CLASSES:
        result["response_class"] = response_class
    response_engine = _bounded_text(value.get("response_engine"), limit=64).lower()
    if response_engine in _RESPONSE_ENGINES:
        result["response_engine"] = response_engine
    escalation_reason = _bounded_text(value.get("escalation_reason"), limit=240)
    if escalation_reason:
        result["escalation_reason"] = escalation_reason
    if "shadow_enabled" in value:
        result["shadow_enabled"] = bool(value.get("shadow_enabled"))
    shadow_model = _bounded_text(value.get("shadow_model"), limit=96)
    if shadow_model:
        result["shadow_model"] = shadow_model
    for name in _LOCAL_TIMING_KEYS:
        number = _ms(value.get(name))
        if number is not None:
            result[name] = number
    elapsed_ms = _ms(value.get("elapsed_ms"))
    if elapsed_ms is not None:
        result["elapsed_ms"] = elapsed_ms
    if "local_only" in value:
        result["local_only"] = bool(value.get("local_only"))
    lane = _safe_lane_summary(value.get("conversation_lane") or value.get("lane"))
    if lane:
        result["conversation_lane"] = lane
    plan = _safe_plan_summary(value.get("plan"))
    if plan:
        result["plan"] = plan
    return result


def _response_engine(
    reasoning_meta: Mapping[str, Any],
    local_mind: Mapping[str, Any],
) -> str:
    configured = _bounded_text(
        reasoning_meta.get("response_engine")
        or local_mind.get("response_engine"),
        limit=64,
    ).lower()
    if configured in _RESPONSE_ENGINES:
        return configured
    provider = _bounded_text(reasoning_meta.get("provider"), limit=64).lower()
    if provider == "local/mind":
        return "local_composer_v2"
    if bool(reasoning_meta.get("llm_skipped")):
        return "deterministic_system"
    lane = _lane_name(reasoning_meta.get("conversation_lane"))
    purpose = _bounded_text(
        reasoning_meta.get("generation_purpose")
        or reasoning_meta.get("routing_purpose"),
        limit=64,
    ).lower()
    if lane in {"social_instant", "conversation"} and purpose in {
        "conversation",
        "conversation_fast",
    }:
        return "conversation_generation"
    return "task_generation"


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
    local_mind = _safe_local_mind_summary(cycle_meta.get("local_mind"))
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

    local_timings = {
        name: local_mind.get(name)
        for name in _LOCAL_TIMING_KEYS
    }
    timings: dict[str, float] = {}
    for name, value in {
        **cognition_timings,
        **local_timings,
        **voice_timings,
        "pipeline_ms": pipeline_ms,
        "avatar_ms": avatar_ms,
        "worker_total_ms": worker_total_ms,
        "provider_call_ms": provider_call_ms,
    }.items():
        number = _ms(value)
        if number is not None:
            timings[str(name)] = number

    response_class = _bounded_text(
        reasoning_meta.get("response_class")
        or local_mind.get("response_class"),
        limit=40,
    ).lower()
    if response_class not in _RESPONSE_CLASSES:
        response_class = "n/a"
    response_engine = _response_engine(reasoning_meta, local_mind)
    escalation_reason = _bounded_text(
        reasoning_meta.get("escalation_reason")
        or local_mind.get("escalation_reason"),
        limit=240,
    )
    shadow_enabled = bool(
        reasoning_meta.get("shadow_enabled", local_mind.get("shadow_enabled", False))
    )
    shadow_model = _bounded_text(
        reasoning_meta.get("shadow_model") or local_mind.get("shadow_model"),
        limit=96,
    )
    shadow_ms = _ms(
        reasoning_meta.get("shadow_ms")
        if reasoning_meta.get("shadow_ms") is not None
        else local_mind.get("shadow_ms")
    )

    return {
        "turn_id": str(getattr(result, "turn_id", "") or ""),
        "provider": str(reasoning_meta.get("provider") or "local/system"),
        "model": str(reasoning_meta.get("model") or "n/a"),
        "generation_purpose": str(reasoning_meta.get("generation_purpose") or "default/task"),
        "conversation_lane": _lane_name(reasoning_meta.get("conversation_lane")),
        "reflection_mode": str(reflection_meta.get("mode") or "n/a"),
        "response_class": response_class,
        "response_engine": response_engine,
        "escalation_reason": escalation_reason,
        "shadow_enabled": shadow_enabled,
        "shadow_model": shadow_model or None,
        "shadow_ms": shadow_ms,
        "local_mind": local_mind,
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
