"""MaryV2 LLM Router.

Routes language-model requests through a preferred provider with optional
ordered failover. Providers remain lazy and swappable; Mary depends on the
capability, not on Groq/OpenAI specifically.
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
    """Route generation through configured language-model providers."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.providers: dict[str, LLMInterface] = {}
        self.last_generation_attempts: list[dict[str, str]] = []

    def _create_provider(self, name: str) -> LLMInterface:
        name = str(name).lower().strip()

        if name == "groq":
            from .providers.groq import GroqProvider
            model = (
                self.config.llm.model
                if self.config.llm.provider == "groq"
                else "openai/gpt-oss-20b"
            )
            return GroqProvider(model=model)

        if name == "openai":
            from .providers.openai import OpenAIProvider
            model = (
                self.config.llm.model
                if self.config.llm.provider == "openai"
                else "gpt-4.1-mini"
            )
            return OpenAIProvider(model=model)

        raise ValueError(f"Unknown LLM provider: {name}")

    def register_provider(self, name: str, provider: LLMInterface) -> None:
        self.providers[str(name).lower().strip()] = provider

    def get_provider(self, name: str | None = None) -> LLMInterface:
        provider_name = str(name or self.config.llm.provider).lower().strip()
        provider = self.providers.get(provider_name)
        if provider is None:
            provider = self._create_provider(provider_name)
            self.providers[provider_name] = provider
        return provider

    def _provider_order(self, requested: str | None) -> list[str]:
        first = str(requested or self.config.llm.provider).lower().strip()
        order = [first]
        for item in self.config.llm.fallback_providers:
            name = str(item).lower().strip()
            if name and name not in order:
                order.append(name)
        return order

    def _normalize_error(self, exc: Exception, provider_name: str) -> LLMProviderError:
        if isinstance(exc, LLMProviderError):
            return exc

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
            return LLMRateLimitError(message, provider=provider_name)

        return LLMProviderError(
            message,
            provider=provider_name,
            retryable=False,
        )

    def generate(
        self,
        messages: list[LLMMessage],
        provider: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Generate through the first healthy provider in the configured order."""

        self.last_generation_attempts = []
        last_error: LLMProviderError | None = None

        for provider_name in self._provider_order(provider):
            try:
                selected = self.get_provider(provider_name)
            except Exception as exc:
                error = self._normalize_error(exc, provider_name)
                self.last_generation_attempts.append({
                    "provider": provider_name,
                    "status": "unavailable",
                    "error": str(error),
                })
                last_error = error
                continue

            try:
                available = selected.is_available()
            except Exception:
                available = True

            if not available:
                self.last_generation_attempts.append({
                    "provider": provider_name,
                    "status": "not_configured",
                    "error": "provider is not configured/available",
                })
                continue

            try:
                response = selected.generate(
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
            except Exception as exc:
                error = self._normalize_error(exc, provider_name)
                self.last_generation_attempts.append({
                    "provider": provider_name,
                    "status": "failed",
                    "error": str(error),
                })
                last_error = error
                continue

            self.last_generation_attempts.append({
                "provider": provider_name,
                "status": "success",
                "error": "",
            })
            return response

        if last_error is not None:
            raise last_error

        primary = self.provider_name(provider)
        raise LLMProviderError(
            "No configured language-model provider is currently available.",
            provider=primary,
            retryable=True,
        )

    def is_available(self, provider: str | None = None) -> bool:
        if provider is not None:
            try:
                return self.get_provider(provider).is_available()
            except Exception:
                return False
        return any(
            self._provider_available(name)
            for name in self._provider_order(None)
        )

    def _provider_available(self, name: str) -> bool:
        try:
            return bool(self.get_provider(name).is_available())
        except Exception:
            return False

    def provider_name(self, provider: str | None = None) -> str:
        return str(provider or self.config.llm.provider).lower().strip()

    def model_name(self, provider: str | None = None) -> str:
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
