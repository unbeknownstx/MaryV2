"""Ollama provider backed by an authorized MaryV2 capability node.

This adapter lets the canonical remote Mary Core use the existing ``ollama``
provider route without pretending Ollama is installed on the cloud host.  It
queues one typed ``llm.ollama`` capability task, waits on the Core-owned broker,
and converts the sanitized device result back into Mary's normal LLM contract.

The device still owns local execution permission and concrete model selection.
Core never sends an arbitrary model name, shell command, filesystem path, or raw
provider payload through this adapter.
"""
from __future__ import annotations

import os
from typing import Any

from mary.distributed import DeviceTaskBroker, NodeRegistry
from mary.llm.interface import LLMInterface, LLMMessage, LLMProviderError, LLMResponse


class DeviceOllamaProvider(LLMInterface):
    """Expose a connected device's bounded Ollama executor as provider ``ollama``."""

    def __init__(
        self,
        registry: NodeRegistry,
        broker: DeviceTaskBroker,
        *,
        role: str = "general",
        timeout_seconds: float | None = None,
    ) -> None:
        self.registry = registry
        self.broker = broker
        self.role = self._normalize_role(role)
        if timeout_seconds is None:
            try:
                timeout_seconds = float(os.getenv("MARY_DEVICE_OLLAMA_TIMEOUT", "190"))
            except (TypeError, ValueError):
                timeout_seconds = 190.0
        self.timeout_seconds = max(5.0, min(240.0, float(timeout_seconds)))

    @staticmethod
    def _normalize_role(role: str) -> str:
        value = str(role or "general").strip().lower()
        return value if value in {"general", "conversation", "fast", "utility"} else "general"

    def for_role(self, role: str) -> "DeviceOllamaProvider":
        """Return a lightweight view using another device-owned model role."""

        return DeviceOllamaProvider(
            self.registry,
            self.broker,
            role=self._normalize_role(role),
            timeout_seconds=self.timeout_seconds,
        )

    def for_purpose(self, purpose: str | None) -> "DeviceOllamaProvider":
        """Map Mary's existing generation purpose to a device-owned model role."""

        name = str(purpose or "").strip().lower()
        if name in {"social_instant", "conversation_fast"}:
            return self.for_role("fast")
        if name in {"conversation", "character", "relational", "self"}:
            return self.for_role("conversation")
        return self.for_role("general")

    def generate(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        selected = self.registry.choose("llm.ollama")
        if selected is None:
            raise LLMProviderError(
                "No connected capability node currently exposes llm.ollama.",
                provider="ollama",
                retryable=True,
            )

        task = self.broker.enqueue(
            self.registry,
            capability="llm.ollama",
            intent=f"Mary Core {self.role} language generation",
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
        completed = self.broker.wait_for_terminal(
            task.task_id,
            timeout_seconds=self.timeout_seconds,
        )
        if completed is None:
            raise LLMProviderError(
                "The device Ollama task disappeared before completion.",
                provider="ollama",
                retryable=True,
            )
        if completed.status != "completed":
            detail = completed.error or f"device task ended with status {completed.status}"
            if completed.status == "claimed":
                detail = f"device Ollama generation exceeded the {self.timeout_seconds:g}s Core wait limit"
            raise LLMProviderError(detail, provider="ollama", retryable=True)

        result: dict[str, Any] = dict(completed.result or {})
        content = str(result.get("content") or "").strip()
        if not content:
            raise LLMProviderError(
                "The device Ollama task completed without response content.",
                provider="ollama",
                retryable=True,
            )
        return LLMResponse(
            content=content,
            provider="ollama",
            model=str(result.get("model") or self.model_name()),
            finish_reason=str(result.get("finish_reason") or "") or None,
            usage=dict(result.get("usage") or {}),
            raw=None,
        )

    def is_available(self) -> bool:
        return self.registry.choose("llm.ollama") is not None

    def provider_name(self) -> str:
        return "ollama"

    def model_name(self) -> str:
        selected = self.registry.choose("llm.ollama")
        if selected is None:
            return f"device:{self.role}:offline"
        capability = selected.capabilities.get("llm.ollama")
        metadata = dict(getattr(capability, "metadata", {}) or {})
        key = f"{self.role}_model"
        return str(
            metadata.get(key)
            or metadata.get("configured_model")
            or metadata.get("model")
            or f"device:{self.role}"
        )[:160]
