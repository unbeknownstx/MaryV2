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
    cognition = getattr(mary, "cognition", None)
    reasoning = getattr(mary, "reasoning", None)
    reflection = getattr(mary, "reflection", None)
    memory = getattr(mary, "memory", None)
    growth = getattr(mary, "growth", None)
    tools = getattr(mary, "tools", None)
    autonomy = getattr(mary, "autonomy", None)
    node_registry = getattr(mary, "node_registry", None)
    browser_sensor = getattr(mary, "browser_context_sensor", None)
    game_router = getattr(mary, "game_action_router", None)
    performance_profiles = getattr(mary, "performance_profiles", None)
    invocation_ledger = getattr(mary, "capability_invocations", None)

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
        _edge(
            "cognition/reasoning/reflection -> shared LLM router",
            cognition is not None
            and getattr(cognition, "reasoning_engine", None) is reasoning
            and getattr(cognition, "reflection_engine", None) is reflection
            and getattr(reasoning, "llm", None) is router
            and getattr(reflection, "llm", None) is router,
            owner="CognitiveOrchestrator/LLMRouter",
        ),
        _edge("TurnMind -> character", turn_mind is not None and getattr(turn_mind, "character", None) is getattr(mary, "character", None), owner="CharacterCore"),
        _edge("TurnMind -> authored character sourcebook", turn_mind is not None and getattr(turn_mind, "character_sourcebook", None) is getattr(mary, "character_sourcebook", None), owner="CharacterSourcebook"),
        _edge("root authority -> canonical Mary", getattr(mary, "root_authority", None) is not None, owner="MaryRootAuthority"),
        _edge("character evaluation -> canonical Mary", getattr(mary, "character_evaluation", None) is not None, owner="MaryEvaluationSet"),
        _edge("TurnMind -> relationship", turn_mind is not None and getattr(turn_mind, "relationship", None) is getattr(mary, "relationship", None), owner="RelationshipManager"),
        _edge("TurnMind -> agency", turn_mind is not None and getattr(turn_mind, "agency", None) is getattr(mary, "agency", None), owner="Agency"),
        _edge("TurnMind -> autonomy", turn_mind is not None and getattr(turn_mind, "autonomy", None) is getattr(mary, "autonomy", None), owner="AutonomyRuntime"),
        _edge(
            "MemoryManager retrieval -> canonical memory stores",
            memory is not None
            and getattr(memory, "retrieval", None) is not None
            and getattr(memory, "episodic", None) is not None
            and getattr(memory, "semantic", None) is not None
            and getattr(memory, "working", None) is not None
            and getattr(getattr(memory, "retrieval", None), "episodic", None)
            is getattr(memory, "episodic", None)
            and getattr(getattr(memory, "retrieval", None), "semantic", None)
            is getattr(memory, "semantic", None)
            and getattr(getattr(memory, "retrieval", None), "working", None)
            is getattr(memory, "working", None),
            owner="MemoryManager/MemoryRetriever",
        ),
        _edge(
            "MemoryManager consolidation -> canonical memory and retrieval",
            memory is not None
            and getattr(memory, "consolidation", None) is not None
            and getattr(memory, "retrieval", None) is not None
            and getattr(memory, "episodic", None) is not None
            and getattr(memory, "semantic", None) is not None
            and getattr(memory, "working", None) is not None
            and getattr(getattr(memory, "consolidation", None), "episodic_memory", None)
            is getattr(memory, "episodic", None)
            and getattr(getattr(memory, "consolidation", None), "semantic_memory", None)
            is getattr(memory, "semantic", None)
            and getattr(getattr(memory, "consolidation", None), "working_memory", None)
            is getattr(memory, "working", None)
            and getattr(getattr(memory, "consolidation", None), "retrieval", None)
            is getattr(memory, "retrieval", None),
            owner="MemoryManager/MemoryConsolidator",
        ),
        _edge(
            "GrowthEngine -> canonical Mary",
            growth is not None and getattr(growth, "mary", None) is mary,
            owner="GrowthEngine",
        ),
        _edge(
            "GrowthEngine -> canonical memory",
            growth is not None
            and getattr(growth, "mary", None) is mary
            and memory is not None
            and getattr(getattr(growth, "mary", None), "memory", None) is memory,
            owner="GrowthEngine/MemoryManager",
        ),
        _edge(
            "GrowthEngine -> canonical preference promotion",
            growth is not None
            and getattr(growth, "mary", None) is mary
            and getattr(mary, "preference_promotion", None) is not None
            and getattr(mary, "preferences", None) is not None
            and getattr(getattr(growth, "mary", None), "preference_promotion", None)
            is getattr(mary, "preference_promotion", None)
            and getattr(getattr(growth, "mary", None), "preferences", None)
            is getattr(mary, "preferences", None),
            owner="GrowthEngine/PreferencePromotionSystem",
        ),
        _edge(
            "ToolManager -> canonical tool registry",
            tools is not None
            and getattr(tools, "registry", None) is not None
            and (turn_mind is None or getattr(turn_mind, "tools", None) is tools),
            owner="ToolManager/ToolRegistry",
        ),
        _edge("TurnMind -> shared emotion", turn_mind is not None and getattr(turn_mind, "emotion", None) is getattr(mary, "emotion", None), owner="EmotionManager"),
        _edge("Presence -> realtime attention bus", presence is not None and realtime is not None and getattr(presence, "attention", None) is getattr(realtime, "attention", None), owner="AttentionBus/PresenceManager"),
        _edge(
            "attention -> shared realtime decision trace",
            realtime is not None
            and getattr(getattr(realtime, "attention", None), "decision_trace", None)
            is getattr(realtime, "decision_trace", None),
            owner="AttentionBus/RealtimeDecisionTrace",
        ),
        _edge(
            "streaming -> canonical presence",
            ecosystem is not None
            and getattr(getattr(ecosystem, "streaming", None), "presence", None) is presence,
            owner="StreamingPresenceCoordinator/PresenceManager",
        ),
        _edge(
            "streaming -> shared speaker scheduler",
            ecosystem is not None
            and realtime is not None
            and getattr(getattr(ecosystem, "streaming", None), "speaker_scheduler", None)
            is getattr(realtime, "speaker_scheduler", None),
            owner="StreamingPresenceCoordinator/SpeakerScheduler",
        ),
        _edge(
            "realtime -> confirmed VAD barge-in gate",
            realtime is not None and callable(getattr(realtime, "report_voice_activity", None)),
            owner="RealtimeInteractionCoordinator",
        ),
        _edge(
            "ecosystem -> bounded cross-surface awareness",
            ecosystem is not None and getattr(ecosystem, "cross_surface", None) is not None,
            owner="CrossSurfaceAwareness",
        ),
        _edge(
            "ecosystem -> bounded dynamic action windows",
            ecosystem is not None
            and realtime is not None
            and getattr(ecosystem, "action_windows", None) is not None
            and getattr(getattr(ecosystem, "action_windows", None), "decision_trace", None)
            is getattr(realtime, "decision_trace", None),
            owner="ActionWindowRegistry/RealtimeDecisionTrace",
        ),
        _edge(
            "ecosystem -> model adapter lab",
            ecosystem is not None and getattr(ecosystem, "adapter_lab", None) is not None,
            owner="AdapterLab",
        ),
        _edge(
            "node routing -> capability readiness",
            node_registry is not None
            and callable(getattr(node_registry, "update_capability_readiness", None))
            and callable(getattr(node_registry, "route_preview", None)),
            owner="NodeRegistry",
        ),
        _edge(
            "realtime -> read-only brain activity projection",
            realtime is not None
            and getattr(getattr(realtime, "brain_activity", None), "realtime", None) is realtime,
            required=False,
            owner="BrainActivityProjection/RealtimeInteractionCoordinator",
        ),
        _edge(
            "browser context -> canonical perception boundary",
            browser_sensor is not None
            and getattr(browser_sensor, "perception", None) is getattr(mary, "perception_director", None),
            required=False,
            owner="BrowserContextSensor/PerceptionDirector",
        ),
        _edge(
            "game semantic intent -> canonical node routing",
            game_router is not None
            and getattr(game_router, "node_registry", None) is node_registry,
            required=False,
            owner="GameActionRouter/NodeRegistry",
        ),
        _edge(
            "runtime performance profile -> Core resource policy",
            performance_profiles is not None
            and callable(getattr(performance_profiles, "status", None)),
            required=False,
            owner="RuntimePerformanceProfiles",
        ),
        _edge(
            "capability orchestration -> bounded invocation ledger",
            invocation_ledger is not None
            and callable(getattr(invocation_ledger, "begin", None)),
            required=False,
            owner="CapabilityInvocationLedger",
        ),
        _edge("performance director -> TurnMind", turn_mind is not None and getattr(mary, "performance", None) is getattr(turn_mind, "performance", None), owner="PerformanceDirector"),
        _edge("training feedback -> canonical Mary", getattr(mary, "training_feedback", None) is not None, owner="ResponseFeedbackStore"),
        _edge("production workspace -> canonical ecosystem", ecosystem is not None and getattr(ecosystem, "production", None) is not None, owner="ProductionStudio"),
        _edge("creative service catalog -> canonical Mary", getattr(mary, "creative_services", None) is not None, owner="CreativeServiceRegistry"),
        _edge("compute registry -> canonical Mary", node_registry is not None, owner="NodeRegistry"),
        _edge(
            "MaryApplication -> canonical autonomy",
            getattr(application, "mary", None) is mary
            and autonomy is not None
            and callable(getattr(application, "_ensure_autonomy_started", None))
            and callable(getattr(application, "_cycle_autonomy", None)),
            owner="MaryApplication/AutonomyRuntime",
        ),
        _edge(
            "MaryApplication -> proposal-only autonomy policy",
            getattr(application, "mary", None) is mary
            and autonomy is not None
            and getattr(turn_mind, "autonomy", None) is autonomy
            and callable(getattr(application, "_agency_autonomy_proposal_trigger", None)),
            owner="MaryApplication/AutonomyRuntime",
        ),
    ]

    if service is not None:
        edges.extend([
            _edge("Core service -> application", getattr(service, "application", None) is application, owner="MaryCoreService"),
            _edge("Core service -> canonical Mary", getattr(service, "mary", None) is mary, owner="MaryCoreService"),
            _edge("remote Ollama provider -> shared router", getattr(service, "_device_ollama_provider", None) is not None and router is not None, required=False, owner="DeviceOllamaProvider"),
            _edge("device task broker -> Core service", getattr(service, "device_tasks", None) is not None, owner="DeviceTaskBroker"),
            _edge(
                "device broker/provider -> canonical node registry",
                getattr(service, "mary", None) is mary
                and getattr(service, "device_tasks", None) is not None
                and getattr(getattr(service, "_device_ollama_provider", None), "registry", None)
                is node_registry
                and getattr(getattr(service, "_device_ollama_provider", None), "broker", None)
                is getattr(service, "device_tasks", None),
                required=False,
                owner="NodeRegistry/DeviceTaskBroker/DeviceOllamaProvider",
            ),
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
