"""MaryV2 LLM Router.

Routes language-model requests through Mary's configured provider strategy.

The default strategy is ``free_first``:

    Groq -> Gemini -> OpenRouter free -> Ollama

Configured cloud providers are skipped when their API key is absent. A
provider that returns a rate-limit response is placed on a short local
cooldown so Mary can immediately use the next free route instead of retrying
the same exhausted provider on every turn.

Explicit provider requests still work, and ``route=\"private\"`` forces local
Ollama without sending the prompt to a cloud provider.
"""

from __future__ import annotations

import os
import time
from typing import Any

from mary.core.config import Config
from mary.governance.resource import ResourceGovernor

from .output_quality import inspect_output_quality

from .interface import (
    LLMInterface,
    LLMMessage,
    LLMResponse,
    LLMProviderError,
    LLMRateLimitError,
)


_FREE_PROVIDER_NAMES = (
    "groq",
    "gemini",
    "openrouter",
    "ollama",
)

_PRIVATE_ROUTES = {
    "private",
    "local",
    "offline",
}

_EXPERT_ROUTES = {
    "expert",
    "paid",
    "openai",
}


class LLMRouter:
    """Route generation through Mary's configured language-model providers."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.providers: dict[str, LLMInterface] = {}
        self.last_generation_attempts: list[dict[str, str]] = []
        self.resource_governor = ResourceGovernor(config.governance)

        # Provider name -> monotonic time when the local cooldown expires.
        self._rate_limit_until: dict[str, float] = {}

    # ============================================================
    # PROVIDERS
    # ============================================================

    def _create_provider(self, name: str) -> LLMInterface:
        name = str(name).lower().strip()

        if name == "groq":
            from .providers.groq import GroqProvider

            model = (
                self.config.llm.model
                if self.config.llm.provider == "groq"
                else os.getenv(
                    "MARY_GROQ_MODEL",
                    "openai/gpt-oss-20b",
                )
            )
            return GroqProvider(model=model)

        if name == "gemini":
            from .providers.gemini import GeminiProvider

            return GeminiProvider()

        if name == "openrouter":
            from .providers.openrouter import OpenRouterProvider

            model = os.getenv(
                "MARY_OPENROUTER_MODEL",
                "openrouter/free",
            ).strip()

            # Free-first mode must never silently turn an OpenRouter fallback
            # into a paid model because an old environment variable happens to
            # contain a paid model ID. Specific ``:free`` models remain valid.
            if self.routing_strategy() == "free_first":
                if (
                    model != "openrouter/free"
                    and not model.endswith(":free")
                ):
                    model = "openrouter/free"

            return OpenRouterProvider(model=model)

        if name == "ollama":
            from .providers.ollama import OllamaProvider

            return OllamaProvider()

        if name == "openai":
            from .providers.openai import OpenAIProvider

            model = str(
                getattr(
                    self.config.llm,
                    "openai_model",
                    "gpt-5.6-luna",
                )
            ).strip() or "gpt-5.6-luna"
            reasoning_effort = str(
                getattr(
                    self.config.llm,
                    "openai_reasoning_effort",
                    "low",
                )
            ).strip().lower() or "low"
            return OpenAIProvider(
                model=model,
                reasoning_effort=reasoning_effort,
            )

        raise ValueError(f"Unknown LLM provider: {name}")

    def register_provider(
        self,
        name: str,
        provider: LLMInterface,
    ) -> None:
        self.providers[str(name).lower().strip()] = provider

    def get_provider(
        self,
        name: str | None = None,
    ) -> LLMInterface:
        provider_name = str(
            name or self.config.llm.provider
        ).lower().strip()

        provider = self.providers.get(provider_name)
        if provider is None:
            provider = self._create_provider(provider_name)
            self.providers[provider_name] = provider

        return provider

    # ============================================================
    # ROUTING
    # ============================================================

    def routing_strategy(self) -> str:
        """Return Mary's active LLM routing strategy."""

        strategy = str(
            getattr(
                self.config.llm,
                "routing_strategy",
                "configured",
            )
        ).lower().strip()

        if strategy not in {
            "configured",
            "free_first",
        }:
            return "configured"

        return strategy

    def _configured_provider_order(
        self,
        requested: str | None,
    ) -> list[str]:
        first = str(
            requested or self.config.llm.provider
        ).lower().strip()

        order = [first]
        for item in self.config.llm.fallback_providers:
            name = str(item).lower().strip()
            if name and name not in order:
                order.append(name)

        return order

    def _free_provider_order(self) -> list[str]:
        configured = list(
            getattr(
                self.config.llm,
                "free_provider_order",
                list(_FREE_PROVIDER_NAMES),
            )
        )

        order: list[str] = []

        for item in configured:
            name = str(item).lower().strip()
            if (
                name in _FREE_PROVIDER_NAMES
                and name not in order
            ):
                order.append(name)

        # Preserve any explicitly configured *free* fallback providers while
        # intentionally excluding OpenAI/other paid routes in free-first mode.
        primary = str(
            self.config.llm.provider
        ).lower().strip()

        if (
            primary in _FREE_PROVIDER_NAMES
            and primary not in order
        ):
            order.append(primary)

        for item in self.config.llm.fallback_providers:
            name = str(item).lower().strip()
            if (
                name in _FREE_PROVIDER_NAMES
                and name not in order
            ):
                order.append(name)

        # Ollama is Mary's zero-cost local safety net. If the user omitted it
        # from an otherwise valid free order, retain it as the final fallback.
        if "ollama" not in order:
            order.append("ollama")

        return order

    def _provider_order(
        self,
        requested: str | None,
        *,
        route: str | None = None,
    ) -> list[str]:
        route_name = str(route or "").lower().strip()

        if route_name in _PRIVATE_ROUTES:
            return ["ollama"]

        if route_name in _EXPERT_ROUTES:
            expert_provider = str(
                getattr(
                    self.config.llm,
                    "expert_provider",
                    "openai",
                )
            ).lower().strip() or "openai"
            return [expert_provider]

        # An explicit provider is an intentional override. Preserve the old
        # provider + configured-fallback behavior for callers that request it.
        if requested is not None:
            return self._configured_provider_order(requested)

        strategy = self.routing_strategy()

        # Custom/test providers should retain legacy behavior rather than being
        # silently removed by the built-in free-provider allowlist.
        primary = str(
            self.config.llm.provider
        ).lower().strip()
        if (
            strategy == "free_first"
            and primary in {
                "groq",
                "gemini",
                "openrouter",
                "ollama",
                "openai",
            }
        ):
            return self._free_provider_order()

        return self._configured_provider_order(None)

    # ============================================================
    # RATE-LIMIT COOLDOWN
    # ============================================================

    def _default_rate_limit_cooldown(self) -> float:
        try:
            return max(
                0.0,
                float(
                    getattr(
                        self.config.llm,
                        "rate_limit_cooldown_seconds",
                        300.0,
                    )
                ),
            )
        except (TypeError, ValueError):
            return 300.0

    @staticmethod
    def _retry_after_seconds(exc: Exception) -> float | None:
        """Extract Retry-After when an SDK exposes the provider headers."""

        candidates: list[Any] = []

        response = getattr(exc, "response", None)
        if response is not None:
            candidates.append(getattr(response, "headers", None))

        candidates.append(getattr(exc, "headers", None))

        for headers in candidates:
            if not headers:
                continue

            value = None
            try:
                value = headers.get("retry-after")
                if value is None:
                    value = headers.get("Retry-After")
            except Exception:
                value = None

            if value is None:
                continue

            try:
                return max(0.0, float(value))
            except (TypeError, ValueError):
                continue

        return None

    def _set_rate_limit_cooldown(
        self,
        provider_name: str,
        exc: Exception,
    ) -> None:
        seconds = self._retry_after_seconds(exc)
        if seconds is None:
            seconds = self._default_rate_limit_cooldown()

        self._rate_limit_until[provider_name] = (
            time.monotonic() + seconds
        )

    def _cooldown_remaining(
        self,
        provider_name: str,
    ) -> float:
        until = self._rate_limit_until.get(provider_name)
        if until is None:
            return 0.0

        remaining = until - time.monotonic()
        if remaining <= 0.0:
            self._rate_limit_until.pop(
                provider_name,
                None,
            )
            return 0.0

        return remaining

    def clear_provider_cooldown(
        self,
        provider_name: str | None = None,
    ) -> None:
        """Clear one or all local rate-limit cooldowns."""

        if provider_name is None:
            self._rate_limit_until.clear()
            return

        self._rate_limit_until.pop(
            str(provider_name).lower().strip(),
            None,
        )

    # ============================================================
    # ERRORS
    # ============================================================

    def _normalize_error(
        self,
        exc: Exception,
        provider_name: str,
    ) -> LLMProviderError:
        if isinstance(exc, LLMProviderError):
            return exc

        message = str(exc)
        lowered = message.lower()
        status_code = getattr(exc, "status_code", None)

        # A provider can report a token-budget problem with rate-limit wording
        # while using HTTP 413. That is a property of this request, not evidence
        # that the provider itself is exhausted, so do not place it on cooldown.
        if (
            status_code == 413
            or "request too large" in lowered
            or "payload too large" in lowered
            or "context length exceeded" in lowered
        ):
            return LLMProviderError(
                message,
                provider=provider_name,
                retryable=False,
            )

        if (
            status_code == 429
            or "rate limit" in lowered
            or "rate_limit_exceeded" in lowered
            or "tokens per day" in lowered
            or "resource_exhausted" in lowered
            or "quota exceeded" in lowered
            or " tpd" in lowered
        ):
            return LLMRateLimitError(
                message,
                provider=provider_name,
            )

        return LLMProviderError(
            message,
            provider=provider_name,
            retryable=False,
        )

    # ============================================================
    # GENERATION
    # ============================================================

    def generate(
        self,
        messages: list[LLMMessage],
        provider: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        route: str | None = None,
    ) -> LLMResponse:
        """Generate through the first healthy provider in Mary's route."""

        self.last_generation_attempts = []
        last_error: LLMProviderError | None = None
        order = self.resource_governor.provider_order(
            self._provider_order(provider, route=route)
        )
        self.resource_governor.record_generation_start(
            route=str(route or self.routing_strategy()),
            order=order,
        )

        for provider_name in order:
            cooldown = self._cooldown_remaining(
                provider_name
            )
            if cooldown > 0.0:
                self.last_generation_attempts.append({
                    "provider": provider_name,
                    "status": "cooldown",
                    "error": (
                        "rate-limit cooldown active "
                        f"({cooldown:.0f}s remaining)"
                    ),
                })
                self.resource_governor.record_attempt(provider_name, "cooldown")
                continue

            try:
                selected = self.get_provider(provider_name)
            except Exception as exc:
                error = self._normalize_error(
                    exc,
                    provider_name,
                )
                self.last_generation_attempts.append({
                    "provider": provider_name,
                    "status": "unavailable",
                    "error": str(error),
                })
                last_error = error
                self.resource_governor.record_attempt(provider_name, "unavailable")
                continue

            try:
                available = selected.is_available()
            except Exception as exc:
                error = self._normalize_error(
                    exc,
                    provider_name,
                )
                self.last_generation_attempts.append({
                    "provider": provider_name,
                    "status": "unavailable",
                    "error": str(error),
                })
                last_error = error
                self.resource_governor.record_attempt(provider_name, "unavailable")
                continue

            if not available:
                self.last_generation_attempts.append({
                    "provider": provider_name,
                    "status": "not_configured",
                    "error": (
                        "provider is not configured/available"
                    ),
                })
                self.resource_governor.record_attempt(provider_name, "not_configured")
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
                error = self._normalize_error(
                    exc,
                    provider_name,
                )

                if isinstance(
                    error,
                    LLMRateLimitError,
                ):
                    self._set_rate_limit_cooldown(
                        provider_name,
                        exc,
                    )

                self.last_generation_attempts.append({
                    "provider": provider_name,
                    "status": "failed",
                    "error": str(error),
                })
                last_error = error
                self.resource_governor.record_attempt(provider_name, "failed")
                continue

            quality_issue = inspect_output_quality(
                response.content,
                messages,
            )
            if quality_issue is not None:
                error = LLMProviderError(
                    quality_issue.description,
                    provider=provider_name,
                    retryable=True,
                )
                self.last_generation_attempts.append({
                    "provider": provider_name,
                    "status": "invalid_output",
                    "error": f"{quality_issue.code}: {quality_issue.description}",
                })
                last_error = error
                self.resource_governor.record_attempt(provider_name, "invalid_output")
                continue

            finish_reason = str(
                response.finish_reason or ""
            ).strip().lower()
            if finish_reason in {
                "length",
                "max_tokens",
                "max_output_tokens",
            }:
                error = LLMProviderError(
                    (
                        "Provider returned an incomplete response because "
                        "its output limit was reached."
                    ),
                    provider=provider_name,
                    retryable=True,
                )
                self.last_generation_attempts.append({
                    "provider": provider_name,
                    "status": "incomplete",
                    "error": str(error),
                })
                last_error = error
                self.resource_governor.record_attempt(provider_name, "incomplete")
                continue

            self.clear_provider_cooldown(
                provider_name
            )
            self.last_generation_attempts.append({
                "provider": provider_name,
                "status": "success",
                "error": "",
            })
            self.resource_governor.record_attempt(provider_name, "success")
            self.resource_governor.record_usage(response.usage)
            return response

        if last_error is not None:
            raise last_error

        primary = self.provider_name(provider)
        raise LLMProviderError(
            "No configured language-model provider is currently available.",
            provider=primary,
            retryable=True,
        )

    # ============================================================
    # STATUS
    # ============================================================

    def is_available(
        self,
        provider: str | None = None,
        *,
        route: str | None = None,
    ) -> bool:
        if provider is not None:
            try:
                return self.get_provider(provider).is_available()
            except Exception:
                return False

        return any(
            self._provider_available(name)
            for name in self._provider_order(
                None,
                route=route,
            )
            if self._cooldown_remaining(name) <= 0.0
        )

    def _provider_available(self, name: str) -> bool:
        try:
            return bool(
                self.get_provider(name).is_available()
            )
        except Exception:
            return False

    def provider_name(
        self,
        provider: str | None = None,
    ) -> str:
        return str(
            provider or self.config.llm.provider
        ).lower().strip()

    def model_name(
        self,
        provider: str | None = None,
    ) -> str:
        provider_name = self.provider_name(provider)

        if provider_name == "groq":
            return (
                self.config.llm.model
                if self.config.llm.provider == "groq"
                else os.getenv(
                    "MARY_GROQ_MODEL",
                    "openai/gpt-oss-20b",
                )
            )
        if provider_name == "gemini":
            return self.get_provider("gemini").model_name()
        if provider_name == "openrouter":
            return self.get_provider("openrouter").model_name()
        if provider_name == "ollama":
            return self.get_provider("ollama").model_name()
        if provider_name == "openai":
            return str(
                getattr(
                    self.config.llm,
                    "openai_model",
                    "gpt-5.6-luna",
                )
            ).strip() or "gpt-5.6-luna"
        return self.config.llm.model
