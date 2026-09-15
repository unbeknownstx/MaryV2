"""
MaryV2 LLM Package

Public interface for Mary's language-model abstraction layer.

Keep this package initializer lightweight. In particular, do not eagerly import
``router`` here: governance/resource imports content-free provider evidence
modules under ``mary.llm`` and the router itself depends on ResourceGovernor.
Eagerly importing both creates a package-initialization cycle. LLMRouter remains
available lazily for backwards-compatible ``from mary.llm import LLMRouter``.
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


def __getattr__(name: str):
    """Lazily expose heavy public objects without coupling package imports."""
    if name == "LLMRouter":
        from .router import LLMRouter

        return LLMRouter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
