"""
MaryV2 - LLM Package

Public interface for Mary's language-model abstraction layer.

The LLM package provides:

    - provider-independent interfaces
    - model routing
    - provider adapters

Supported providers currently include:

    - Groq
    - OpenAI

IMPORTANT
---------

Importing this package does NOT:

    - make an API request
    - create a provider client
    - load API credentials
    - select a provider
    - grant internet/tool access

Providers and routers must be explicitly constructed by the
application.

Cognition should depend on this abstraction rather than directly
depending on a specific provider.
"""

from .interface import (
    LLMMessage,
    LLMRequest,
    LLMResponse,
    LLMUsage,
    LLMProvider,
)

from .router import (
    LLMRouter,
    LLMRouterConfig,
    create_llm_router,
)


__all__ = [
    # Interface
    "LLMMessage",
    "LLMRequest",
    "LLMResponse",
    "LLMUsage",
    "LLMProvider",

    # Router
    "LLMRouter",
    "LLMRouterConfig",
    "create_llm_router",
]