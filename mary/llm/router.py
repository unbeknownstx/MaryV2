"""
MaryV2 LLM Router

Routes language-model requests to the configured provider.

Providers are loaded lazily so importing and initializing Mary does not
require every provider SDK to be installed.
"""

from __future__ import annotations

from mary.core.config import Config

from .interface import (
    LLMInterface,
    LLMMessage,
    LLMResponse,
    LLMProviderError,
    LLMRateLimitError,
)


class LLMRouter:
    """
    Routes LLM requests to the configured provider.

    Provider SDKs are intentionally imported only when the provider
    is actually needed.
    """

    def __init__(
        self,
        config: Config,
    ) -> None:

        self.config = config

        self.providers: dict[
            str,
            LLMInterface,
        ] = {}

    # ============================================================
    # PROVIDERS
    # ============================================================

    def _create_provider(
        self,
        name: str,
    ) -> LLMInterface:
        """
        Create a provider only when it is actually requested.
        """

        if name == "groq":

            from .providers.groq import GroqProvider

            model = (
                self.config.llm.model
                if self.config.llm.provider == "groq"
                else "openai/gpt-oss-20b"
            )

            return GroqProvider(
                model=model,
            )

        if name == "openai":

            from .providers.openai import OpenAIProvider

            model = (
                self.config.llm.model
                if self.config.llm.provider == "openai"
                else "gpt-4.1-mini"
            )

            return OpenAIProvider(
                model=model,
            )

        raise ValueError(
            f"Unknown LLM provider: {name}"
        )

    def register_provider(
        self,
        name: str,
        provider: LLMInterface,
    ) -> None:
        """
        Register a custom provider.
        """

        self.providers[name] = provider

    def get_provider(
        self,
        name: str | None = None,
    ) -> LLMInterface:
        """
        Return the requested provider.

        The provider is created lazily if it has not already
        been registered.
        """

        provider_name = (
            name
            or self.config.llm.provider
        )

        provider = self.providers.get(
            provider_name
        )

        if provider is None:

            provider = self._create_provider(
                provider_name
            )

            self.providers[
                provider_name
            ] = provider

        return provider

    # ============================================================
    # GENERATION
    # ============================================================

    def generate(
        self,
        messages: list[LLMMessage],
        provider: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """
        Generate a response using the selected provider.

        This is the point where the actual provider is loaded.
        """

        selected_provider = self.get_provider(
            provider
        )

        provider_name = self.provider_name(provider)

        try:
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
        except LLMProviderError:
            raise
        except Exception as exc:
            message = str(exc)
            lowered = message.lower()
            status_code = getattr(exc, "status_code", None)

            if (
                status_code == 429
                or "rate limit" in lowered
                or "rate_limit_exceeded" in lowered
                or "tokens per day" in lowered
                or " tpd" in lowered
            ):
                raise LLMRateLimitError(
                    message,
                    provider=provider_name,
                ) from exc

            raise LLMProviderError(
                message,
                provider=provider_name,
                retryable=False,
            ) from exc

    # ============================================================
    # STATUS
    # ============================================================

    def is_available(
        self,
        provider: str | None = None,
    ) -> bool:
        """
        Check whether the selected provider is available.

        This does require loading the provider because availability
        depends on the provider implementation.
        """

        return self.get_provider(
            provider
        ).is_available()

    def provider_name(
        self,
        provider: str | None = None,
    ) -> str:
        """
        Return the configured provider name without loading
        the provider SDK.
        """

        return (
            provider
            or self.config.llm.provider
        )

    def model_name(
        self,
        provider: str | None = None,
    ) -> str:
        """
        Return the configured model name without loading
        the provider SDK.
        """

        if provider == "groq":

            return (
                self.config.llm.model
                if self.config.llm.provider == "groq"
                else "openai/gpt-oss-20b"
            )

        if provider == "openai":

            return (
                self.config.llm.model
                if self.config.llm.provider == "openai"
                else "gpt-4.1-mini"
            )

        return self.config.llm.model