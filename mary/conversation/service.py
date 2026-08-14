"""
MaryV2 Conversation Service

Provides the boundary between Mary's runtime pipeline and an LLM.

This layer does not own:
    - memory
    - personality
    - tools
    - internet access
    - autonomy
    - provider-specific logic

It converts conversational input into LLM messages and returns
the standardized LLM response.
"""

from __future__ import annotations

from typing import Sequence

from mary.llm.interface import (
    LLMMessage,
    LLMResponse,
)
from mary.llm.router import LLMRouter


class ConversationService:
    """
    Coordinates one conversational exchange with the configured LLM.
    """

    def __init__(
        self,
        router: LLMRouter,
        *,
        system_prompt: str | None = None,
    ) -> None:
        self.router = router
        self.system_prompt = system_prompt

    def respond(
        self,
        user_input: str,
        *,
        context: Sequence[LLMMessage] | None = None,
        provider: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """
        Generate one conversational response.

        Conversation history is supplied explicitly through context.
        Persistent memory is handled elsewhere.
        """

        messages: list[LLMMessage] = []

        if self.system_prompt:
            messages.append(
                LLMMessage(
                    role="system",
                    content=self.system_prompt,
                )
            )

        if context:
            messages.extend(context)

        messages.append(
            LLMMessage(
                role="user",
                content=user_input,
            )
        )

        return self.router.generate(
            messages=messages,
            provider=provider,
            temperature=temperature,
            max_tokens=max_tokens,
        )
