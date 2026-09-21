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
        ledger = getattr(mary, "model_experiments", None)
        if ledger is not None and callable(getattr(ledger, "snapshot", None)):
            snapshot = ledger.snapshot()
        else:
            # Compatibility fallback for older/partial application fixtures.
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
        trial = _mapping(raw.get("trial_evidence"))
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
            "trial_evidence": {
                "dispatches": int(trial.get("dispatches") or 0),
                "attempts": int(trial.get("attempts") or 0),
                "completed": int(trial.get("completed") or 0),
                "failed": int(trial.get("failed") or 0),
                "rejected": int(trial.get("rejected") or 0),
                "expired": int(trial.get("expired") or 0),
                "completed_trial_observed": bool(trial.get("completed_trial_observed")),
                "latest_status": str(trial.get("latest_status") or "")[:40],
                "last_observed_at": str(trial.get("last_observed_at") or "")[:80],
                "quality_verified": False,
                "authority": "content_free_trial_evidence_only",
            },
        })
    recent_events = []
    for raw in list(snapshot.get("recent_events") or [])[-32:]:
        if not isinstance(raw, dict):
            continue
        details = _mapping(raw.get("details"))
        recent_events.append({
            "id": str(raw.get("id") or "")[:160],
            "experiment_id": str(raw.get("experiment_id") or "")[:160],
            "event_type": str(raw.get("event_type") or "")[:80],
            "occurred_at": str(raw.get("occurred_at") or "")[:80],
            "details": {
                key: value
                for key, value in details.items()
                if key in {
                    "candidate_id",
                    "runtime",
                    "artifact_fingerprint",
                    "dataset_fingerprint",
                    "reviewed_by",
                    "source",
                    "node_id",
                    "benchmark_source",
                    "artifact_match",
                    "mary_fit",
                    "latency_ms",
                    "trial_ready",
                    "missing_scores",
                    "failed_scores",
                    "score_keys",
                    "task_id",
                    "capability",
                    "status",
                    "provider",
                    "model",
                    "error_class",
                }
            },
        })
    return {
        "version": snapshot.get("version"),
        "count": int(snapshot.get("count", len(records)) or 0),
        "trial_ready": int(snapshot.get("trial_ready", 0) or 0),
        "trial_outcomes": int(snapshot.get("trial_outcomes", 0) or 0),
        "completed_trials": int(snapshot.get("completed_trials", 0) or 0),
        "event_count": int(snapshot.get("event_count", len(recent_events)) or 0),
        "records": records,
        "recent_events": recent_events,
        "promotion_performed": False,
        "authority": "experiment_evidence_only",
    }


def _capability_contract(capability_improvement: dict[str, Any]) -> dict[str, Any]:
    """Normalize live capability evidence into one surface-safe contract."""
    rows: list[dict[str, Any]] = []
    for name, raw in sorted(capability_improvement.items()):
        if not isinstance(raw, dict):
            continue
        advertised = bool(raw.get("currently_advertised"))
        available = bool(raw.get("currently_available"))
        authorized = bool(raw.get("execution_authorized"))
        demonstrated = bool(raw.get("demonstrated"))
        degrading = bool(raw.get("degrading_procedure_ids"))
        evidence_needed = [
            str(item)[:240]
            for item in list(raw.get("evidence_needed") or [])[:12]
            if str(item).strip()
        ]
        if degrading:
            state = "degrading"
        elif demonstrated and available and authorized:
            state = "demonstrated_ready"
        elif demonstrated and available:
            state = "demonstrated_permission_required"
        elif demonstrated:
            state = "historically_demonstrated_offline"
        elif advertised or available:
            state = "advertised_untested"
        else:
            state = "evidence_only"
        rows.append({
            "capability": str(name)[:160],
            "state": state,
            "advertised": advertised,
            "available": available,
            "execution_authorized": authorized,
            "demonstrated": demonstrated,
            "degrading": degrading,
            "attempts": int(raw.get("attempts") or 0),
            "verified_successes": int(raw.get("verified_successes") or 0),
            "evidence_strength": float(raw.get("strongest_evidence_strength") or 0.0),
            "evidence_needed": evidence_needed,
        })
    return {
        "version": "13.74",
        "capabilities": rows[:64],
        "demonstrated": sum(1 for row in rows if row["demonstrated"]),
        "execution_ready": sum(1 for row in rows if row["state"] == "demonstrated_ready"),
        "degrading": sum(1 for row in rows if row["degrading"]),
        "evidence_gaps": sum(len(row["evidence_needed"]) for row in rows),
        "authority": (
            "read-only self-capability evidence; advertisement, competence, permission "
            "and execution remain separate"
        ),
    }


