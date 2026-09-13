"""Generic OpenAI-compatible inference provider for MaryV2.

The adapter intentionally owns only transport/model invocation. Mary remains
above it. Named presets cover useful frontier services, while the custom
openai_compatible profile lets a new provider or local compatible server be
tried without another architecture change.
"""
from __future__ import annotations

import json
import os
from typing import Any
from urllib.parse import urlparse

from ..interface import (
    GenerationCost,
    GenerationPrivacy,
    GenerationRequest,
    LLMInterface,
    LLMProviderError,
    LLMResponse,
    ProviderRoute,
)
from ..provider_catalog import ProviderPreset


def _env_prefix(name: str) -> str:
    return str(name or "openai_compatible").upper().replace("-", "_")


def _is_loopback_url(value: str) -> bool:
    try:
        parsed = urlparse(str(value or ""))
    except Exception:
        return False
    return parsed.scheme in {"http", "https"} and (parsed.hostname or "").lower() in {
        "127.0.0.1",
        "localhost",
        "::1",
    }


class OpenAICompatibleProvider(LLMInterface):
    """OpenAI Chat Completions transport with provider-scoped configuration."""

    def __init__(
        self,
        *,
        provider_name: str = "openai_compatible",
        preset: ProviderPreset | None = None,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self.name = str(provider_name or "openai_compatible").strip().lower()
        self.preset = preset
        prefix = _env_prefix(self.name)

        preset_base = preset.base_url if preset is not None else ""
        preset_model = preset.default_model if preset is not None else ""
        base_env = (
            preset.base_url_env
            if preset is not None
            else "MARY_OPENAI_COMPAT_BASE_URL"
        )
        model_env = (
            preset.model_env
            if preset is not None
            else "MARY_OPENAI_COMPAT_MODEL"
        )

        self.base_url = str(
            base_url
            or os.getenv(base_env, "").strip()
            or preset_base
        ).rstrip("/")
        self.model = str(
            model
            or os.getenv(model_env, "").strip()
            or preset_model
        ).strip()

        resolved_key = str(api_key or "").strip()
        if not resolved_key and preset is not None:
            for env_name in preset.api_key_envs:
                candidate = os.getenv(env_name, "").strip()
                if candidate:
                    resolved_key = candidate
                    break
        if not resolved_key and preset is None:
            resolved_key = os.getenv("MARY_OPENAI_COMPAT_API_KEY", "").strip()
        self.api_key = resolved_key

        timeout_name = f"MARY_{prefix}_TIMEOUT_SECONDS"
        self.timeout = max(
            1.0,
            float(
                os.getenv(
                    timeout_name,
                    os.getenv("MARY_OPENAI_COMPAT_TIMEOUT_SECONDS", "30"),
                )
                or 30
            ),
        )
        self.client = None

    def _is_local(self) -> bool:
        return _is_loopback_url(self.base_url)

    def route_capabilities(self) -> ProviderRoute:
        if self._is_local():
            return ProviderRoute(
                privacy_modes=frozenset({
                    GenerationPrivacy.CLOUD_OK.value,
                    GenerationPrivacy.REDACT_FIRST.value,
                    GenerationPrivacy.LOCAL_ONLY.value,
                }),
                cost_class=GenerationCost.ZERO_LOCAL.value,
                structured_output=bool(self.preset and self.preset.structured_output),
                deadline_enforced=True,
            )
        return ProviderRoute(
            privacy_modes=frozenset({
                GenerationPrivacy.CLOUD_OK.value,
                GenerationPrivacy.REDACT_FIRST.value,
            }),
            cost_class=(
                self.preset.cost_class
                if self.preset is not None
                else GenerationCost.PAID_LOW.value
            ),
            structured_output=bool(self.preset and self.preset.structured_output),
            deadline_enforced=True,
        )

    def _client(self, *, timeout_seconds: float | None = None):
        if not self.is_available():
            raise LLMProviderError(
                f"{self.name} is not configured.",
                provider=self.name,
                retryable=False,
                category="not_configured",
            )
        if self.client is None:
            from openai import OpenAI

            self.client = OpenAI(
                api_key=self.api_key or "mary-local",
                base_url=self.base_url,
                timeout=(
                    self.timeout
                    if timeout_seconds is None
                    else max(0.1, min(self.timeout, float(timeout_seconds)))
                ),
                max_retries=0,
            )
        return self.client

    def _extra_body(self) -> dict[str, Any]:
        prefix = _env_prefix(self.name)
        raw = os.getenv(f"MARY_{prefix}_EXTRA_BODY_JSON", "").strip()
        if not raw:
            return {}
        try:
            value = json.loads(raw)
        except Exception as exc:
            raise LLMProviderError(
                f"Invalid extra-body JSON configured for {self.name}.",
                provider=self.name,
                retryable=False,
                category="invalid_configuration",
            ) from exc
        if not isinstance(value, dict):
            raise LLMProviderError(
                f"Extra-body JSON for {self.name} must be an object.",
                provider=self.name,
                retryable=False,
                category="invalid_configuration",
            )
        return value

    def _request_kwargs(
        self,
        messages,
        *,
        temperature: float,
        max_tokens: int,
        response_format: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": str(message.role), "content": str(message.content)}
                for message in messages
            ],
            "temperature": float(temperature),
            "max_tokens": int(max_tokens),
        }
        if response_format is not None:
            payload["response_format"] = response_format

        prefix = _env_prefix(self.name)
        reasoning_effort = os.getenv(
            f"MARY_{prefix}_REASONING_EFFORT",
            "",
        ).strip().lower()
        if reasoning_effort:
            payload["reasoning_effort"] = reasoning_effort

        extra_body = self._extra_body()
        if extra_body:
            payload["extra_body"] = extra_body
        return payload

    @staticmethod
    def _usage(response: Any) -> dict[str, int]:
        usage = getattr(response, "usage", None)
        if usage is None:
            return {}
        prompt = int(getattr(usage, "prompt_tokens", 0) or 0)
        completion = int(getattr(usage, "completion_tokens", 0) or 0)
        total = int(getattr(usage, "total_tokens", prompt + completion) or 0)
        completion_details = getattr(usage, "completion_tokens_details", None)
        reasoning = int(
            getattr(completion_details, "reasoning_tokens", 0) or 0
        )
        prompt_details = getattr(usage, "prompt_tokens_details", None)
        cached = int(
            getattr(prompt_details, "cached_tokens", 0) or 0
        )
        return {
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "reasoning_tokens": reasoning,
            "cached_prompt_tokens": cached,
            "total_tokens": total,
        }

    def _generate(
        self,
        messages,
        *,
        temperature: float,
        max_tokens: int,
        timeout_seconds: float | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse:
        client = self._client(timeout_seconds=timeout_seconds)
        response = client.chat.completions.create(
            **self._request_kwargs(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
            )
        )
        if not getattr(response, "choices", None):
            raise LLMProviderError(
                f"{self.name} returned no completion choices.",
                provider=self.name,
                retryable=True,
                category="empty_response",
            )
        choice = response.choices[0]
        message = getattr(choice, "message", None)
        content = str(getattr(message, "content", "") or "")
        if not content.strip():
            raise LLMProviderError(
                f"{self.name} completed without visible response content.",
                provider=self.name,
                retryable=True,
                category="empty_response",
            )
        return LLMResponse(
            content=content,
            provider=self.name,
            model=self.model,
            finish_reason=getattr(choice, "finish_reason", None),
            usage=self._usage(response),
            raw=response,
        )

    def generate(
        self,
        messages,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        return self._generate(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def generate_constrained(
        self,
        request: GenerationRequest,
        *,
        timeout_seconds: float | None = None,
    ) -> LLMResponse:
        if request.structured_output and not self.route_capabilities().structured_output:
            raise LLMProviderError(
                f"{self.name} is not registered for structured output.",
                provider=self.name,
                retryable=False,
                category="unsupported_constraint",
            )

        response_format: dict[str, Any] | None = None
        if request.structured_output:
            if request.structured_schema_json:
                schema = json.loads(request.structured_schema_json)
                response_format = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "mary_response",
                        "strict": True,
                        "schema": schema,
                    },
                }
            else:
                response_format = {"type": "json_object"}

        return self._generate(
            list(request.messages),
            temperature=0.7 if request.temperature is None else request.temperature,
            max_tokens=2048 if request.max_tokens is None else request.max_tokens,
            timeout_seconds=timeout_seconds,
            response_format=response_format,
        )

    def is_available(self) -> bool:
        if not self.base_url or not self.model:
            return False
        if self._is_local():
            return True
        return bool(self.api_key)

    def provider_name(self) -> str:
        return self.name

    def model_name(self) -> str:
        return self.model
