"""MaryV2 OpenAI provider.

OpenAI is an intentional paid expert route in V2. It is not part of Mary's
``free_first`` conversation chain.

The provider uses OpenAI's Responses API and keeps the SDK import lazy so the
normal deterministic/offline MaryV2 suite does not require network access or
provider SDK initialization.
"""

from __future__ import annotations

import os
from typing import Any

from ..interface import (
    GenerationCost,
    GenerationRequest,
    LLMInterface,
    LLMMessage,
    LLMResponse,
    ProviderRoute,
)


_REASONING_EFFORTS = {
    "none",
    "low",
    "medium",
    "high",
    "xhigh",
    "max",
}


class OpenAIProvider(LLMInterface):
    """Paid OpenAI expert provider backed by the Responses API."""

    def route_capabilities(self) -> ProviderRoute:
        return ProviderRoute(
            cost_class=GenerationCost.PAID_LOW.value,
            deadline_enforced=True,
            fallback_eligible=False,
        )

    def generate_constrained(
        self,
        request: GenerationRequest,
        *,
        timeout_seconds: float | None = None,
    ) -> LLMResponse:
        return self._generate(
            list(request.messages),
            max_tokens=2048 if request.max_tokens is None else request.max_tokens,
            timeout_seconds=timeout_seconds,
        )

    def __init__(
        self,
        model: str = "gpt-5.6-luna",
        api_key: str | None = None,
        *,
        reasoning_effort: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self.model = str(model).strip() or "gpt-5.6-luna"
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")

        requested_effort = str(
            reasoning_effort
            or os.getenv("MARY_OPENAI_REASONING_EFFORT", "low")
        ).strip().lower()
        self.reasoning_effort = (
            requested_effort
            if requested_effort in _REASONING_EFFORTS
            else "low"
        )

        timeout_value = timeout_seconds
        if timeout_value is None:
            try:
                timeout_value = float(
                    os.getenv("MARY_OPENAI_TIMEOUT", "60")
                )
            except ValueError:
                timeout_value = 60.0
        self.timeout_seconds = max(1.0, float(timeout_value))

        self.client: Any | None = None
        self._sdk_error: Exception | None = None

        if self.api_key:
            try:
                from openai import OpenAI

                # Mary owns retry/failover policy at the router boundary. Avoid
                # hidden SDK retries on a paid route and keep latency bounded.
                self.client = OpenAI(
                    api_key=self.api_key,
                    timeout=self.timeout_seconds,
                    max_retries=0,
                )
            except Exception as exc:  # pragma: no cover - exact SDK failure varies
                self._sdk_error = exc
                self.client = None

    @staticmethod
    def _instructions(messages: list[LLMMessage]) -> str | None:
        parts = [
            message.content.strip()
            for message in messages
            if str(message.role).strip().lower() in {"system", "developer"}
            and str(message.content).strip()
        ]
        return "\n\n".join(parts) or None

    @staticmethod
    def _input(messages: list[LLMMessage]) -> list[dict[str, str]]:
        payload: list[dict[str, str]] = []
        for message in messages:
            role = str(message.role).strip().lower()
            content = str(message.content).strip()
            if not content or role in {"system", "developer"}:
                continue
            if role not in {"user", "assistant"}:
                role = "user"
            payload.append({
                "role": role,
                "content": content,
            })
        return payload

    def generate(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        del temperature  # Reasoning-model compatibility: keep sampling provider-owned.
        return self._generate(
            messages,
            max_tokens=max_tokens,
            timeout_seconds=None,
        )

    def _generate(
        self,
        messages: list[LLMMessage],
        *,
        max_tokens: int,
        timeout_seconds: float | None,
    ) -> LLMResponse:

        if not self.api_key:
            raise RuntimeError(
                "OpenAI API key is not configured. Set OPENAI_API_KEY."
            )

        if self.client is None:
            if self._sdk_error is not None:
                raise RuntimeError(
                    "OpenAI SDK is unavailable or failed to initialize: "
                    f"{self._sdk_error}"
                ) from self._sdk_error
            raise RuntimeError("OpenAI client is not available.")

        request: dict[str, Any] = {
            "model": self.model,
            "input": self._input(messages),
            "max_output_tokens": int(max_tokens),
            # Do not create retrievable Responses state for ordinary Mary
            # consultations. The task workspace remains Mary's local record.
            "store": False,
            "reasoning": {
                "effort": self.reasoning_effort,
            },
        }

        instructions = self._instructions(messages)
        if instructions:
            request["instructions"] = instructions

        client = self.client
        if timeout_seconds is not None:
            client = client.with_options(
                timeout=max(0.001, min(self.timeout_seconds, timeout_seconds))
            )
        response = client.responses.create(**request)

        status = str(getattr(response, "status", "") or "").strip().lower()
        finish_reason: str | None
        if status == "completed":
            finish_reason = "stop"
        elif status == "incomplete":
            details = getattr(response, "incomplete_details", None)
            finish_reason = str(
                getattr(details, "reason", None) or "incomplete"
            )
        else:
            finish_reason = status or None

        raw_usage = getattr(response, "usage", None)
        usage: dict[str, Any] = {}
        if raw_usage is not None:
            usage = {
                "prompt_tokens": getattr(raw_usage, "input_tokens", 0),
                "completion_tokens": getattr(raw_usage, "output_tokens", 0),
                "total_tokens": getattr(raw_usage, "total_tokens", 0),
            }

            input_details = getattr(raw_usage, "input_tokens_details", None)
            cached_tokens = getattr(input_details, "cached_tokens", None)
            if cached_tokens is not None:
                usage["cached_tokens"] = cached_tokens

            output_details = getattr(raw_usage, "output_tokens_details", None)
            reasoning_tokens = getattr(output_details, "reasoning_tokens", None)
            if reasoning_tokens is not None:
                usage["reasoning_tokens"] = reasoning_tokens

        return LLMResponse(
            content=str(getattr(response, "output_text", "") or ""),
            provider=self.provider_name(),
            model=self.model,
            finish_reason=finish_reason,
            usage=usage,
            raw=response,
        )

    def is_available(self) -> bool:
        return bool(self.api_key and self.client)

    def provider_name(self) -> str:
        return "openai"

    def model_name(self) -> str:
        return self.model
