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
]