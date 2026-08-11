"""
MaryV2 OpenAI Provider

OpenAI-specific implementation of the LLM interface.
"""

import os

from openai import OpenAI

from ..interface import (
    LLMInterface,
    LLMMessage,
    LLMResponse,
)


class OpenAIProvider(LLMInterface):
    """
    Language-model provider backed by OpenAI.
    """

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
    ):
        self.model = model

        self.api_key = (
            api_key
            or os.getenv("OPENAI_API_KEY")
        )

        self.client = None

        if self.api_key:
            self.client = OpenAI(
                api_key=self.api_key
            )

    def generate(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> LLMResponse:

        if not self.client:
            raise RuntimeError(
                "OpenAI API key is not configured. "
                "Set OPENAI_API_KEY in the environment."
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
        return "openai"

    def model_name(self) -> str:
        return self.model