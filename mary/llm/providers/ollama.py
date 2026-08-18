"""Local Ollama provider using Ollama's native chat API."""

from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.request
from typing import Any

from ..interface import LLMInterface, LLMResponse


_TRUE_VALUES = {"1", "true", "yes", "on"}


class OllamaProvider(LLMInterface):
    """Generate Mary's language responses through a local Ollama server."""

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.model = model or os.getenv(
            "MARY_OLLAMA_MODEL",
            "qwen3:4b",
        )
        self.base_url = (
            base_url
            or os.getenv(
                "MARY_OLLAMA_BASE_URL",
                "http://localhost:11434",
            )
        ).rstrip("/")
        self.timeout = float(
            os.getenv(
                "MARY_OLLAMA_TIMEOUT",
                "180",
            )
        )
        self.keep_alive: str | int = os.getenv(
            "MARY_OLLAMA_KEEP_ALIVE",
            "30m",
        )
        self.think = os.getenv(
            "MARY_OLLAMA_THINK",
            "false",
        ).strip().lower() in _TRUE_VALUES
        self.num_ctx = int(
            os.getenv(
                "MARY_OLLAMA_NUM_CTX",
                "8192",
            )
        )

    def generate(
        self,
        messages,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": message.role,
                    "content": message.content,
                }
                for message in messages
            ],
            "stream": False,
            "think": self.think,
            "keep_alive": self.keep_alive,
            "options": {
                "temperature": float(temperature),
                "num_predict": int(max_tokens),
                "num_ctx": self.num_ctx,
            },
        }

        request = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=self.timeout,
            ) as response:
                raw_body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", errors="replace")
            except Exception:
                detail = ""
            message = detail.strip() or str(exc)
            raise RuntimeError(
                f"Ollama HTTP {exc.code}: {message}"
            ) from exc
        except (TimeoutError, socket.timeout) as exc:
            raise RuntimeError(
                f"Ollama request timed out after {self.timeout:g} seconds."
            ) from exc
        except urllib.error.URLError as exc:
            reason = getattr(exc, "reason", exc)
            if isinstance(reason, (TimeoutError, socket.timeout)):
                raise RuntimeError(
                    f"Ollama request timed out after {self.timeout:g} seconds."
                ) from exc
            raise RuntimeError(
                f"Unable to reach Ollama at {self.base_url}: {reason}"
            ) from exc

        try:
            result: dict[str, Any] = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "Ollama returned an invalid JSON response."
            ) from exc

        if result.get("error"):
            raise RuntimeError(
                f"Ollama error: {result['error']}"
            )

        message_data = result.get("message") or {}
        content = str(message_data.get("content") or "")

        prompt_tokens = int(result.get("prompt_eval_count") or 0)
        completion_tokens = int(result.get("eval_count") or 0)
        usage = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        }

        return LLMResponse(
            content=content,
            provider="ollama",
            model=self.model,
            finish_reason=result.get("done_reason"),
            usage=usage,
            raw=result,
        )

    def is_available(self) -> bool:
        return os.getenv(
            "MARY_OLLAMA_ENABLED",
            "true",
        ).strip().lower() in _TRUE_VALUES

    def provider_name(self) -> str:
        return "ollama"

    def model_name(self) -> str:
        return self.model