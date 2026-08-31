"""MaryV2 LLM Router.

Routes language-model requests through Mary's configured provider strategy.

The default task/general strategy is ``free_first``:

    Groq -> Gemini -> OpenRouter free -> Ollama

Ordinary personal/character conversation uses a separately configurable
purpose route. The current Windows profile may prefer cloud-first latency while
private/offline turns still force Ollama.

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
from mary.runtime.turn_observability import (
    classify_failure,
    observe_turn_stage,
    record_turn_stage,
)

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

_CONVERSATION_PURPOSES = {
    "conversation",
    "character",
    "relational",
    "self",
    "conversation_fast",
    "social_instant",
}


class LLMRouter:
    """Route generation through Mary's configured language-model providers."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.providers: dict[str, LLMInterface] = {}
        self._purpose_providers: dict[tuple[str, str], LLMInterface] = {}
        # Preserve the long-standing public attempt record shape for callers
        # and tests. Timing is carried in a parallel display-safe structure so
        # instrumentation does not silently break routing consumers.
        self.last_generation_attempts: list[dict[str, str]] = []
        self.last_generation_attempt_timings: list[dict[str, Any]] = []
        self.last_generation_route: dict[str, Any] = {}
        self.resource_governor = ResourceGovernor(config.governance)

        # Process-local conversational routing override. This is intentionally
        # ephemeral: the creator may temporarily force local/private or one of
        # Mary's free providers without changing durable configuration. Explicit
        # per-call provider/route arguments always take precedence.
        self._session_provider_override: str | None = None
        self._session_route_override: str | None = None

        # Provider name -> monotonic time when the local cooldown expires.
        self._rate_limit_until: dict[str, float] = {}

    # ============================================================
    # PROVIDERS
    # ============================================================

    def _create_provider(self, name: str, *, purpose: str | None = None) -> LLMInterface:
        name = str(name).lower().strip()
        purpose_name = str(purpose or "").lower().strip()

        if name == "groq":
            from .providers.groq import GroqProvider

            model = self._groq_model_for_purpose(
                purpose_name,
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

            if purpose_name in {"conversation_fast", "social_instant"}:
                fast_model = os.getenv("MARY_OLLAMA_CONVERSATION_MODEL", "").strip()
                return OllamaProvider(model=fast_model or None)
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

    def _groq_model_for_purpose(
        self,
        purpose: str | None = None,
    ) -> str:
        """Resolve Groq model overrides consistently across every route.

        ``MARY_GROQ_MODEL`` is the provider-specific source of truth. The
        older ``MARY_LLM_MODEL``/``config.llm.model`` remains a compatibility
        fallback when Groq is the configured primary provider.

        Fast/social conversation may still use its own explicit
        ``MARY_GROQ_CONVERSATION_MODEL``. When that override is absent, an
        explicit ``MARY_GROQ_MODEL`` now carries through to conversation too
        instead of being silently ignored.
        """

        purpose_name = str(purpose or "").lower().strip()
        provider_specific = os.getenv(
            "MARY_GROQ_MODEL",
            "",
        ).strip()

        legacy_primary = ""
        if str(self.config.llm.provider).lower().strip() == "groq":
            legacy_primary = str(
                self.config.llm.model
                or ""
            ).strip()

        if purpose_name in {"conversation_fast", "social_instant"}:
            conversation_specific = os.getenv(
                "MARY_GROQ_CONVERSATION_MODEL",
                "",
            ).strip()
            return (
                conversation_specific
                or provider_specific
                or legacy_primary
                or "openai/gpt-oss-20b"
            )

        return (
            provider_specific
            or legacy_primary
            or "openai/gpt-oss-20b"
        )

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

    def _get_provider_for_purpose(self, name: str, purpose: str | None) -> LLMInterface:
        """Return a provider instance whose model may be purpose-specific.

        Registered providers keep priority so tests/custom integrations retain
        the long-standing public override behavior.
        """
        provider_name = str(name).lower().strip()
        registered = self.providers.get(provider_name)
        if registered is not None:
            purpose_adapter = getattr(registered, "for_purpose", None)
            if callable(purpose_adapter):
                return purpose_adapter(purpose)
            return registered
        purpose_name = str(purpose or "").lower().strip()
        if purpose_name not in {"conversation_fast", "social_instant"} or provider_name not in {"groq", "ollama"}:
            return self.get_provider(provider_name)
        key = (provider_name, "conversation_fast")
        provider = self._purpose_providers.get(key)
        if provider is None:
            provider = self._create_provider(provider_name, purpose="conversation_fast")
            self._purpose_providers[key] = provider
        return provider

    # ============================================================
    # ROUTING
    # ============================================================

    def set_session_override(
        self,
        *,
        provider: str | None = None,
        route: str | None = None,
    ) -> dict[str, str | None]:
        """Set a process-local routing override for ordinary generation.

        Paid OpenAI is deliberately excluded from sticky overrides. It remains
        task-authorized through the expert route.
        """

        normalized_provider = str(provider or "").strip().lower() or None
        normalized_route = str(route or "").strip().lower() or None

        if normalized_route is not None and normalized_route not in {
            "private", "local", "offline",
        }:
            raise ValueError(f"Unsupported session route override: {normalized_route}")

        if normalized_provider is not None:
            if normalized_provider == "openai":
                raise ValueError(
                    "Paid OpenAI cannot be enabled as a sticky session override; "
                    "use explicit expert authorization for an individual task."
                )
            if normalized_provider not in {"groq", "gemini", "openrouter", "ollama"}:
                raise ValueError(f"Unsupported session provider override: {normalized_provider}")

        self._session_provider_override = normalized_provider
        self._session_route_override = normalized_route
        return self.session_override_status()

    def clear_session_override(self) -> dict[str, str | None]:
        """Return ordinary generation to Mary's configured strategy."""

        self._session_provider_override = None
        self._session_route_override = None
        return self.session_override_status()

    def session_override_status(self) -> dict[str, str | None]:
        return {
            "provider": self._session_provider_override,
            "route": self._session_route_override,
        }

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


    def _conversation_provider_order(self) -> list[str]:
        """Return Mary's configured free-provider order for character conversation.

        This route is independent from task/general routing. A creator can use a
        cloud-first profile for low latency or an Ollama-first profile for local
        privacy; paid OpenAI is never injected into this route automatically.
        """

        configured = list(
            getattr(
                self.config.llm,
                "conversation_provider_order",
                ["ollama", "groq", "gemini", "openrouter"],
            )
        )

        order: list[str] = []
        for item in configured:
            name = str(item).lower().strip()
            if name in _FREE_PROVIDER_NAMES and name not in order:
                order.append(name)

        if "ollama" not in order:
            order.insert(0, "ollama")

        # Conversation may fall back to Mary's normal free pool, but paid OpenAI
        # is never introduced by this purpose route.
        for name in self._free_provider_order():
            if name not in order:
                order.append(name)

        return order

    def _provider_order(
        self,
        requested: str | None,
        *,
        route: str | None = None,
        purpose: str | None = None,
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
        # silently removed by the built-in free-provider allowlist or by Mary's
        # independently configured conversation policy.
        primary = str(
            self.config.llm.provider
        ).lower().strip()
        purpose_name = str(purpose or "").lower().strip()
        if (
            purpose_name in _CONVERSATION_PURPOSES
            and primary in {"groq", "gemini", "openrouter", "ollama", "openai"}
        ):
            return self._conversation_provider_order()
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

    def conversation_provider_order(self) -> list[str]:
        """Return the configured free-provider order for Mary character conversation."""

        return self._provider_order(None, purpose="conversation")

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
        purpose: str | None = None,
    ) -> LLMResponse:
        """Generate through the first healthy provider in Mary's route."""

        self.last_generation_attempts = []
        self.last_generation_attempt_timings = []
        last_error: LLMProviderError | None = None

        effective_provider = provider
        effective_route = route
        effective_purpose = purpose
        if effective_provider is None and effective_route is None:
            if self._session_provider_override is not None or self._session_route_override is not None:
                effective_provider = self._session_provider_override
                effective_route = self._session_route_override
                effective_purpose = None

        order = self.resource_governor.provider_order(
            self._provider_order(
                effective_provider,
                route=effective_route,
                purpose=effective_purpose,
            )
        )
        self.last_generation_route = {
            "requested_provider": effective_provider,
            "route": effective_route,
            "purpose": effective_purpose,
            "strategy": self.routing_strategy(),
            "order": list(order),
            "selected_provider": None,
            "selected_model": None,
            "status": "routing",
        }
        self.resource_governor.record_generation_start(
            route=str(
                effective_route
                or effective_provider
                or effective_purpose
                or self.routing_strategy()
            ),
            order=order,
        )

        fallback_recorded = False
        for attempt_number, provider_name in enumerate(order, start=1):
            attempt_started = time.monotonic()
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
                self.last_generation_attempt_timings.append({
                    "provider": provider_name,
                    "status": "cooldown",
                    "elapsed_ms": round((time.monotonic() - attempt_started) * 1000.0, 2),
                })
                self.resource_governor.record_attempt(provider_name, "cooldown")
                record_turn_stage(
                    "provider_availability",
                    status="skipped",
                    elapsed_ms=(time.monotonic() - attempt_started) * 1000.0,
                    provider=provider_name,
                    attempt=attempt_number,
                    outcome="cooldown",
                )
                record_turn_stage(
                    "provider_fallback",
                    status="success",
                    elapsed_ms=0.0,
                    provider=provider_name,
                    attempt=attempt_number,
                    outcome="cooldown",
                )
                fallback_recorded = True
                continue

            try:
                with observe_turn_stage(
                    "provider_availability",
                    provider=provider_name,
                    attempt=attempt_number,
                    failure_kind="provider_error",
                ):
                    selected = self._get_provider_for_purpose(provider_name, effective_purpose)
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
                self.last_generation_attempt_timings.append({
                    "provider": provider_name,
                    "status": "unavailable",
                    "elapsed_ms": round((time.monotonic() - attempt_started) * 1000.0, 2),
                })
                self.resource_governor.record_attempt(provider_name, "unavailable")
                record_turn_stage(
                    "provider_fallback",
                    status="success",
                    elapsed_ms=0.0,
                    provider=provider_name,
                    attempt=attempt_number,
                    outcome="unavailable",
                )
                fallback_recorded = True
                continue

            if not available:
                self.last_generation_attempts.append({
                    "provider": provider_name,
                    "status": "not_configured",
                    "error": (
                        "provider is not configured/available"
                    ),
                })
                self.last_generation_attempt_timings.append({
                    "provider": provider_name,
                    "status": "not_configured",
                    "elapsed_ms": round((time.monotonic() - attempt_started) * 1000.0, 2),
                })
                self.resource_governor.record_attempt(provider_name, "not_configured")
                record_turn_stage(
                    "provider_fallback",
                    status="success",
                    elapsed_ms=0.0,
                    provider=provider_name,
                    attempt=attempt_number,
                    outcome="not_configured",
                )
                fallback_recorded = True
                continue

            provider_call_started = time.monotonic()
            try:
                with observe_turn_stage(
                    "provider_generation",
                    provider=provider_name,
                    attempt=attempt_number,
                    failure_kind="provider_error",
                ):
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
                provider_call_ms = round((time.monotonic() - provider_call_started) * 1000.0, 2)
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
                self.last_generation_attempt_timings.append({
                    "provider": provider_name,
                    "status": "failed",
                    "call_ms": provider_call_ms,
                    "elapsed_ms": round((time.monotonic() - attempt_started) * 1000.0, 2),
                })
                last_error = error
                self.resource_governor.record_attempt(provider_name, "failed")
                record_turn_stage(
                    "provider_fallback",
                    status="success",
                    elapsed_ms=0.0,
                    provider=provider_name,
                    attempt=attempt_number,
                    outcome=classify_failure(exc, default="provider_error"),
                )
                fallback_recorded = True
                continue

            provider_call_ms = round((time.monotonic() - provider_call_started) * 1000.0, 2)
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
                self.last_generation_attempt_timings.append({
                    "provider": provider_name,
                    "status": "invalid_output",
                    "call_ms": provider_call_ms,
                    "elapsed_ms": round((time.monotonic() - attempt_started) * 1000.0, 2),
                })
                last_error = error
                self.resource_governor.record_attempt(provider_name, "invalid_output")
                record_turn_stage(
                    "provider_fallback",
                    status="success",
                    elapsed_ms=0.0,
                    provider=provider_name,
                    attempt=attempt_number,
                    outcome="invalid_output",
                )
                fallback_recorded = True
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
                self.last_generation_attempt_timings.append({
                    "provider": provider_name,
                    "status": "incomplete",
                    "call_ms": provider_call_ms,
                    "elapsed_ms": round((time.monotonic() - attempt_started) * 1000.0, 2),
                })
                last_error = error
                self.resource_governor.record_attempt(provider_name, "incomplete")
                record_turn_stage(
                    "provider_fallback",
                    status="success",
                    elapsed_ms=0.0,
                    provider=provider_name,
                    attempt=attempt_number,
                    outcome="incomplete",
                )
                fallback_recorded = True
                continue

            self.clear_provider_cooldown(
                provider_name
            )
            self.last_generation_attempts.append({
                "provider": provider_name,
                "status": "success",
                "error": "",
            })
            self.last_generation_attempt_timings.append({
                "provider": provider_name,
                "status": "success",
                "call_ms": provider_call_ms,
                "elapsed_ms": round((time.monotonic() - attempt_started) * 1000.0, 2),
            })
            self.resource_governor.record_attempt(provider_name, "success")
            self.resource_governor.record_usage(response.usage)
            self.last_generation_route.update({
                "selected_provider": provider_name,
                "selected_model": str(response.model or selected.model_name()),
                "status": "success",
            })
            if not fallback_recorded:
                record_turn_stage(
                    "provider_fallback",
                    status="skipped",
                    elapsed_ms=0.0,
                    provider=provider_name,
                    attempt=attempt_number,
                    outcome="not_needed",
                )
            return response

        if last_error is not None:
            self.last_generation_route["status"] = "failed"
            record_turn_stage(
                "provider_fallback",
                status="failure",
                elapsed_ms=0.0,
                provider=getattr(last_error, "provider", None),
                attempt=max(1, len(order)),
                outcome="exhausted",
                failure_kind="provider_exhausted",
                error=last_error,
            )
            raise last_error

        primary = (
            order[0]
            if order
            else self.provider_name(effective_provider)
        )
        error = LLMProviderError(
            "No configured language-model provider is currently available.",
            provider=primary,
            retryable=True,
        )
        record_turn_stage(
            "provider_fallback",
            status="failure",
            elapsed_ms=0.0,
            provider=primary,
            attempt=max(1, len(order)),
            outcome="exhausted",
            failure_kind="provider_exhausted",
            error=error,
        )
        raise error

    # ============================================================
    # STATUS
    # ============================================================


    def routing_status(self) -> dict[str, Any]:
        """Return display-safe truth about Mary's current model routing fabric.

        This is observability only. It does not authorize provider use, mutate
        provider order, contact a provider, or promote a capability node into an
        identity/state owner. Availability checks are local/configuration checks.
        """

        routes = {
            "general": self._provider_order(None),
            "conversation": self._provider_order(None, purpose="conversation"),
            "private": self._provider_order(None, route="private"),
            "expert": self._provider_order(None, route="expert"),
        }
        names: list[str] = []
        for order in routes.values():
            for name in order:
                if name not in names:
                    names.append(name)

        providers: list[dict[str, Any]] = []
        for name in names:
            remaining = self._cooldown_remaining(name)
            available = False
            model = None
            source = "configured_host"
            try:
                selected = self._get_provider_for_purpose(name, "conversation")
                available = bool(selected.is_available()) and remaining <= 0.0
                model = str(selected.model_name() or "") or None
                if selected.__class__.__name__ == "DeviceOllamaProvider":
                    source = "capability_node"
            except Exception:
                available = False
            providers.append({
                "provider": name,
                "available": available,
                "model": model,
                "source": source,
                "cooldown_seconds": round(remaining, 2),
            })

        return {
            "strategy": self.routing_strategy(),
            "session_override": self.session_override_status(),
            "routes": routes,
            "providers": providers,
            "last_generation": {
                **dict(self.last_generation_route),
                "attempts": [dict(item) for item in self.last_generation_attempts],
                "timings": [dict(item) for item in self.last_generation_attempt_timings],
            },
            "policy": (
                "Models and capability nodes are replaceable execution engines; "
                "Mary Core remains the identity/state authority."
            ),
        }

    def is_available(
        self,
        provider: str | None = None,
        *,
        route: str | None = None,
        purpose: str | None = None,
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
                purpose=purpose,
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
            return self._groq_model_for_purpose()
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
