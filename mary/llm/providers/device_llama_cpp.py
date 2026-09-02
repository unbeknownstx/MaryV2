"""llama.cpp provider backed by an authorized Mary capability node.

Core sends only bounded chat-generation tasks. The device owns the concrete
GGUF, adapter set, llama-server endpoint, and local execution permission.
"""
from __future__ import annotations

import os
from typing import Any

from mary.distributed import DeviceTaskBroker, NodeRegistry
from mary.llm.interface import GenerationCost, GenerationPrivacy, LLMInterface, LLMMessage, LLMProviderError, LLMResponse, ProviderRoute


class DeviceLlamaCppProvider(LLMInterface):
    def route_capabilities(self) -> ProviderRoute:
        return ProviderRoute(
            privacy_modes=frozenset({
                GenerationPrivacy.CLOUD_OK.value,
                GenerationPrivacy.REDACT_FIRST.value,
                GenerationPrivacy.LOCAL_ONLY.value,
            }),
            cost_class=GenerationCost.ZERO_LOCAL.value,
        )

    def __init__(self, registry: NodeRegistry, broker: DeviceTaskBroker, *, role: str = "general", timeout_seconds: float | None = None) -> None:
        self.registry = registry
        self.broker = broker
        self.role = self._normalize_role(role)
        if timeout_seconds is None:
            try:
                timeout_seconds = float(os.getenv("MARY_DEVICE_LLAMA_CPP_TIMEOUT", "190"))
            except (TypeError, ValueError):
                timeout_seconds = 190.0
        self.timeout_seconds = max(5.0, min(240.0, float(timeout_seconds)))

    @staticmethod
    def _normalize_role(role: str) -> str:
        value = str(role or "general").strip().lower()
        return value if value in {"general", "conversation", "fast", "utility"} else "general"

    def for_role(self, role: str) -> "DeviceLlamaCppProvider":
        return DeviceLlamaCppProvider(self.registry, self.broker, role=self._normalize_role(role), timeout_seconds=self.timeout_seconds)

    def for_purpose(self, purpose: str | None) -> "DeviceLlamaCppProvider":
        name = str(purpose or "").strip().lower()
        if name in {"social_instant", "conversation_fast"}:
            return self.for_role("fast")
        if name in {"conversation", "character", "relational", "self"}:
            return self.for_role("conversation")
        return self.for_role("general")

    def generate(self, messages: list[LLMMessage], temperature: float = 0.7, max_tokens: int = 2048) -> LLMResponse:
        selected = self.registry.choose("llm.llama_cpp")
        if selected is None:
            raise LLMProviderError("No connected capability node currently exposes llm.llama_cpp.", provider="llama_cpp", retryable=True)
        task = self.broker.enqueue(
            self.registry,
            capability="llm.llama_cpp",
            intent=f"Mary Core {self.role} llama.cpp generation",
            args={
                "messages": [{"role": str(m.role), "content": str(m.content)} for m in messages],
                "role": self.role,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            requester_device_id="mary-core-llm-router",
        )
        completed = self.broker.wait_for_terminal(task.task_id, timeout_seconds=self.timeout_seconds)
        if completed is None or completed.status != "completed":
            detail = "device llama.cpp task unavailable" if completed is None else (completed.error or f"device task ended with status {completed.status}")
            raise LLMProviderError(detail, provider="llama_cpp", retryable=True)
        result: dict[str, Any] = dict(completed.result or {})
        content = str(result.get("content") or "").strip()
        if not content:
            raise LLMProviderError("The device llama.cpp task completed without response content.", provider="llama_cpp", retryable=True)
        return LLMResponse(content=content, provider="llama_cpp", model=str(result.get("model") or self.model_name()), finish_reason=str(result.get("finish_reason") or "") or None, usage=dict(result.get("usage") or {}), raw=None)

    def is_available(self) -> bool:
        return self.registry.choose("llm.llama_cpp") is not None

    def provider_name(self) -> str:
        return "llama_cpp"

    def model_name(self) -> str:
        selected = self.registry.choose("llm.llama_cpp")
        if selected is None:
            return f"device:{self.role}:offline"
        capability = selected.capabilities.get("llm.llama_cpp")
        metadata = dict(getattr(capability, "metadata", {}) or {})
        return str(metadata.get("configured_model") or metadata.get("model") or f"device:{self.role}")[:160]
