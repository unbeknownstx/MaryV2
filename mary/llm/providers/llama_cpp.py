"""Local llama.cpp server provider.

This adapter deliberately treats llama.cpp as a replaceable local generation
engine.  It never owns Mary's identity, memory, relationship state, or adapter
selection truth.  The server may load one or more GGUF LoRA adapters; optional
per-request scales are supplied through ``MARY_LLAMA_CPP_LORA_SCALES``.
"""
from __future__ import annotations

import json
import os
import socket
import time
import urllib.error
import urllib.request
from typing import Any

from ..interface import (
    GenerationCost,
    GenerationPrivacy,
    GenerationRequest,
    LLMInterface,
    LLMProviderError,
    LLMResponse,
    ProviderRoute,
)

_TRUE = {"1", "true", "yes", "on", "enabled"}


class LlamaCppProvider(LLMInterface):
    """Generate through a local ``llama-server`` OpenAI-compatible endpoint."""

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.base_url = (
            base_url
            or os.getenv("MARY_LLAMA_CPP_BASE_URL", "http://127.0.0.1:8080")
        ).rstrip("/")
        self.model = str(model or os.getenv("MARY_LLAMA_CPP_MODEL", "")).strip()
        self.timeout = max(1.0, float(os.getenv("MARY_LLAMA_CPP_TIMEOUT", "120") or 120))
        self.health_timeout = max(
            0.1,
            float(os.getenv("MARY_LLAMA_CPP_HEALTH_TIMEOUT", "0.8") or 0.8),
        )
        self.health_ttl = max(
            0.0,
            float(os.getenv("MARY_LLAMA_CPP_HEALTH_TTL", "5.0") or 5.0),
        )
        self._health_checked_at = 0.0
        self._health_available = False
        self._discovered_model: str | None = None

    def route_capabilities(self) -> ProviderRoute:
        return ProviderRoute(
            privacy_modes=frozenset({
                GenerationPrivacy.CLOUD_OK.value,
                GenerationPrivacy.REDACT_FIRST.value,
                GenerationPrivacy.LOCAL_ONLY.value,
            }),
            cost_class=GenerationCost.ZERO_LOCAL.value,
            structured_output=False,
            deadline_enforced=True,
        )

    @staticmethod
    def _lora_scales() -> list[dict[str, float | int]]:
        raw = os.getenv("MARY_LLAMA_CPP_LORA_SCALES", "").strip()
        if not raw:
            return []
        try:
            value = json.loads(raw)
        except Exception:
            return []
        if not isinstance(value, list):
            return []
        output: list[dict[str, float | int]] = []
        for item in value[:16]:
            if not isinstance(item, dict):
                continue
            try:
                adapter_id = int(item.get("id"))
                scale = float(item.get("scale", 1.0))
            except (TypeError, ValueError):
                continue
            output.append({"id": max(0, adapter_id), "scale": max(-4.0, min(4.0, scale))})
        return output

    def _request_json(
        self,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> Any:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            method="GET" if payload is None else "POST",
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=max(0.05, float(timeout if timeout is not None else self.timeout)),
            ) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raise LLMProviderError(
                "llama.cpp returned an HTTP error.",
                provider="llama_cpp",
                retryable=int(exc.code) >= 500 or int(exc.code) == 429,
                status_code=int(exc.code),
            ) from exc
        except (TimeoutError, socket.timeout) as exc:
            raise LLMProviderError(
                "llama.cpp request timed out.",
                provider="llama_cpp",
                retryable=True,
                category="timeout",
            ) from exc
        except urllib.error.URLError as exc:
            raise LLMProviderError(
                "Unable to reach local llama.cpp server.",
                provider="llama_cpp",
                retryable=True,
                category="unavailable",
            ) from exc
        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            raise LLMProviderError(
                "llama.cpp returned invalid JSON.",
                provider="llama_cpp",
                retryable=False,
                category="invalid_response",
            ) from exc

    @staticmethod
    def _thinking_policy(model: str) -> bool | None:
        """Return an explicit llama.cpp thinking preference when Mary owns one.

        Qwen3 is used in Mary as a low-latency local lane, so it defaults to
        non-thinking unless the operator explicitly opts in. Other model
        families keep their server/template default unless the environment
        explicitly selects a policy.
        """
        raw = os.getenv("MARY_LLAMA_CPP_THINKING", "").strip().lower()
        if raw in _TRUE:
            return True
        if raw in {"0", "false", "no", "off", "disabled"}:
            return False
        normalized = str(model or "").strip().lower()
        if "qwen3" in normalized:
            return False
        return None

    def _resolve_model(self) -> str:
        if self.model:
            return self.model
        if self._discovered_model:
            return self._discovered_model
        try:
            payload = self._request_json("/v1/models", timeout=self.health_timeout)
            items = payload.get("data", []) if isinstance(payload, dict) else []
            if items and isinstance(items[0], dict):
                discovered = str(items[0].get("id") or "").strip()
                if discovered:
                    self._discovered_model = discovered
                    return discovered
        except Exception:
            pass
        return "local"

    def generate_constrained(
        self,
        request: GenerationRequest,
        *,
        timeout_seconds: float | None = None,
    ) -> LLMResponse:
        if request.structured_output:
            raise LLMProviderError(
                "llama.cpp structured output is not enabled in this adapter.",
                provider="llama_cpp",
                retryable=False,
                category="unsupported_constraint",
            )
        return self.generate(
            list(request.messages),
            temperature=0.7 if request.temperature is None else request.temperature,
            max_tokens=2048 if request.max_tokens is None else request.max_tokens,
            _timeout_seconds=timeout_seconds,
        )

    @staticmethod
    def _normalize_lora(lora: Any) -> list[dict[str, float | int]]:
        if not isinstance(lora, (list, tuple)):
            return []
        output: list[dict[str, float | int]] = []
        for item in list(lora)[:16]:
            if not isinstance(item, dict):
                continue
            try:
                adapter_id = int(item.get("id"))
                scale = float(item.get("scale", 1.0))
            except (TypeError, ValueError):
                continue
            output.append({"id": max(0, adapter_id), "scale": max(-4.0, min(4.0, scale))})
        return output

    def generate_with_lora(
        self,
        messages,
        *,
        lora: Any = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        model: str | None = None,
        timeout_seconds: float | None = None,
    ) -> LLMResponse:
        return self._generate_request(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            lora=self._normalize_lora(lora),
            model=model,
            timeout_seconds=timeout_seconds,
        )

    def generate(
        self,
        messages,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        *,
        _timeout_seconds: float | None = None,
    ) -> LLMResponse:
        return self._generate_request(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            lora=self._lora_scales(),
            timeout_seconds=_timeout_seconds,
        )

    def _generate_request(
        self,
        messages,
        *,
        temperature: float,
        max_tokens: int,
        lora: list[dict[str, float | int]],
        model: str | None = None,
        timeout_seconds: float | None = None,
    ) -> LLMResponse:
        resolved_model = str(model or "").strip() or self._resolve_model()
        payload: dict[str, Any] = {
            "model": resolved_model,
            "messages": [
                {"role": str(message.role), "content": str(message.content)}
                for message in messages
            ],
            "temperature": float(temperature),
            "max_tokens": int(max_tokens),
            "stream": False,
        }
        thinking = self._thinking_policy(resolved_model)
        if thinking is not None:
            payload["chat_template_kwargs"] = {"enable_thinking": bool(thinking)}
        if lora:
            payload["lora"] = self._normalize_lora(lora)
        result = self._request_json(
            "/v1/chat/completions",
            payload=payload,
            timeout=(
                self.timeout
                if timeout_seconds is None
                else max(0.05, min(self.timeout, float(timeout_seconds)))
            ),
        )
        if not isinstance(result, dict):
            raise LLMProviderError(
                "llama.cpp returned an invalid completion payload.",
                provider="llama_cpp",
                category="invalid_response",
            )
        choices = result.get("choices") or []
        if not choices or not isinstance(choices[0], dict):
            raise LLMProviderError(
                "llama.cpp completion contained no choices.",
                provider="llama_cpp",
                category="invalid_response",
            )
        choice = choices[0]
        message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
        content = str(message.get("content") or "")
        if not content.strip():
            raise LLMProviderError(
                "llama.cpp completed without visible response content.",
                provider="llama_cpp",
                retryable=True,
                category="empty_response",
            )
        usage_raw = result.get("usage") if isinstance(result.get("usage"), dict) else {}
        usage = {
            "prompt_tokens": int(usage_raw.get("prompt_tokens") or 0),
            "completion_tokens": int(usage_raw.get("completion_tokens") or 0),
            "total_tokens": int(usage_raw.get("total_tokens") or 0),
        }
        return LLMResponse(
            content=content,
            provider="llama_cpp",
            model=resolved_model,
            finish_reason=choice.get("finish_reason"),
            usage=usage,
            raw=result,
        )

    def is_available(self) -> bool:
        if os.getenv("MARY_LLAMA_CPP_ENABLED", "false").strip().lower() not in _TRUE:
            return False
        now = time.monotonic()
        if self._health_checked_at and now - self._health_checked_at < self.health_ttl:
            return self._health_available
        try:
            payload = self._request_json("/v1/models", timeout=self.health_timeout)
            data = payload.get("data") if isinstance(payload, dict) else None
            available = isinstance(data, list) and bool(data)
            if available and not self.model and isinstance(data[0], dict):
                self._discovered_model = str(data[0].get("id") or "").strip() or None
        except Exception:
            available = False
        self._health_checked_at = now
        self._health_available = available
        return available

    def provider_name(self) -> str:
        return "llama_cpp"

    def model_name(self) -> str:
        return self._resolve_model()
