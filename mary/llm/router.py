"""
MaryV2 LLM Router

Selects and manages language-model providers.

The router prevents the rest of Mary from needing to know whether a request
is being handled by Groq, OpenAI, or another provider added in the future.
"""

from ..core.config import Config

from .interface import (
    LLMInterface,
    LLMMessage,
    LLMResponse,
)

from .providers.groq import GroqProvider
from .providers.openai import OpenAIProvider


class LLMRouter:
    """
    Routes LLM requests to the configured provider.
    """

    def __init__(
        self,
        config: Config,
    ):
        self.config = config

        self.providers: dict[
            str,
            LLMInterface,
        ] = {}

        self._register_default_providers()

    def _register_default_providers(self):
        """Register the providers currently supported by MaryV2."""

        self.providers["groq"] = GroqProvider(
            model=self.config.llm.model
            if self.config.llm.provider == "groq"
            else "openai/gpt-oss-20b"
        )

        self.providers["openai"] = OpenAIProvider(
            model=(
                self.config.llm.model
                if self.config.llm.provider == "openai"
                else "gpt-4.1-mini"
            )
        )

    def register_provider(
        self,
        name: str,
        provider: LLMInterface,
    ):
        """
        Register a custom LLM provider.

        This allows future providers—including local models—to be added
        without modifying the router's core logic.
        """

        self.providers[name] = provider

    def get_provider(
        self,
        name: str | None = None,
    ) -> LLMInterface:

        provider_name = (
            name
            or self.config.llm.provider
        )

        provider = self.providers.get(
            provider_name
        )

        if provider is None:
            raise ValueError(
                f"Unknown LLM provider: "
                f"{provider_name}"
            )

        return provider

    def generate(
        self,
        messages: list[LLMMessage],
        provider: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """
        Generate a response using the selected provider.
        """

        selected_provider = self.get_provider(
            provider
        )

        return selected_provider.generate(
            messages=messages,
            temperature=(
                temperature
                if temperature is not None
                else self.config.llm.temperature
            ),
            max_tokens=(
                max_tokens
                if max_tokens is not None
                else self.config.llm.max_tokens
            ),
        )

    def is_available(
        self,
        provider: str | None = None,
    ) -> bool:
        """Check whether the selected provider is available."""

        return self.get_provider(
            provider
        ).is_available()

    def provider_name(
        self,
        provider: str | None = None,
    ) -> str:
        """Return the selected provider's name."""

        return self.get_provider(
            provider
        ).provider_name()

    def model_name(
        self,
        provider: str | None = None,
    ) -> str:
        """Return the selected provider's model name."""

        return self.get_provider(
            provider
        ).model_name()