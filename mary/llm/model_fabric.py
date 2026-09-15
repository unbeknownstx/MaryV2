"""Task-aware provider/model execution suitability for MaryV2.

The canonical vocabulary is:
    discovered != configured != authorized != reachable != feasible != suitable != preferred

This projection is advisory. It does not grant device permission, spend money,
change Mary identity/state, or silently promote a model. 13.60–13.64 provider
health/quota/pressure/readiness evidence belongs to this same execution fabric,
but remains subordinate to LLMRouter eligibility.
"""
from __future__ import annotations

from typing import Any

from .provider_catalog import (
    CATALOG_AUTHORITY,
    CATALOG_REVISION,
    FRONTIER_PROVIDER_NAMES,
    public_provider_catalog,
)


VERSION = "13.64"
MODEL_SUITABILITY_REVISION = "13.35"
RELIABILITY_REVISION = "13.37"
PROVIDER_OPERATIONAL_REVISION = "13.64"

TASK_LANES: dict[str, dict[str, Any]] = {
    "realtime_voice": {
        "latency_budget_ms": 1500.0,
        "min_success_rate": 0.95,
        "min_accuracy": 0.90,
        "realtime": True,
        "description": "Speech/backchannel path; latency and reliability dominate.",
    },
    "social_instant": {
        "latency_budget_ms": 2500.0,
        "min_success_rate": 0.90,
        "min_accuracy": 0.80,
        "realtime": True,
        "description": "Fast banter/presence; slow engines should not block the floor.",
    },
    "conversation": {
        "latency_budget_ms": 10000.0,
        "min_success_rate": 0.85,
        "min_accuracy": 0.75,
        "realtime": True,
        "description": "Normal interactive conversation.",
    },
    "private_conversation": {
        "latency_budget_ms": 60000.0,
        "min_success_rate": 0.75,
        "min_accuracy": 0.70,
        "realtime": False,
        "privacy_required": True,
        "description": "Creator-selected local/private conversation; slower local inference is acceptable.",
    },
    "deep_reasoning": {
        "latency_budget_ms": 180000.0,
        "min_success_rate": 0.70,
        "min_accuracy": 0.75,
        "realtime": False,
        "description": "Hard reasoning where correctness matters more than immediate latency.",
    },
    "coding_agent": {
        "latency_budget_ms": 180000.0,
        "min_success_rate": 0.80,
        "min_accuracy": 0.80,
        "realtime": False,
        "description": "Coding/engineering work; prefer measured correctness and tool fit.",
    },
    "research_synthesis": {
        "latency_budget_ms": 180000.0,
        "min_success_rate": 0.80,
        "min_accuracy": 0.75,
        "realtime": False,
        "description": "Research/long synthesis with provenance retained above the model layer.",
    },
    "long_context": {
        "latency_budget_ms": 300000.0,
        "min_success_rate": 0.75,
        "min_accuracy": 0.70,
        "realtime": False,
        "description": "Large-context work where context capacity can outweigh latency.",
    },
    "background": {
        "latency_budget_ms": 600000.0,
        "min_success_rate": 0.65,
        "min_accuracy": 0.60,
        "realtime": False,
        "description": "Offline/background work; cheap idle compute is valuable even when slow.",
    },
}


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def assess_local_capability_route(
    route: dict[str, Any] | None,
    lane: str,
) -> dict[str, Any]:
    """Classify a local capability using sanitized benchmark evidence only."""

    lane_name = str(lane or "conversation").strip().lower()
    profile = dict(TASK_LANES.get(lane_name) or TASK_LANES["conversation"])
    values = dict(route or {})
    selected = str(values.get("selected_node_id") or "")
    if not bool(values.get("available")) or not selected:
        return {
            "lane": lane_name,
            "status": "unavailable",
            "selected_node_id": selected or None,
            "measured": False,
            "reason": "no_routable_node",
        }

    benchmarks = dict(values.get("candidate_benchmarks") or {})
    bench = dict(benchmarks.get(selected) or {})
    latency = _float(bench.get("benchmark_latency_ms"))
    success = _float(bench.get("benchmark_success_rate"))
    throughput = _float(bench.get("benchmark_throughput"))
    accuracy = _float(bench.get("benchmark_accuracy"))
    useful_throughput = _float(bench.get("benchmark_useful_throughput"))
    measured = any(item is not None for item in (latency, success, throughput, accuracy, useful_throughput))

    if not measured:
        status = "experimental"
        reason = "available_but_unbenchmarked"
    elif success is not None and success < float(profile["min_success_rate"]):
        status = "avoid"
        reason = "measured_reliability_below_lane_requirement"
    elif accuracy is not None and accuracy < float(profile["min_accuracy"]):
        status = "avoid"
        reason = "measured_accuracy_below_lane_requirement"
    elif latency is not None and latency > float(profile["latency_budget_ms"]):
        if bool(profile.get("realtime")):
            status = "avoid"
            reason = "measured_latency_too_high_for_realtime_lane"
        else:
            status = "feasible_slow"
            reason = "measured_latency_above_target_but_lane_allows_slow_work"
    else:
        status = "preferred"
        reason = "measured_within_lane_requirements"

    return {
        "lane": lane_name,
        "status": status,
        "selected_node_id": selected,
        "measured": measured,
        "benchmark": {
            "latency_ms": latency,
            "success_rate": success,
            "throughput": throughput,
            "accuracy": accuracy,
            "useful_throughput": useful_throughput,
        },
        "requirements": {
            "latency_budget_ms": profile["latency_budget_ms"],
            "min_success_rate": profile["min_success_rate"],
            "min_accuracy": profile["min_accuracy"],
            "realtime": bool(profile.get("realtime")),
            "privacy_required": bool(profile.get("privacy_required", False)),
        },
        "reason": reason,
    }


