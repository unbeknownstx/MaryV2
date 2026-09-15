"""Optional research/runtime candidates mined for future MaryV2 promotion.

Nothing in this catalog is imported as a startup dependency or granted identity,
memory, tool, network, filesystem, or spending authority. Promotion requires
explicit configuration plus benchmark/evaluation evidence.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from importlib.util import find_spec
import os
from typing import Any


@dataclass(frozen=True)
class ResearchRuntime:
    runtime_id: str
    domain: str
    role: str
    integration: str
    authority: str
    readiness_probe: str
    maturity: str
    notes: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


CATALOG: tuple[ResearchRuntime, ...] = (
    ResearchRuntime("coconut", "reasoning", "continuous_latent_reasoning", "offline_lab", "proposal_only", "env:MARY_COCONUT_LAB_READY", "experimental", "Hidden-state recurrence research; never required by Core."),
    ResearchRuntime("recurrent_reasoning", "reasoning", "depth_recurrent_latent_compute", "offline_lab", "proposal_only", "env:MARY_RECURRENT_REASONING_LAB_READY", "experimental", "Huginn/TRM/MoDr-style recurrence and branching experiments."),
    ResearchRuntime("latent_verifier", "reasoning", "latent_state_verification", "offline_lab", "evaluation_only", "env:MARY_LATENT_VERIFIER_READY", "experimental", "LTO/process-reward style verifier experiments."),
    ResearchRuntime("vllm", "inference", "cuda_serving_speculation", "node_service", "capability_only", "module:vllm", "production_candidate", "Future CUDA server; benchmark before scheduler promotion."),
    ResearchRuntime("sglang", "inference", "cuda_serving_prefix_cache", "node_service", "capability_only", "module:sglang", "production_candidate", "Future CUDA server; benchmark against vLLM/llama.cpp."),
    ResearchRuntime("executorch", "mobile", "on_device_inference", "native_client", "capability_only", "module:executorch", "production_candidate", "iOS/iPadOS/edge inference candidate; native integration required."),
    ResearchRuntime("mlc_llm", "mobile", "metal_mobile_inference", "native_client", "capability_only", "module:mlc_llm", "production_candidate", "Metal/iOS/iPadOS model runtime candidate."),
    ResearchRuntime("exo", "distributed", "heterogeneous_model_sharding", "external_node_fabric", "capability_only", "env:MARY_EXO_READY", "experimental", "Optional distributed inference fabric; Mary Core remains state authority."),
    ResearchRuntime("pipecat", "realtime", "voice_pipeline_orchestration", "optional_transport", "presentation_only", "module:pipecat", "production_candidate", "Streaming audio/voice orchestration candidate."),
    ResearchRuntime("livekit_agents", "realtime", "webrtc_agent_transport", "optional_transport", "presentation_only", "env:MARY_LIVEKIT_AGENTS_READY", "production_candidate", "Realtime participant/WebRTC transport candidate."),
    ResearchRuntime("a2a_gateway", "interop", "agent_to_agent_delegation", "bounded_gateway", "proposal_only", "env:MARY_A2A_GATEWAY_READY", "experimental", "External agents are workers, never Mary identity."),
    ResearchRuntime("areal", "learning", "agent_reinforcement_learning", "offline_lab", "proposal_only", "env:MARY_AREAL_READY", "experimental", "Offline/controlled trajectory learning only."),
    ResearchRuntime("verl", "learning", "reinforcement_learning", "offline_lab", "proposal_only", "module:verl", "experimental", "Offline model optimization after MaryBench gates."),
    ResearchRuntime("opentelemetry", "observability", "genai_trace_export", "optional_exporter", "evaluation_only", "module:opentelemetry", "production_candidate", "Export structural telemetry only; no prompt/response retention by default."),
)


def _probe(probe: str) -> tuple[bool, str]:
    kind, _, target = str(probe).partition(":")
    if kind == "env":
        ready = str(os.getenv(target, "")).strip().lower() in {"1", "true", "yes", "on"}
        return ready, "configured" if ready else "not_configured"
    if kind == "module":
        try:
            ready = find_spec(target) is not None
        except (ImportError, ValueError):
            ready = False
        return ready, "installed" if ready else "not_installed"
    return False, "unknown_probe"


def research_runtime_status() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for item in CATALOG:
        ready, state = _probe(item.readiness_probe)
        row = item.to_dict()
        row.update({"ready": ready, "state": state})
        rows.append(row)
    return {
        "version": "13.32",
        "runtimes": rows,
        "ready": [item["runtime_id"] for item in rows if item["ready"]],
        "semantics": {
            "discovery_only": True,
            "core_startup_dependency": False,
            "identity_authority": False,
            "memory_authority": False,
            "tool_authority": False,
            "automatic_training": False,
            "automatic_self_modification": False,
        },
    }
