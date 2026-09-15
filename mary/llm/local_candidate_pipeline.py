"""Bridge local-engine discovery into Mary's measured candidate pipeline.

Discovery means an endpoint answered and exposed a model ID. It does not mean
the model is trusted, suitable, fast, correct, or authorized. This module turns
13.42 discoveries into 13.39 qualified identities plus explicit measurement
requirements, without registering or routing them automatically.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable

from mary.distributed.model_instances import ModelInstanceIdentity
from mary.llm.local_engine_discovery import DetectedLocalEngine

VERSION = "13.49"


@dataclass(frozen=True)
class LocalModelCandidate:
    node_id: str
    engine_id: str
    model: str
    protocol: str
    base_url: str
    identity_strength: str
    qualified_id: str
    model_fingerprint: str
    measurement_requirements: tuple[str, ...] = (
        "runtime_capability_probe",
        "correctness_benchmark",
        "latency_benchmark",
        "resource_fit",
    )
    promotion_state: str = "measurement_required"
    auto_promoted: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _instance(node_id: str, engine: DetectedLocalEngine, model: str) -> ModelInstanceIdentity:
    return ModelInstanceIdentity(
        node_id=str(node_id or "local")[:96],
        engine=engine.engine_id,
        model=str(model or "unknown")[:200],
        variant=(
            "protocol-specific"
            if engine.identity_strength == "protocol_specific"
            else engine.identity_strength
        ),
        capabilities={},
    )


def candidates_from_discovery(
    engines: Iterable[DetectedLocalEngine],
    *,
    node_id: str,
) -> list[LocalModelCandidate]:
    """Convert reachable model listings into stable unmeasured candidates."""
    output: list[LocalModelCandidate] = []
    seen: set[tuple[str, str]] = set()
    for engine in engines:
        models = tuple(engine.models) or ("unknown",)
        for model in models:
            key = (engine.engine_id, str(model))
            if key in seen:
                continue
            seen.add(key)
            instance = _instance(node_id, engine, str(model))
            output.append(
                LocalModelCandidate(
                    node_id=str(node_id or "local")[:96],
                    engine_id=engine.engine_id,
                    model=str(model)[:200],
                    protocol=engine.protocol,
                    base_url=engine.base_url,
                    identity_strength=engine.identity_strength,
                    qualified_id=instance.qualified_id,
                    model_fingerprint=instance.fingerprint,
                )
            )
    output.sort(key=lambda item: item.qualified_id)
    return output


def measurement_plan(candidate: LocalModelCandidate) -> dict[str, Any]:
    """Describe the next evidence needed before the candidate may influence routing."""
    capability_probes = ["structured_json", "tools", "vision", "embeddings"]
    benchmark_lanes = ["conversation", "task_generation"]
    if candidate.identity_strength in {"port_hint", "protocol_only"}:
        identity_action = "preserve_ambiguous_engine_identity"
    else:
        identity_action = "protocol_identity_accepted_as_runtime_hint"
    return {
        "version": VERSION,
        "qualified_id": candidate.qualified_id,
        "model_fingerprint": candidate.model_fingerprint,
        "promotion_state": candidate.promotion_state,
        "auto_promoted": False,
        "capability_probes": capability_probes,
        "benchmark_lanes": benchmark_lanes,
        "resource_measurement": "required",
        "identity_action": identity_action,
        "execution_authorized": False,
        "policy": (
            "discovered candidates must be explicitly adopted and measured; "
            "reachability/model listing never changes Mary routing"
        ),
    }


def candidate_catalog(
    engines: Iterable[DetectedLocalEngine],
    *,
    node_id: str,
) -> dict[str, Any]:
    candidates = candidates_from_discovery(engines, node_id=node_id)
    return {
        "version": VERSION,
        "node_id": str(node_id or "local")[:96],
        "candidates": [item.to_dict() for item in candidates],
        "measurement_plans": [measurement_plan(item) for item in candidates],
        "count": len(candidates),
        "auto_promoted": 0,
        "execution_authorized": False,
        "authority": "discovery_to_measurement_planning_only",
    }
