"""
MaryV2 LLM Package

Public interface for Mary's language-model abstraction layer.
"""

from .interface import (
    LLMInterface,
    LLMMessage,
    LLMResponse,
)

from .router import LLMRouter


__all__ = [
    "LLMInterface",
    "LLMMessage",
    "LLMResponse",
    "LLMRouter",
]