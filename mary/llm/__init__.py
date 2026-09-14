"""
MaryV2 LLM Package

Public interface for Mary's language-model abstraction layer.
"""

from .interface import (
    GenerationCost,
    GenerationOperation,
    GenerationPrivacy,
    GenerationRequest,
    dispatch_generation,
    generation_correlation_id,
    LLMInterface,
    LLMMessage,
    ProviderRoute,
    LLMResponse,
)
from .local_engine_discovery import (
    DetectedLocalEngine,
    LocalEnginePreset,
    PRESETS as LOCAL_ENGINE_PRESETS,
    discover_local_engines,
    discovery_status as local_engine_discovery_status,
)
from .router import LLMRouter


__all__ = [
    "LLMInterface",
    "LLMMessage",
    "LLMResponse",
    "GenerationCost",
    "GenerationOperation",
    "GenerationPrivacy",
    "GenerationRequest",
    "ProviderRoute",
    "dispatch_generation",
    "generation_correlation_id",
    "LLMRouter",
    "DetectedLocalEngine",
    "LocalEnginePreset",
    "LOCAL_ENGINE_PRESETS",
    "discover_local_engines",
    "local_engine_discovery_status",
]
