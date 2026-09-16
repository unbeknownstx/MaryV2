"""Canonical-Core provider backed by a replaceable local capability node.

The logical provider name is local_device. The selected device owns the actual
runtime, model identifier, and local execution permission. Core sends only
typed chat messages and role hints; it never sends shell commands or arbitrary
model paths.
"""
from __future__ import annotations

import os
from typing import Any

from mary.distributed import DeviceTaskBroker, NodeRegistry
from mary.llm.interface import (
    GenerationCost,
    GenerationPrivacy,
    GenerationRequest,
    LLMInterface,
    LLMMessage,
    LLMProviderError,
    LLMResponse,
    ProviderRoute,
)


class DeviceLocalProvider(LLMInterface):
    """Expose a connected node's llm.local capability as local_device."""

    def __init__(
        self,
        registry: NodeRegistry,
        broker: DeviceTaskBroker,
        *,
        role: str = "general",
        timeout_seconds: float | None = None,
        fallback_provider: LLMInterface | None = None,
    ) -> None:
        self.registry = registry
        self.broker = broker
        self.role = self._normalize_role(role)
        self.fallback_provider = fallback_provider
        if timeout_seconds is None:
            timeout_env = (
                "MARY_DEVICE_LOCAL_FAST_TIMEOUT"
                if self.role == "fast"
                else "MARY_DEVICE_LOCAL_TIMEOUT"
            )
            timeout_default = "12" if self.role == "fast" else "180"
            try:
                timeout_seconds = float(os.getenv(timeout_env, timeout_default))
            except (TypeError, ValueError):
                timeout_seconds = float(timeout_default)
        self.timeout_seconds = max(3.0, min(240.0, float(timeout_seconds)))

    @staticmethod
    def _normalize_role(role: str) -> str:
        value = str(role or "general").strip().lower()
        return value if value in {"general", "conversation", "fast", "utility"} else "general"

    def route_capabilities(self) -> ProviderRoute:
        return ProviderRoute(
            privacy_modes=frozenset({
                GenerationPrivacy.CLOUD_OK.value,
                GenerationPrivacy.REDACT_FIRST.value,
                GenerationPrivacy.LOCAL_ONLY.value,
            }),
            cost_class=GenerationCost.ZERO_LOCAL.value,
            deadline_enforced=True,
        )

    def for_role(self, role: str) -> "DeviceLocalProvider":
        normalized = self._normalize_role(role)
        # Purpose adapters should receive their own role budget. In
        # particular, conversation_fast must not inherit the 180 s general
        # device wait merely because the registered provider was created as
        # role=general.
        inherited_timeout = self.timeout_seconds if normalized == self.role else None
        fallback = self.fallback_provider
        for_role = getattr(fallback, "for_role", None)
        if callable(for_role):
            try:
                fallback = for_role(normalized)
            except Exception:
                fallback = self.fallback_provider
        return DeviceLocalProvider(
            self.registry,
            self.broker,
            role=normalized,
            timeout_seconds=inherited_timeout,
            fallback_provider=fallback,
        )

    def for_purpose(self, purpose: str | None) -> "DeviceLocalProvider":
        name = str(purpose or "").strip().lower()
        if name in {"social_instant", "conversation_fast"}:
            return self.for_role("fast")
        if name in {"conversation", "character", "relational", "self"}:
            return self.for_role("conversation")
        return self.for_role("general")

    def _generate(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float,
        max_tokens: int,
        timeout_seconds: float | None = None,
    ) -> LLMResponse:
        selected = self.registry.choose("llm.local", require_execution_ready=True)
        if selected is None:
            fallback = self.fallback_provider
            try:
                fallback_ready = bool(fallback is not None and fallback.is_available())
            except Exception:
                fallback_ready = False
            if not fallback_ready:
                raise LLMProviderError(
                    "No authorized device or Core-local runtime currently exposes llm.local.",
                    provider="local_device",
                    retryable=True,
                )
            response = fallback.generate(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return LLMResponse(
                content=str(response.content or ""),
                provider="local_device",
                model=str(response.model or fallback.model_name()),
                finish_reason=response.finish_reason,
                usage=dict(response.usage or {}),
                raw=response.raw,
            )

        task = self.broker.enqueue(
            self.registry,
            capability="llm.local",
            intent=f"Mary Core {self.role} local language generation",
            args={
                "messages": [
                    {"role": str(message.role), "content": str(message.content)}
                    for message in messages
                ],
                "role": self.role,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            requester_device_id="mary-core-llm-router",
        )
        wait_seconds = self.timeout_seconds
        if timeout_seconds is not None:
            wait_seconds = max(0.1, min(wait_seconds, float(timeout_seconds)))
        completed = self.broker.wait_for_terminal(
            task.task_id,
            timeout_seconds=wait_seconds,
        )
        if completed is None:
            raise LLMProviderError(
                "The local-device generation task disappeared before completion.",
                provider="local_device",
                retryable=True,
            )
        if completed.status != "completed":
            detail = completed.error or f"device task ended with status {completed.status}"
            if completed.status == "claimed":
                detail = (
                    "local-device generation exceeded the "
                    f"{self.timeout_seconds:g}s Core wait limit"
                )
            raise LLMProviderError(detail, provider="local_device", retryable=True)

        result: dict[str, Any] = dict(completed.result or {})
        content = str(result.get("content") or "").strip()
        if not content:
            raise LLMProviderError(
                "The local-device task completed without response content.",
                provider="local_device",
                retryable=True,
            )
        return LLMResponse(
            content=content,
            provider="local_device",
            model=str(result.get("model") or self.model_name()),
            finish_reason=str(result.get("finish_reason") or "") or None,
            usage=dict(result.get("usage") or {}),
            raw=None,
        )

    def generate(
        self,
        messages: list[LLMMessage],
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
        return self._generate(
            list(request.messages),
            temperature=0.7 if request.temperature is None else request.temperature,
            max_tokens=2048 if request.max_tokens is None else request.max_tokens,
            timeout_seconds=timeout_seconds,
        )

    def is_available(self) -> bool:
        if self.registry.choose("llm.local", require_execution_ready=True) is not None:
            return True
        try:
            return bool(self.fallback_provider is not None and self.fallback_provider.is_available())
        except Exception:
            return False

    def provider_name(self) -> str:
        return "local_device"

    def model_name(self) -> str:
        selected = self.registry.choose("llm.local", require_execution_ready=True)
        if selected is None:
            try:
                if self.fallback_provider is not None and self.fallback_provider.is_available():
                    return str(self.fallback_provider.model_name() or f"core-local:{self.role}")[:160]
            except Exception:
                pass
            return f"device:{self.role}:offline"
        capability = selected.capabilities.get("llm.local")
        metadata = dict(getattr(capability, "metadata", {}) or {})
        key = f"{self.role}_model"
        model = (
            metadata.get(key)
            or metadata.get("configured_model")
            or metadata.get("model")
            or f"device:{self.role}"
        )
        runtime = str(metadata.get("runtime") or "").strip()
        return f"{runtime}/{model}"[:160] if runtime else str(model)[:160]
