"""Unified local runtime provider for MaryV2.

This provider is the host-local execution surface behind the logical
local_device route. Mary chooses a bounded runtime role; the host chooses
which installed engine satisfies it. LM Studio, Ollama, and llama.cpp remain
replaceable runtimes and never own Mary identity or canonical state.
"""
from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

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


_RUNTIME_NAMES = ("lm_studio", "ollama", "llama_cpp")
_CONVERSATION_PURPOSES = {
    "conversation",
    "character",
    "relational",
    "self",
}
_FAST_PURPOSES = {"conversation_fast", "social_instant"}


def _normalize_role(role: str) -> str:
    value = str(role or "general").strip().lower()
    return value if value in {"general", "conversation", "fast", "utility"} else "general"


def _role_for_purpose(purpose: str | None) -> str:
    name = str(purpose or "").strip().lower()
    if name in _FAST_PURPOSES:
        return "fast"
    if name in _CONVERSATION_PURPOSES:
        return "conversation"
    return "general"


def _lm_studio_model_for_role(role: str) -> str:
    role = _normalize_role(role)
    base = (
        os.getenv("MARY_LM_STUDIO_MODEL", "").strip()
        or os.getenv("MARY_LM_STUDIO_IDENTIFIER", "").strip()
        or "mary-conversation"
    )
    conversation = os.getenv("MARY_LM_STUDIO_CONVERSATION_MODEL", "").strip() or base
    fast = os.getenv("MARY_LM_STUDIO_FAST_MODEL", "").strip() or conversation
    utility = os.getenv("MARY_LM_STUDIO_UTILITY_MODEL", "").strip() or fast
    return {
        "general": base,
        "conversation": conversation,
        "fast": fast,
        "utility": utility,
    }[role]


def _ollama_model_for_role(role: str) -> str | None:
    role = _normalize_role(role)
    base = os.getenv("MARY_OLLAMA_MODEL", "").strip()
    conversation = os.getenv("MARY_OLLAMA_CONVERSATION_MODEL", "").strip() or base
    fast = os.getenv("MARY_OLLAMA_FAST_MODEL", "").strip() or conversation
    utility = os.getenv("MARY_OLLAMA_UTILITY_MODEL", "").strip() or fast
    return {
        "general": base,
        "conversation": conversation,
        "fast": fast,
        "utility": utility,
    }[role] or None


def _loopback(value: str) -> bool:
    try:
        parsed = urlparse(str(value or ""))
    except Exception:
        return False
    return parsed.scheme in {"http", "https"} and (parsed.hostname or "").lower() in {
        "127.0.0.1",
        "localhost",
        "::1",
    }


