"""
MaryV2 - LLM Provider Adapters

Provider-specific implementations for Mary's LLM abstraction.

Current providers:

    - Groq
    - OpenAI

These adapters implement the provider-independent interface defined
in mary.llm.interface.

IMPORTANT
---------

Importing this package does NOT:

    - make an API request
    - automatically load credentials
    - instantiate a provider
    - select a provider
    - grant internet access

Providers must be explicitly created by the application or LLM
router.
"""

from .groq import (
    GroqProvider,
)

from .openai import (
    OpenAIProvider,
)


__all__ = [
    "GroqProvider",
    "OpenAIProvider",
]