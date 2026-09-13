"""Translate 13.17 cognitive plans into 13.11 home-compute workload hints.

This bridge does not execute anything and does not bypass device permissions.
It lets Mary's cognitive runtime express latency/locality needs to the existing
benchmark-aware node scheduler.
"""
from __future__ import annotations

from typing import Any

from mary.distributed.compute_fabric import WorkloadRequest


def workload_from_cognitive_plan(
    capability: str,
    plan: dict[str, Any],
    *,
    privacy_required: bool = False,
) -> WorkloadRequest:
    mode = str(plan.get("cognitive_mode") or "balanced").strip().lower()
    latency = str(plan.get("latency_priority") or "responsive").strip().lower()
    depth = str(plan.get("reasoning_depth") or "moderate").strip().lower()
    try:
        local_preference = float(plan.get("local_preference", 0.65))
    except (TypeError, ValueError):
        local_preference = 0.65

    realtime = latency in {"fast", "responsive"} or mode == "relational"
    local_preferred = local_preference >= 0.5
    if mode == "deliberate" or depth == "deep":
        operation = "deep_reasoning"
        estimated_seconds = 18.0
    elif mode == "relational":
        operation = "conversation"
        estimated_seconds = 2.0
    elif mode == "direct":
        operation = "quick_answer"
        estimated_seconds = 1.5
    else:
        operation = "general_reasoning"
        estimated_seconds = 5.0

    return WorkloadRequest(
        capability=str(capability).strip().lower(),
        operation=operation,
        realtime=realtime,
        privacy_required=bool(privacy_required),
        local_preferred=local_preferred,
        cost_sensitive=True,
        estimated_seconds=estimated_seconds,
    )


def cognitive_route_preview(scheduler: Any, capability: str, plan: dict[str, Any], *, privacy_required: bool = False) -> dict[str, Any]:
    request = workload_from_cognitive_plan(capability, plan, privacy_required=privacy_required)
    preview = scheduler.route_preview(request)
    preview["cognitive_plan"] = {
        "cognitive_mode": str(plan.get("cognitive_mode") or "balanced"),
        "reasoning_depth": str(plan.get("reasoning_depth") or "moderate"),
        "latency_priority": str(plan.get("latency_priority") or "responsive"),
        "local_preference": plan.get("local_preference"),
    }
    preview["authority"] = "scheduling_hint_only"
    return preview
