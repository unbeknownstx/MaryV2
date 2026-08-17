"""
MaryV2 Groq Provider

Groq-specific implementation of the LLM interface.
"""

import os

from groq import Groq

from ..interface import (
    LLMInterface,
    LLMMessage,
    LLMResponse,
)


class GroqProvider(LLMInterface):
    """
    Language-model provider backed by Groq.
    """

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
    ):
        self.model = model

        self.api_key = (
            api_key
            or os.getenv("GROQ_API_KEY")
        )

        self.client = None

        if self.api_key:
            # Desktop/conversational turns should never inherit the Groq
            # SDK's long default wait-and-retry behavior. Mary already has
            # provider-failure fallbacks at the cognition layer, so fail
            # promptly and let those deterministic fallbacks take over.
            self.client = Groq(
                api_key=self.api_key,
                timeout=20.0,
                max_retries=0,
            )

    def generate(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> LLMResponse:

        if not self.client:
            raise RuntimeError(
                "Groq API key is not configured. "
                "Set GROQ_API_KEY in the environment."
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
        )

        choice = response.choices[0]

        usage = {}

        if getattr(response, "usage", None):
            usage = {
                "prompt_tokens": getattr(
                    response.usage,
                    "prompt_tokens",
                    0,
                ),
                "completion_tokens": getattr(
                    response.usage,
                    "completion_tokens",
                    0,
                ),
                "total_tokens": getattr(
                    response.usage,
                    "total_tokens",
                    0,
                ),
            }

        return LLMResponse(
            content=choice.message.content or "",
            provider=self.provider_name(),
            model=self.model,
            finish_reason=getattr(
                choice,
                "finish_reason",
                None,
            ),
            usage=usage,
            raw=response,
        )

    def is_available(self) -> bool:
        return bool(
            self.api_key
            and self.client
        )

    def provider_name(self) -> str:
        return "groq"

    def model_name(self) -> str:
        return self.model