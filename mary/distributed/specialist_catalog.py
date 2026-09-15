"""Optional specialist-backend catalog for MaryV2.

The catalog is discovery/diagnostics only. It gives the home compute fabric a
single vocabulary for experimental backends discovered from research without
making any of them Mary Core startup dependencies or authority owners.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from importlib.util import find_spec
import os
import shutil
from typing import Any


@dataclass(frozen=True)
class SpecialistBackend:
    backend_id: str
    domain: str
    role: str
    integration: str
    local_first: bool
    authority: str
    readiness_probe: str
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


CATALOG: tuple[SpecialistBackend, ...] = (
    SpecialistBackend("fluid_audio", "audio", "stt_vad_diarization", "native_bridge", True, "sensor_only", "env:MARY_FLUID_AUDIO_ENDPOINT", "Apple Neural Engine candidate; benchmark on Mac/iPhone."),
    SpecialistBackend("qwen3_asr", "audio", "stt", "node_service", True, "sensor_only", "env:MARY_QWEN_ASR_ENDPOINT", "Local multilingual ASR candidate; compare with whisper.cpp/faster-whisper."),
    SpecialistBackend("ten_vad", "audio", "vad", "node_library", True, "sensor_only", "module:ten_vad", "Optional low-latency VAD candidate."),
    SpecialistBackend("chatterbox", "audio", "tts_expression", "node_service", True, "presentation_only", "env:MARY_CHATTERBOX_ENDPOINT", "Optional expressive TTS; never identity authority."),
    SpecialistBackend("llama_cpp_mtmd", "vision", "multimodal_perception", "node_service", True, "sensor_only", "env:MARY_LLAMA_CPP_VLM_URL", "Image/audio/video perception through llama.cpp-compatible server."),
    SpecialistBackend("omniparser", "vision", "ui_structure", "node_service", True, "sensor_only", "env:MARY_OMNIPARSER_ENDPOINT", "Screenshot-to-UI semantics; no direct mouse/keyboard authority."),
    SpecialistBackend("graphiti", "character_memory", "temporal_graph_projection", "optional_adapter", False, "projection_only", "module:graphiti_core", "May enrich graph retrieval; canonical Mary owners remain authoritative."),
    SpecialistBackend("dspy_gepa", "learning", "prompt_program_optimization", "offline_lab", False, "proposal_only", "module:dspy", "Optimization proposals must pass MaryBench before manual promotion."),
    SpecialistBackend("phoenix", "observability", "experiment_tracing", "offline_or_hosted_lab", False, "evaluation_only", "module:phoenix", "Trace/evaluation sink only; no runtime authority."),
    SpecialistBackend("promptfoo", "evaluation", "regression_redteam", "cli_lab", True, "evaluation_only", "exe:promptfoo", "CI/offline behavioral regression candidate."),
    SpecialistBackend("unsloth", "training", "lora_qlora", "offline_lab", True, "proposal_only", "module:unsloth", "Future local adaptation after sufficient curated MaryBench evidence."),
    SpecialistBackend("axolotl", "training", "sft_dpo_grpo", "offline_lab", True, "proposal_only", "module:axolotl", "Future training lab; trained model remains replaceable cortex."),
)


def _probe(value: str) -> tuple[bool, str]:
    kind, _, target = str(value).partition(":")
    if kind == "env":
        configured = bool(os.getenv(target, "").strip())
        return configured, "configured" if configured else "not_configured"
    if kind == "module":
        try:
            available = find_spec(target) is not None
        except (ImportError, ValueError):
            available = False
        return available, "installed" if available else "not_installed"
    if kind == "exe":
        available = shutil.which(target) is not None
        return available, "installed" if available else "not_installed"
    return False, "unknown_probe"


def specialist_status() -> dict[str, Any]:
    backends: list[dict[str, Any]] = []
    for item in CATALOG:
        ready, state = _probe(item.readiness_probe)
        row = item.to_dict()
        row.update({"ready": ready, "state": state})
        backends.append(row)
    return {
        "version": "13.14",
        "backends": backends,
        "ready": [item["backend_id"] for item in backends if item["ready"]],
        "semantics": {
            "discovery_only": True,
            "core_startup_dependency": False,
            "external_identity_authority": False,
            "external_memory_authority": False,
            "arbitrary_shell": False,
        },
    }


def backend(backend_id: str) -> SpecialistBackend:
    clean = str(backend_id or "").strip().casefold()
    for item in CATALOG:
        if item.backend_id.casefold() == clean:
            return item
    raise KeyError(backend_id)
