"""Display-safe executable integration graph for the canonical MaryV2 runtime.

This module does not own state. It verifies that existing subsystem owners are
wired into one runtime and reports optional capability readiness separately from
required architecture connections.
"""
from __future__ import annotations

from typing import Any


def _edge(name: str, connected: bool, *, required: bool = True, owner: str = "") -> dict[str, Any]:
    return {
        "name": name,
        "connected": bool(connected),
        "required": bool(required),
        "owner": owner,
    }


def build_integration_graph(*, application: Any, service: Any | None = None) -> dict[str, Any]:
    mary = getattr(application, "mary", None)
    ecosystem = getattr(application, "ecosystem", None)
    turn_mind = getattr(mary, "turn_mind", None)
    realtime = getattr(mary, "realtime", None)
    presence = getattr(ecosystem, "presence", None)
    router = getattr(mary, "llm", None)
    system_contract = getattr(mary, "system_contract", None)

    contract = {}
    if callable(getattr(system_contract, "snapshot", None)):
        try:
            contract = dict(system_contract.snapshot(mary) or {})
        except Exception:
            contract = {}

    edges = [
        _edge("application -> canonical Mary", mary is not None, owner="MaryApplication"),
        _edge("ecosystem -> canonical Mary", ecosystem is not None and getattr(ecosystem, "mary", None) is mary, owner="MaryEcosystem"),
        _edge("reasoning/reflection/task generation -> one LLM router", bool(contract.get("single_llm_router")), owner="LLMRouter"),
        _edge("TurnMind -> character", turn_mind is not None and getattr(turn_mind, "character", None) is getattr(mary, "character", None), owner="CharacterCore"),
        _edge("TurnMind -> authored character sourcebook", turn_mind is not None and getattr(turn_mind, "character_sourcebook", None) is getattr(mary, "character_sourcebook", None), owner="CharacterSourcebook"),
        _edge("root authority -> canonical Mary", getattr(mary, "root_authority", None) is not None, owner="MaryRootAuthority"),
        _edge("character evaluation -> canonical Mary", getattr(mary, "character_evaluation", None) is not None, owner="MaryEvaluationSet"),
        _edge("TurnMind -> relationship", turn_mind is not None and getattr(turn_mind, "relationship", None) is getattr(mary, "relationship", None), owner="RelationshipManager"),
        _edge("TurnMind -> agency", turn_mind is not None and getattr(turn_mind, "agency", None) is getattr(mary, "agency", None), owner="Agency"),
        _edge("TurnMind -> autonomy", turn_mind is not None and getattr(turn_mind, "autonomy", None) is getattr(mary, "autonomy", None), owner="AutonomyRuntime"),
        _edge("TurnMind -> shared emotion", turn_mind is not None and getattr(turn_mind, "emotion", None) is getattr(mary, "emotion", None), owner="EmotionManager"),
        _edge("Presence -> realtime attention bus", presence is not None and realtime is not None and getattr(presence, "attention", None) is getattr(realtime, "attention", None), owner="AttentionBus/PresenceManager"),
        _edge("performance director -> TurnMind", turn_mind is not None and getattr(mary, "performance", None) is getattr(turn_mind, "performance", None), owner="PerformanceDirector"),
        _edge("training feedback -> canonical Mary", getattr(mary, "training_feedback", None) is not None, owner="ResponseFeedbackStore"),
        _edge("production workspace -> canonical ecosystem", ecosystem is not None and getattr(ecosystem, "production", None) is not None, owner="ProductionStudio"),
        _edge("creative service catalog -> canonical Mary", getattr(mary, "creative_services", None) is not None, owner="CreativeServiceRegistry"),
        _edge("compute registry -> canonical Mary", getattr(mary, "node_registry", None) is not None, owner="NodeRegistry"),
    ]

    if service is not None:
        edges.extend([
            _edge("Core service -> application", getattr(service, "application", None) is application, owner="MaryCoreService"),
            _edge("Core service -> canonical Mary", getattr(service, "mary", None) is mary, owner="MaryCoreService"),
            _edge("remote Ollama provider -> shared router", getattr(service, "_device_ollama_provider", None) is not None and router is not None, required=False, owner="DeviceOllamaProvider"),
            _edge("device task broker -> Core service", getattr(service, "device_tasks", None) is not None, owner="DeviceTaskBroker"),
        ])

    required_failures = [item["name"] for item in edges if item["required"] and not item["connected"]]
    optional_unavailable = [item["name"] for item in edges if not item["required"] and not item["connected"]]
    return {
        "healthy": not required_failures,
        "required_failures": required_failures,
        "optional_unavailable": optional_unavailable,
        "edges": edges,
        "authority": {
            "identity_relationship_memory_character_agency": "mary_core",
            "authored_character_evidence": "CharacterSourcebook",
            "root_hierarchy": "MaryRootAuthority",
            "workspace_artifacts": "MaryEcosystem",
            "production_artifacts": "ProductionStudio",
            "model_policy": "LLMRouter",
            "device_execution": "permission-bounded capability node",
            "training_data": "explicit creator feedback only",
            "external_consequential_actions": "creator approval",
        },
        "policy": "connection health is architecture truth; optional provider availability is never treated as authority",
    }
