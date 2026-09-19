"""Bounded cross-surface projection of Mary's connected system fabric.

This module owns no state and grants no authority. It gives product surfaces one
stable vocabulary for systems already owned by canonical Mary Core. Only
structural/status information belongs here; private memory bodies, prompts,
secrets, raw traces and host filesystem paths are intentionally excluded.
"""
from __future__ import annotations

from typing import Any


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _status(owner: Any, *names: str) -> dict[str, Any]:
    if owner is None:
        return {}
    for name in names:
        method = getattr(owner, name, None)
        if not callable(method):
            continue
        try:
            return _mapping(method())
        except Exception as exc:
            return {"available": False, "error_type": type(exc).__name__}
    return {}


def _candidate_summary(catalog: Any) -> dict[str, Any]:
    snapshot = _status(catalog, "snapshot")
    candidates = list(snapshot.get("candidates") or [])
    return {
        "version": snapshot.get("version"),
        "count": int(snapshot.get("count", len(candidates)) or 0),
        "candidates": [
            {
                "id": str(item.get("id") or "")[:120],
                "kind": str(item.get("kind") or "")[:80],
                "runtime": str(item.get("runtime") or "")[:80],
                "roles": list(item.get("roles") or [])[:12],
                "license": str(item.get("license") or "")[:120],
                "required_base": str(item.get("required_base") or "")[:240],
                "upstream_base": str(item.get("upstream_base") or "")[:240],
            }
            for item in candidates[:24]
            if isinstance(item, dict)
        ],
        "authority": "reviewed experiment metadata only",
    }


def _model_experiment_summary(mary: Any) -> dict[str, Any]:
    """Project exact reviewed/benchmarked model evidence without model output."""
    try:
        from mary.learning import ModelExperimentLedger
        paths = getattr(getattr(mary, "config", None), "paths", None)
        runtime_root = getattr(paths, "runtime", None)
        if runtime_root is None:
            return {"count": 0, "trial_ready": 0, "records": []}
        snapshot = ModelExperimentLedger(
            runtime_root / "model_experiment_evidence.json"
        ).snapshot()
    except Exception as exc:
        return {
            "count": 0,
            "trial_ready": 0,
            "records": [],
            "available": False,
            "error_type": type(exc).__name__,
        }
    records = []
    for raw in list(snapshot.get("records") or [])[-24:]:
        if not isinstance(raw, dict):
            continue
        records.append({
            "id": str(raw.get("id") or "")[:160],
            "status": str(raw.get("status") or "")[:80],
            "candidate_id": str(raw.get("candidate_id") or "")[:160],
            "runtime": str(raw.get("runtime") or "")[:80],
            "model": str(raw.get("model") or "")[:240],
            "node_id": str(raw.get("node_id") or "")[:180],
            "mary_fit": raw.get("mary_fit"),
            "latency_ms": raw.get("latency_ms"),
            "benchmark_verified": bool(raw.get("benchmark_verified")),
            "trial_ready": bool(raw.get("trial_ready")),
            "missing_scores": list(raw.get("missing_scores") or [])[:16],
            "failed_scores": list(raw.get("failed_scores") or [])[:16],
        })
    return {
        "version": snapshot.get("version"),
        "count": int(snapshot.get("count", len(records)) or 0),
        "trial_ready": int(snapshot.get("trial_ready", 0) or 0),
        "records": records,
        "promotion_performed": False,
        "authority": "experiment_evidence_only",
    }


def build_system_fabric_projection(application: Any, *, service: Any | None = None) -> dict[str, Any]:
    """Return one read-only status contract shared by Desktop/PWA/iPhone."""

    mary = getattr(application, "mary", None)
    ecosystem = getattr(application, "ecosystem", None)
    continuity = _status(getattr(mary, "experiential_continuity", None), "status")
    knowledge = _status(getattr(mary, "knowledge_fabric", None), "status")
    nodes = _status(getattr(mary, "node_registry", None), "snapshot")
    adapter_lab = _status(getattr(ecosystem, "adapter_lab", None), "snapshot")
    candidates = _candidate_summary(getattr(ecosystem, "model_candidates", None))
    experiments = _model_experiment_summary(mary)
    training = _status(getattr(mary, "training_feedback", None), "status")
    character_eval = _status(getattr(mary, "character_evaluation", None), "snapshot")

    compute: dict[str, Any] = {}
    integration: dict[str, Any] = {}
    if service is not None:
        try:
            raw_compute = _mapping(service.compute_fabric_status())
            compute = {
                "tasks": _mapping(raw_compute.get("tasks")),
                "model_execution": _mapping(raw_compute.get("model_execution")),
                "capability_routes": _mapping(raw_compute.get("capability_routes")),
            }
        except Exception as exc:
            compute = {"available": False, "error_type": type(exc).__name__}
        try:
            raw_integration = _mapping(service.integration_status())
            runtime = _mapping(raw_integration.get("runtime"))
            integration = {
                "healthy": bool(raw_integration.get("healthy")),
                "operational": bool(raw_integration.get("operational")),
                "required_failures": list(raw_integration.get("required_failures") or [])[:32],
                "optional_unavailable": list(raw_integration.get("optional_unavailable") or [])[:64],
                "degraded": list(runtime.get("degraded") or [])[:32],
            }
        except Exception as exc:
            integration = {"healthy": False, "error_type": type(exc).__name__}

    return {
        "version": "1",
        "authority": {
            "identity_state": "mary_core",
            "projection": "read_only",
            "execution_permission": False,
            "promotion_permission": False,
        },
        "knowledge": knowledge,
        "world": {
            "beliefs": _mapping(continuity.get("world_model")),
            "temporal": _mapping(continuity.get("temporal")),
        },
        "continuity": {
            "experience": _mapping(continuity.get("experience")),
            "replay": _mapping(continuity.get("replay")),
            "skills": _mapping(continuity.get("skills")),
            "plans": _mapping(continuity.get("plans")),
            "workflows": _mapping(continuity.get("workflows")),
            "verification": _mapping(continuity.get("verification")),
            "competence": _mapping(continuity.get("competence")),
        },
        "models": {
            "adapter_lab": adapter_lab,
            "candidates": candidates,
            "experiments": experiments,
            "policy": "model/adapters are replaceable capabilities; benchmark and creator promotion remain explicit",
        },
        "compute": {"nodes": nodes, **compute},
        "training": {
            "feedback": training,
            "character_evaluation": character_eval,
            "automatic_training": False,
        },
        "integration": integration,
        "semantics": {
            "retrieval": "evidence_not_memory",
            "temporal_history": "historical_or_superseded_is_not_current_truth",
            "skills": "creator_approval_required",
            "competence": "routing_hint_only_after_hard_eligibility",
            "models": "benchmark_and_creator_promotion_required",
        },
    }