def _frontier_status(
    routing: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Project frontier readiness without constructing optional providers."""

    catalog = {str(item["name"]): dict(item) for item in public_provider_catalog()}
    published = {
        str(item.get("provider") or "").strip().lower(): dict(item)
        for item in list(dict(routing or {}).get("providers") or [])
        if isinstance(item, dict)
    }
    output: list[dict[str, Any]] = []
    for name in FRONTIER_PROVIDER_NAMES:
        item = dict(catalog.get(name) or {"name": name})
        status = dict(published.get(name) or {})
        configured = bool(status.get("available", False))
        active_model = str(status.get("model") or item.get("default_model") or "")
        item.update({
            "configured": configured,
            "active_model": active_model,
            "promotion": "benchmark_required",
            "auto_promoted": False,
        })
        output.append(item)
    return output


def build_model_execution_fabric(
    router: Any,
    *,
    capability_routes: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a display-safe execution portfolio from existing routing truth."""

    routing_status = getattr(router, "routing_status", None)
    routing = dict(routing_status() or {}) if callable(routing_status) else {}
    active: list[dict[str, Any]] = []
    for raw in list(routing.get("providers") or []):
        item = dict(raw or {})
        available = bool(item.get("available"))
        source = str(item.get("source") or "configured_host")
        if not available:
            readiness = "unavailable"
        elif source == "capability_node":
            readiness = "available_requires_task_fit_measurement"
        else:
            readiness = "available_unbenchmarked"
        active.append({
            "provider": str(item.get("provider") or ""),
            "model": str(item.get("model") or ""),
            "available": available,
            "source": source,
            "cost_class": str(item.get("cost_class") or ""),
            "privacy_modes": list(item.get("privacy_modes") or []),
            "operations": list(item.get("operations") or []),
            "execution_readiness": readiness,
        })

    routes = dict(capability_routes or {})
    local_route = dict(routes.get("llm.ollama") or {})
    local_suitability = {lane: assess_local_capability_route(local_route, lane) for lane in TASK_LANES}

    return {
        "version": VERSION,
        "model_suitability_revision": MODEL_SUITABILITY_REVISION,
        "reliability_revision": RELIABILITY_REVISION,
        "provider_operational_revision": PROVIDER_OPERATIONAL_REVISION,
        "provider_catalog": {
            "revision": CATALOG_REVISION,
            "authority": CATALOG_AUTHORITY,
            "role": "approved_connection_metadata_not_execution_authority",
        },
        "active_candidates": active,
        "frontier_catalog": _frontier_status(routing),
        "task_lanes": {
            name: {**dict(values), "authority": "selection_policy_only"}
            for name, values in TASK_LANES.items()
        },
        "local_ollama_suitability": local_suitability,
        "provider_execution_policy": {
            "ordering": "router_eligibility_then_resource_governor_then_bounded_attempts",
            "health_quota_pressure": "operational_evidence_only",
            "catalog_can_enable_provider": False,
            "adaptive_can_add_ineligible_provider": False,
            "gateway_is_replaceable": True,
            "free_llm_api_required": False,
            "embedding_failover_requires_same_space": True,
        },
        "operating_policy": {
            "ordinary_budget": "zero_cost_and_free_only",
            "local_preference": "prefer_when_lane_suitable",
            "free_cloud_fallback_order": ["groq", "gemini", "openrouter"],
            "paid_frontier": "explicit_only",
            "quality_metric": "correctness_weighted_useful_throughput_when_available",
            "cohesion_priority": "successful_end_to_end_behavior_over_provider_novelty",
        },
        "promotion_policy": {
            "reachable_is_not_preferred": True,
            "benchmark_before_promotion": True,
            "correctness_matters_more_than_raw_speed": True,
            "raw_outputs_not_required_for_operational_benchmarks": True,
            "paid_requires_existing_authorization": True,
            "private_requires_local_or_private_capability": True,
            "models_never_own_identity_or_memory": True,
        },
        "authority": "planning_and_observability_only",
    }
