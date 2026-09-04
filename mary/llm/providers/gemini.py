"""Gemini provider using Google's OpenAI-compatible endpoint."""

from __future__ import annotations

import os

from ..interface import LLMInterface, LLMResponse


_LEGACY_MODEL_ALIASES = {
    # This model now returns a 404 for the user's current Gemini account and
    # Google's error response directs callers to Gemini 3.6 Flash.
    "gemini-2.5-flash": "gemini-3.6-flash",
}


class GeminiProvider(LLMInterface):
    """Free-tier Gemini route for MaryV2."""

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
    ) -> None:
        requested_model = (
            model
            or os.getenv(
                "MARY_GEMINI_MODEL",
                "gemini-3.6-flash",
            )
        ).strip()

        # Keep older MaryV2 .env files working after Google's model retirement.
        self.model = _LEGACY_MODEL_ALIASES.get(
            requested_model,
            requested_model,
        )
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.client = None

    def generate(
        self,
        messages,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        if not self.api_key:
            raise RuntimeError(
                "Gemini API key is not configured. Set GEMINI_API_KEY."
            )

        if self.client is None:
            from openai import OpenAI

            self.client = OpenAI(
                api_key=self.api_key,
                base_url=(
                    "https://generativelanguage.googleapis.com/"
                    "v1beta/openai/"
                ),
                timeout=float(os.getenv("MARY_GEMINI_TIMEOUT_SECONDS", "8")),
                max_retries=0,
            )

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": message.role,
                    "content": message.content,
                }
                for message in messages
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            **({"reasoning_effort": os.getenv("MARY_GEMINI_REASONING_EFFORT", "minimal").strip().lower() or "minimal"} if self.model.startswith("gemini-3") else {}),
        )

        choice = response.choices[0]
        raw_usage = getattr(response, "usage", None)
        usage = (
            {
                "prompt_tokens": getattr(raw_usage, "prompt_tokens", 0),
                "completion_tokens": getattr(raw_usage, "completion_tokens", 0),
                "total_tokens": getattr(raw_usage, "total_tokens", 0),
            }
            if raw_usage
            else {}
        )

        return LLMResponse(
            content=choice.message.content or "",
            provider="gemini",
            model=self.model,
            finish_reason=getattr(choice, "finish_reason", None),
            usage=usage,
            raw=response,
        )

    def is_available(self) -> bool:
        return bool(self.api_key)

    def provider_name(self) -> str:
        return "gemini"

    def model_name(self) -> str:
        return self.model