def _openai_models(base_url: str, *, timeout: float = 0.45) -> tuple[str, ...]:
    """Return bounded model identifiers from a local OpenAI-compatible server."""

    base = str(base_url or "").rstrip("/")
    if not base or not _loopback(base):
        return ()
    request = Request(
        base + "/models",
        headers={
            "Accept": "application/json",
            "User-Agent": "MaryV2-local-runtime/13.65",
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=max(0.1, min(1.5, float(timeout)))) as response:
            raw = response.read(256_000)
    except (OSError, HTTPError, URLError, TimeoutError):
        return ()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return ()
    rows = payload.get("data", []) if isinstance(payload, dict) else []
    output: list[str] = []
    for row in list(rows)[:128]:
        if not isinstance(row, dict):
            continue
        model = str(row.get("id") or row.get("model") or row.get("name") or "").strip()
        if model and model not in output:
            output.append(model[:240])
    return tuple(output)


class LocalRuntimeProvider(LLMInterface):
    """Use the best host-local model runtime for one bounded role."""

    def __init__(self, *, role: str = "general") -> None:
        self.role = _normalize_role(role)
        self._last_runtime = ""
        self._last_model = ""

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

    def for_role(self, role: str) -> "LocalRuntimeProvider":
        return LocalRuntimeProvider(role=_normalize_role(role))

    def for_purpose(self, purpose: str | None) -> "LocalRuntimeProvider":
        return self.for_role(_role_for_purpose(purpose))

    def _runtime_order(self) -> tuple[str, ...]:
        configured = os.getenv("MARY_LOCAL_INFERENCE_RUNTIME", "auto").strip().lower()
        if configured in _RUNTIME_NAMES:
            return (configured,)

        if self.role == "fast":
            requested = os.getenv(
                "MARY_LOCAL_FAST_RUNTIME_ORDER",
                "ollama",
            )
            ordered: list[str] = []
            for item in str(requested or "").split(","):
                runtime = item.strip().lower()
                if runtime in _RUNTIME_NAMES and runtime not in ordered:
                    ordered.append(runtime)
            if ordered:
                return tuple(ordered)

        return _RUNTIME_NAMES

    def _build(self, runtime: str) -> LLMInterface:
        if runtime == "lm_studio":
            from mary.llm.providers.openai_compatible import OpenAICompatibleProvider

            return OpenAICompatibleProvider(
                provider_name="lm_studio",
                base_url=(
                    os.getenv("MARY_LM_STUDIO_BASE_URL", "").strip()
                    or "http://127.0.0.1:1234/v1"
                ),
                model=_lm_studio_model_for_role(self.role),
            )
        if runtime == "ollama":
            from mary.llm.providers.ollama import OllamaProvider

            return OllamaProvider(model=_ollama_model_for_role(self.role))
        if runtime == "llama_cpp":
            from mary.llm.providers.llama_cpp import LlamaCppProvider

            return LlamaCppProvider()
        raise ValueError(f"Unsupported local runtime: {runtime}")

    def _backend_available(self, runtime: str, backend: LLMInterface) -> bool:
        if runtime == "lm_studio":
            base_url = str(getattr(backend, "base_url", "") or "")
            model = str(getattr(backend, "model_name", lambda: "")() or "")
            models = _openai_models(base_url)
            return bool(models) and model in models
        try:
            return bool(backend.is_available())
        except Exception:
            return False

    def selected(self) -> tuple[str, LLMInterface] | None:
        for runtime in self._runtime_order():
            try:
                backend = self._build(runtime)
            except Exception:
                continue
            if self._backend_available(runtime, backend):
                self._last_runtime = runtime
                self._last_model = str(backend.model_name() or "")[:160]
                return runtime, backend
        return None

    def runtime_status(self) -> dict[str, Any]:
        selected = self.selected()
        if selected is None:
            return {
                "available": False,
                "runtime": "",
                "model": "",
                "role": self.role,
                "order": list(self._runtime_order()),
            }
        runtime, backend = selected
        return {
            "available": True,
            "runtime": runtime,
            "model": str(backend.model_name() or "")[:160],
            "role": self.role,
            "order": list(self._runtime_order()),
        }

    def is_available(self) -> bool:
        return self.selected() is not None

    def provider_name(self) -> str:
        return "local_device"

    def runtime_name(self) -> str:
        if self._last_runtime:
            return self._last_runtime
        selected = self.selected()
        return selected[0] if selected is not None else ""

    def model_name(self) -> str:
        if self._last_model:
            return self._last_model
        selected = self.selected()
        if selected is None:
            return f"local:{self.role}:offline"
        return str(selected[1].model_name() or f"local:{self.role}")[:160]

    def _wrap(self, runtime: str, response: LLMResponse) -> LLMResponse:
        self._last_runtime = runtime
        self._last_model = str(response.model or self._last_model or "")[:160]
        return LLMResponse(
            content=str(response.content or ""),
            provider="local_device",
            model=str(response.model or self.model_name()),
            finish_reason=response.finish_reason,
            usage=dict(response.usage or {}),
            raw=response.raw,
        )

    def generate(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        selected = self.selected()
        if selected is None:
            raise LLMProviderError(
                "No configured local model runtime is currently ready.",
                provider="local_device",
                retryable=True,
            )
        runtime, backend = selected
        response = backend.generate(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return self._wrap(runtime, response)

    def generate_constrained(
        self,
        request: GenerationRequest,
        *,
        timeout_seconds: float | None = None,
    ) -> LLMResponse:
        selected = self.selected()
        if selected is None:
            raise LLMProviderError(
                "No configured local model runtime is currently ready.",
                provider="local_device",
                retryable=True,
            )
        runtime, backend = selected
        constrained = getattr(backend, "generate_constrained", None)
        if callable(constrained):
            response = constrained(request, timeout_seconds=timeout_seconds)
        else:
            response = backend.generate(
                list(request.messages),
                temperature=0.7 if request.temperature is None else request.temperature,
                max_tokens=2048 if request.max_tokens is None else request.max_tokens,
            )
        return self._wrap(runtime, response)
