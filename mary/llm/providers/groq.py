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

        request = {
            "model": self.model,
            "messages": [
                {
                    "role": message.role,
                    "content": message.content,
                }
                for message in messages
            ],
            "temperature": temperature,
        }

        if self.model.startswith("openai/gpt-oss-"):
            # GPT-OSS is a reasoning model. Groq defaults it to medium
            # reasoning effort, which can spend most of a small completion
            # budget on hidden reasoning during ordinary conversation. Mary
            # uses Groq as her fast free conversational lane, so default to
            # low effort and suppress returned reasoning. Harder reasoning can
            # still be routed to another provider or opt into a different
            # effort later without changing Mary's identity/cognition layer.
            request["max_completion_tokens"] = int(max_tokens)
            request["reasoning_effort"] = os.getenv(
                "MARY_GROQ_REASONING_EFFORT",
                "low",
            ).strip().lower() or "low"
            request["include_reasoning"] = False
        else:
            # max_tokens remains broadly compatible with non-reasoning Groq
            # models. GPT-OSS uses Groq's preferred max_completion_tokens.
            request["max_tokens"] = int(max_tokens)

        response = self.client.chat.completions.create(**request)

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

            details = getattr(
                response.usage,
                "completion_tokens_details",
                None,
            )
            reasoning_tokens = getattr(
                details,
                "reasoning_tokens",
                None,
            ) if details is not None else None
            if reasoning_tokens is not None:
                usage["reasoning_tokens"] = reasoning_tokens

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