"""Read-only intelligence projection for MaryV2 capability nodes.

Nodes remain replaceable workers. This module combines their live advertisements
with bounded competence evidence so Core/surfaces can distinguish:
- advertised capability,
- live readiness,
- device-local execution authorization,
- demonstrated observed competence.

It never routes, grants permission, promotes a model, or owns Mary state.
"""
from __future__ import annotations

from typing import Any


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def build_node_intelligence(
    registry: Any,
    competence: Any | None = None,
    *,
    competence_limit: int = 4,
) -> dict[str, Any]:
    try:
        snapshot = _mapping(registry.snapshot())
    except Exception as exc:
        return {
            "version": 1,
            "nodes": [],
            "registered": 0,
            "connected": 0,
            "available": False,
            "error_type": type(exc).__name__,
            "authority": "read_only_projection_no_execution_authority",
        }

    summary_fn = getattr(competence, "summary_for", None)
    nodes: list[dict[str, Any]] = []
    for raw in list(snapshot.get("nodes") or [])[:64]:
        if not isinstance(raw, dict):
            continue
        node_id = str(raw.get("node_id") or "")[:160]
        connected = bool(raw.get("connected"))
        capabilities: list[dict[str, Any]] = []
        for raw_name, raw_capability in list(_mapping(raw.get("capabilities")).items())[:96]:
            name = str(raw_name or "").strip().casefold()[:120]
            if not name:
                continue
            cap = _mapping(raw_capability)
            metadata = _mapping(cap.get("metadata"))
            available = bool(cap.get("available", True))
            readiness = str(
                cap.get("readiness") or ("ready" if available else "unavailable")
            )[:80]
            authorized = metadata.get("execution_authorized") is True
            evidence: list[dict[str, Any]] = []
            if callable(summary_fn) and node_id:
                try:
                    raw_evidence = list(
                        summary_fn(
                            name,
                            node_ids=(node_id,),
                            limit=max(1, min(12, int(competence_limit))),
                        )
                        or []
                    )
                except Exception:
                    raw_evidence = []
                for item in raw_evidence[:12]:
                    if not isinstance(item, dict):
                        continue
                    if str(item.get("node_id") or "") not in {"", node_id}:
                        continue
                    evidence.append({
                        "attempts": int(item.get("attempts") or 0),
                        "successes": int(item.get("successes") or 0),
                        "failures": int(item.get("failures") or 0),
                        "verified_successes": int(item.get("verified_successes") or 0),
                        "reliability": round(float(item.get("reliability") or 0.0), 4),
                        "evidence_strength": round(
                            float(item.get("evidence_strength") or 0.0), 4
                        ),
                        "mean_latency_ms": item.get("mean_latency_ms"),
                        "last_success": item.get("last_success"),
                        "last_observed_at": str(
                            item.get("last_observed_at") or ""
                        )[:80],
                    })

            attempts = sum(int(item["attempts"]) for item in evidence)
            verified_successes = sum(
                int(item["verified_successes"]) for item in evidence
            )
            if not connected:
                evidence_state = "offline"
            elif not available or readiness == "unavailable":
                evidence_state = "unavailable"
            elif attempts <= 0:
                evidence_state = "advertised_unverified"
            elif verified_successes <= 0:
                evidence_state = "observed_unverified"
            else:
                evidence_state = "demonstrated"

            capabilities.append({
                "name": name,
                "available": available,
                "readiness": readiness,
                "execution_authorized": authorized,
                "routable": bool(cap.get("routable", available and readiness in {"ready", "degraded"})),
                "evidence_state": evidence_state,
                "evidence": evidence,
                "experiment": {
                    "id": str(metadata.get("model_experiment_id") or "")[:160],
                    "trial_ready": metadata.get("model_experiment_trial_ready") is True,
                    "benchmark_verified": metadata.get(
                        "model_experiment_benchmark_verified"
                    ) is True,
                },
            })

        nodes.append({
            "node_id": node_id,
            "display_name": str(raw.get("display_name") or node_id)[:160],
            "platform": str(raw.get("platform") or "")[:80],
            "host_type": str(raw.get("host_type") or "")[:80],
            "surface": str(raw.get("surface") or "")[:80],
            "transport": str(raw.get("transport") or "")[:80],
            "connected": connected,
            "trusted": bool(raw.get("trusted")),
            "capabilities": capabilities,
            "counts": {
                "advertised": len(capabilities),
                "ready": sum(
                    1
                    for item in capabilities
                    if item["available"]
                    and item["readiness"] in {"ready", "degraded"}
                ),
                "authorized": sum(
                    1 for item in capabilities if item["execution_authorized"]
                ),
                "demonstrated": sum(
                    1 for item in capabilities if item["evidence_state"] == "demonstrated"
                ),
                "trial_ready_experiments": sum(
                    1
                    for item in capabilities
                    if item["experiment"]["trial_ready"]
                ),
            },
            "ownership": {
                "character_identity": False,
                "memory": False,
                "canonical_state": False,
            },
        })

    return {
        "version": 1,
        "registered": int(snapshot.get("registered") or len(nodes)),
        "connected": sum(1 for item in nodes if item["connected"]),
        "nodes": nodes,
        "semantics": {
            "advertised": "node reports capability presence",
            "ready": "runtime reports currently routable readiness",
            "authorized": "device-local execution permission is represented",
            "demonstrated": "terminal competence evidence includes verified success",
        },
        "execution_permission_granted": False,
        "routing_performed": False,
        "promotion_performed": False,
        "authority": "read_only_projection_no_execution_authority",
    }