def _knowledge_evaluation_readiness(
    knowledge: dict[str, Any],
    substrate: dict[str, Any],
    evaluation_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Summarize whether the local substrate is ready for deterministic regression evaluation."""
    enabled = int(knowledge.get("enabled") or substrate.get("enabled") or 0)
    indexed = int(knowledge.get("indexed_documents") or substrate.get("indexed_chunks") or 0)
    stale_derivatives = list(substrate.get("stale_derivatives") or [])
    stale_local = list(substrate.get("stale_local_indexes") or [])
    observed = dict(evaluation_evidence or {})
    evidence_needed: list[str] = []
    if enabled <= 0:
        evidence_needed.append("enable at least one reviewed local knowledge pack")
    if indexed <= 0:
        evidence_needed.append("index or connect evidence before retrieval regression can prove recall")
    if stale_local:
        evidence_needed.append("rebuild stale local indexes before treating evaluation as current")
    if stale_derivatives:
        evidence_needed.append("rebuild stale semantic derivatives from their current source fingerprints")
    if not int(observed.get("runs") or 0):
        evidence_needed.append("run the deterministic retrieval regression suite and retain content-free evidence")
    elif bool(observed.get("stale")):
        evidence_needed.append("rerun deterministic retrieval regression against the current substrate fingerprint")
    elif not bool(observed.get("latest_all_passed")):
        evidence_needed.append("resolve failing retrieval regression cases before claiming evaluated health")
    return {
        "version": "13.74",
        "enabled_packs": enabled,
        "indexed_chunks": indexed,
        "stale_local_indexes": len(stale_local),
        "stale_derivatives": len(stale_derivatives),
        "ready_for_regression": bool(enabled > 0 and indexed > 0 and not stale_local and not stale_derivatives),
        "evaluation_runs": int(observed.get("runs") or 0),
        "latest_evaluation_passed": bool(observed.get("latest_all_passed")),
        "evaluation_stale": bool(observed.get("stale")),
        "current_substrate_match": bool(observed.get("current_substrate_match")),
        "evaluated_health_current": bool(
            enabled > 0
            and indexed > 0
            and not stale_local
            and not stale_derivatives
            and int(observed.get("runs") or 0) > 0
            and bool(observed.get("latest_all_passed"))
            and not bool(observed.get("stale"))
        ),
        "retrieval_can_decline": True,
        "citation_evidence_required": True,
        "deterministic_evaluator": "KnowledgeFabricEvaluator",
        "evidence_needed": evidence_needed,
        "automatic_rebuild": False,
        "authority": "evaluation readiness only; retrieval never becomes memory or truth automatically",
    }


def _live_scene_summary(ecosystem: Any) -> dict[str, Any]:
    """Project bounded situational presence without leaking scene content."""
    presence = getattr(ecosystem, "presence", None)
    scene = getattr(presence, "scene", None)
    snapshot = _status(scene, "snapshot")
    participants = _mapping(snapshot.get("participants"))
    recent_events = [
        item for item in list(snapshot.get("recent_events") or [])[:16]
        if isinstance(item, dict)
    ]
    return {
        "version": "13.75",
        "available": bool(snapshot),
        "mode": str(snapshot.get("mode") or "")[:40],
        "floor_owner": str(snapshot.get("floor_owner") or "none")[:40],
        "realtime_phase": str(snapshot.get("realtime_phase") or "idle")[:40],
        "participant_count": len(participants),
        "recent_event_count": len(recent_events),
        "has_activity": bool(str(snapshot.get("activity") or "").strip()),
        "has_project": bool(str(snapshot.get("project") or "").strip()),
        "has_workspace": bool(str(snapshot.get("workspace") or "").strip()),
        "has_selected_asset": bool(str(snapshot.get("selected_asset") or "").strip()),
        "has_mary_target": bool(str(snapshot.get("mary_target") or "").strip()),
        "has_mary_goal": bool(str(snapshot.get("mary_goal") or "").strip()),
        "updated_at": str(snapshot.get("updated_at") or "")[:80],
        "persistence": "none",
        "authority": "ephemeral_context_only",
    }


def _improvement_agenda(
    capability_contract: dict[str, Any],
    knowledge_evaluation: dict[str, Any],
    procedure_intelligence: dict[str, Any],
    model_evidence: dict[str, Any],
) -> dict[str, Any]:
    """Combine existing evidence gaps into one non-executing improvement agenda."""
    items: list[dict[str, Any]] = []

    for row in list(capability_contract.get("capabilities") or [])[:64]:
        if not isinstance(row, dict):
            continue
        needs = [str(item)[:240] for item in list(row.get("evidence_needed") or [])[:8] if str(item).strip()]
        if not needs and not bool(row.get("degrading")):
            continue
        items.append({
            "kind": "capability",
            "subject": str(row.get("capability") or "")[:160],
            "state": str(row.get("state") or "")[:80],
            "attention": "recovery" if bool(row.get("degrading")) else "evidence",
            "evidence_needed": needs,
            "automatic_action": False,
        })

    if not bool(knowledge_evaluation.get("ready_for_regression")):
        needs = [
            str(item)[:240]
            for item in list(knowledge_evaluation.get("evidence_needed") or [])[:8]
            if str(item).strip()
        ]
        items.append({
            "kind": "knowledge",
            "subject": "local_knowledge_substrate",
            "state": "attention_required",
            "attention": (
                "recovery"
                if int(knowledge_evaluation.get("stale_local_indexes") or 0)
                or int(knowledge_evaluation.get("stale_derivatives") or 0)
                else "evidence"
            ),
            "evidence_needed": needs,
            "automatic_action": False,
        })

    for row in list(procedure_intelligence.get("procedures") or [])[:32]:
        if not isinstance(row, dict):
            continue
        needs = [str(item)[:240] for item in list(row.get("evidence_needed") or [])[:8] if str(item).strip()]
        if not needs and not bool(row.get("degrading")):
            continue
        items.append({
            "kind": "procedure",
            "subject": str(row.get("skill_id") or row.get("name") or "")[:180],
            "state": str(row.get("state") or "")[:80],
            "attention": "recovery" if bool(row.get("degrading")) else "evidence",
            "evidence_needed": needs,
            "automatic_action": False,
        })

    for row in list(model_evidence.get("records") or [])[:16]:
        if not isinstance(row, dict):
            continue
        needs = [str(item)[:240] for item in list(row.get("evidence_needed") or [])[:8] if str(item).strip()]
        if not needs:
            continue
        items.append({
            "kind": "model_experiment",
            "subject": str(row.get("id") or row.get("candidate_id") or "")[:180],
            "state": str(row.get("status") or "experimental")[:80],
            "attention": "trial" if bool(row.get("trial_ready")) else "evidence",
            "evidence_needed": needs,
            "automatic_action": False,
        })

    order = {"recovery": 0, "evidence": 1, "trial": 2}
    items.sort(key=lambda item: (order.get(str(item.get("attention")), 9), str(item.get("kind")), str(item.get("subject"))))
    return {
        "version": "13.75",
        "open_items": len(items),
        "recovery_items": sum(1 for item in items if item.get("attention") == "recovery"),
        "evidence_items": sum(1 for item in items if item.get("attention") == "evidence"),
        "trial_items": sum(1 for item in items if item.get("attention") == "trial"),
        "items": items[:48],
        "automatic_execution": False,
        "automatic_permission": False,
        "automatic_model_promotion": False,
        "authority": "read_only_evidence_agenda",
    }


def _embodiment_projection(live_scene: dict[str, Any] | None = None) -> dict[str, Any]:
    """Project Riko-style one-character/many-bodies readiness without creating a body owner."""
    try:
        from mary.expression.surface_performance import capabilities_for_surface
        surfaces = {
            name: capabilities_for_surface(name).to_dict()
            for name in ("desktop", "mobile_web", "ios_native", "stream", "vr")
        }
    except Exception as exc:
        return {
            "available": False,
            "surfaces": {},
            "error_type": type(exc).__name__,
            "authority": "presentation_projection_only",
        }
    return {
        "version": "13.75",
        "canonical_score": "PerformancePacket",
        "voice_direction_owner": "DeliveryPlan",
        "scene_context_owner": "LiveScene",
        "surfaces": surfaces,
        "live_scene": dict(live_scene or {}),
        "one_character_many_bodies": True,
        "renderer_infers_character": False,
        "body_persistence": False,
        "body_identity_authority": False,
        "policy": (
            "surfaces render or degrade canonical acting/voice/scene cues; renderer state "
            "does not become identity, memory, relationship, emotion or world truth"
        ),
        "authority": "presentation_projection_only",
    }


def build_system_fabric_projection(application: Any, *, service: Any | None = None) -> dict[str, Any]:
    """Return one read-only status contract shared by Desktop/PWA/iPhone."""

    mary = getattr(application, "mary", None)
    ecosystem = getattr(application, "ecosystem", None)
    continuity = _status(getattr(mary, "experiential_continuity", None), "status")
    knowledge_owner = getattr(mary, "knowledge_fabric", None)
    knowledge = _status(knowledge_owner, "status")
    knowledge_intelligence = _status(knowledge_owner, "substrate_profile")
    knowledge_evaluation_evidence: dict[str, Any] = {}
    try:
        from mary.knowledge import knowledge_substrate_fingerprint
        evaluation_owner = getattr(mary, "knowledge_evaluation_evidence", None)
        snapshot = getattr(evaluation_owner, "snapshot", None)
        if callable(snapshot) and knowledge_owner is not None:
            knowledge_evaluation_evidence = dict(snapshot(
                current_substrate_fingerprint=knowledge_substrate_fingerprint(knowledge_owner)
            ) or {})
    except Exception:
        knowledge_evaluation_evidence = {}
    nodes = _status(getattr(mary, "node_registry", None), "snapshot")
    try:
        from mary.distributed import build_node_intelligence
        node_intelligence = build_node_intelligence(
            getattr(mary, "node_registry", None),
            getattr(mary, "competence", None),
        )
    except Exception as exc:
        node_intelligence = {
            "available": False,
            "nodes": [],
            "registered": 0,
            "connected": 0,
            "error_type": type(exc).__name__,
            "authority": "read_only_projection_no_execution_authority",
        }
    adapter_lab = _status(getattr(ecosystem, "adapter_lab", None), "snapshot")
    candidates = _candidate_summary(getattr(ecosystem, "model_candidates", None))
    experiments = _model_experiment_summary(mary)
    self_evidence = _status(
        getattr(mary, "self_introspection", None),
        "capability_evidence",
    )
    procedure_intelligence = _mapping(self_evidence.get("procedural_memory"))
    capability_improvement = _mapping(
        self_evidence.get("capability_improvement")
    )
    model_evidence = _mapping(self_evidence.get("model_experiments"))
    procedure_rows = list(procedure_intelligence.get("procedures") or [])[:32]
    evidence_gap_count = sum(
        len(list(_mapping(item).get("evidence_needed") or []))
        for item in procedure_rows
    )
    capability_gap_count = sum(
        len(list(_mapping(item).get("evidence_needed") or []))
        for item in capability_improvement.values()
        if isinstance(item, dict)
    )
    capability_contract = _capability_contract(capability_improvement)
    knowledge_evaluation = _knowledge_evaluation_readiness(
        knowledge,
        knowledge_intelligence,
        knowledge_evaluation_evidence,
    )
    live_scene = _live_scene_summary(ecosystem)
    embodiment = _embodiment_projection(live_scene)
    improvement_agenda = _improvement_agenda(
        capability_contract,
        knowledge_evaluation,
        procedure_intelligence,
        model_evidence,
    )
    intelligence_loop = {
        "version": "13.73",
        "terminal_outcomes_feed_competence": True,
        "competence_feeds_procedure_ranking": True,
        "procedure_failures_feed_revision_pressure": True,
        "evidence_selected_dispatch_supported": True,
        "durable_auto_binding": False,
        "automatic_permission": False,
        "automatic_model_promotion": False,
        "demonstrated_procedures": int(
            procedure_intelligence.get("demonstrated", 0) or 0
        ),
        "degrading_procedures": int(
            procedure_intelligence.get("degrading", 0) or 0
        ),
        "procedure_evidence_gaps": int(evidence_gap_count),
        "capability_evidence_gaps": int(capability_gap_count),
        "selection_policy": (
            "explicit plan dispatch may ephemerally choose only an approved, "
            "demonstrated, non-degrading procedure that clears bounded score "
            "and ambiguity gates; node permission remains separate"
        ),
        "authority": "read_only_convergence_projection",
    }
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
        "knowledge": {
            **knowledge,
            "substrate": knowledge_intelligence,
            "evaluation_readiness": knowledge_evaluation,
            "evaluation_evidence": knowledge_evaluation_evidence,
        },
        "world": {
            "beliefs": _mapping(continuity.get("world_model")),
            "temporal": _mapping(continuity.get("temporal")),
            "review": {
                "reconciliation_groups": int(
                    _mapping(continuity.get("world_model")).get("reconciliation_groups", 0)
                    or 0
                ),
            },
        },
        "continuity": {
            "experience": _mapping(continuity.get("experience")),
            "replay": _mapping(continuity.get("replay")),
            "skills": _mapping(continuity.get("skills")),
            "procedure_review": {
                "revision_attention": int(
                    _mapping(continuity.get("skills")).get("revision_attention", 0)
                    or 0
                ),
                "revision_candidates": int(
                    _mapping(continuity.get("skills")).get("revision_candidates", 0)
                    or 0
                ),
                "demonstrated": int(
                    procedure_intelligence.get("demonstrated", 0) or 0
                ),
                "degrading": int(
                    procedure_intelligence.get("degrading", 0) or 0
                ),
                "procedures": list(
                    procedure_intelligence.get("procedures") or []
                )[:16],
                "authority": (
                    "read-only evidence projection; review, approval, binding "
                    "and execution remain explicit"
                ),
            },
            "plans": _mapping(continuity.get("plans")),
            "workflows": _mapping(continuity.get("workflows")),
            "verification": _mapping(continuity.get("verification")),
            "competence": _mapping(continuity.get("competence")),
        },
        "models": {
            "adapter_lab": adapter_lab,
            "candidates": candidates,
            "experiments": experiments,
            "evidence_readiness": model_evidence,
            "policy": "model/adapters are replaceable capabilities; benchmark and creator promotion remain explicit",
        },
        "compute": {
            "nodes": nodes,
            "node_intelligence": node_intelligence,
            "capability_improvement": capability_improvement,
            "capability_contract": capability_contract,
            **compute,
        },
        "intelligence_loop": intelligence_loop,
        "improvement_agenda": improvement_agenda,
        "embodiment": embodiment,
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
            "competence": "routing_and_procedure-ranking_evidence_only_after_hard_eligibility",
            "procedure_selection": "approved_demonstrated_non_degrading_ephemeral_only",
            "node_intelligence": "advertisement_readiness_permission_and_demonstrated_competence_are_distinct",
            "models": "benchmark_and_creator_promotion_required",
            "knowledge_evaluation": "deterministic_regression_no_automatic_truth_promotion",
            "embodiment": "one_character_many_bodies_performance_packet_authoritative",
            "improvement_agenda": "read_only_evidence_gaps_no_automatic_execution",
        },
    }
