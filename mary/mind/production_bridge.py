"""Display-safe bridge between production-local dialogue and Mary cognition.

This module carries only bounded control-plane metadata.  Canonical plans,
selected fact values, raw slots, and rationale text never cross into retained
runtime diagnostics.
"""
from __future__ import annotations

from typing import Any, Mapping

from .production_local import LOCAL_ENGINE, LOCAL_MODEL

_SAFE_FIELDS = (
    "response_class",
    "response_engine",
    "escalation_reason",
    "classification_ms",
    "local_composer_ms",
    "local_audit_ms",
    "shadow_enabled",
    "shadow_model",
    "shadow_ms",
    "elapsed_ms",
    "local_only",
)


def safe_local_metadata(raw: Any) -> dict[str, Any]:
    source = raw if isinstance(raw, Mapping) else {}
    result = {key: source.get(key) for key in _SAFE_FIELDS if key in source}
    lane = source.get("conversation_lane")
    if isinstance(lane, Mapping):
        result["conversation_lane"] = {
            key: lane.get(key)
            for key in ("lane", "latency_target_ms", "allow_model_revision")
            if key in lane
        }
    plan = source.get("plan")
    if isinstance(plan, Mapping):
        result["plan"] = {
            key: plan.get(key)
            for key in ("act", "local", "target_length")
            if key in plan
        }
    return result


def apply_local_cycle_metadata(cycle: Any, raw: Any) -> dict[str, Any]:
    safe = safe_local_metadata(raw)
    reasoning = getattr(cycle, "reasoning", None)
    metadata = getattr(reasoning, "metadata", None)
    if isinstance(metadata, dict):
        metadata.update({
            "provider": "local/mind",
            "model": LOCAL_MODEL,
            "generation_purpose": "local_dialogue",
            "routing_purpose": "local_dialogue",
            "response_class": safe.get("response_class"),
            "response_engine": LOCAL_ENGINE,
            "escalation_reason": None,
            "provider_attempts": [],
            "provider_attempt_timings": [],
            "conversation_lane": dict(safe.get("conversation_lane") or {}),
        })
    cycle_meta = getattr(cycle, "metadata", None)
    if isinstance(cycle_meta, dict):
        cycle_meta["local_mind"] = safe
        timings = cycle_meta.setdefault("timings", {})
        if isinstance(timings, dict):
            for key in ("classification_ms", "local_composer_ms", "local_audit_ms"):
                value = safe.get(key)
                if isinstance(value, (int, float)):
                    timings[key] = float(value)
    return safe


def merge_escalated_cycle_metadata(cycle: Any, raw: Any) -> dict[str, Any]:
    safe = safe_local_metadata(raw)
    cycle_meta = getattr(cycle, "metadata", None)
    if isinstance(cycle_meta, dict):
        cycle_meta["local_mind"] = safe
        timings = cycle_meta.setdefault("timings", {})
        if isinstance(timings, dict):
            for key in ("classification_ms", "local_composer_ms", "local_audit_ms"):
                value = safe.get(key)
                if isinstance(value, (int, float)):
                    timings[key] = float(value)
    reasoning = getattr(cycle, "reasoning", None)
    metadata = getattr(reasoning, "metadata", None)
    if isinstance(metadata, dict):
        local_class = safe.get("response_class")
        metadata["response_class"] = local_class
        metadata["response_engine"] = (
            "task_generation" if local_class == "thinking_required"
            else "conversation_generation" if local_class == "open_conversation"
            else metadata.get("response_engine")
        )
        metadata["escalation_reason"] = safe.get("escalation_reason")
    return safe
