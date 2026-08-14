"""
MaryV2 Conversation Pipeline Stage

Bridges the runtime pipeline with Mary's conversation service.

The stage does not know how an LLM works.
It only asks ConversationService for a response.
"""

from __future__ import annotations

from mary.runtime.pipeline import (
    PipelineContext,
    PipelineStage,
    StageResult,
)

from .service import ConversationService


class ConversationStage(PipelineStage):
    """
    Pipeline stage responsible for generating Mary's response.
    """

    def __init__(
        self,
        conversation: ConversationService,
        *,
        name: str = "conversation",
        required: bool = True,
        enabled: bool = True,
        provider: str | None = None,
    ) -> None:
        super().__init__(
            name=name,
            handler=lambda context: None,
            required=required,
            enabled=enabled,
        )

        self.conversation = conversation
        self.provider = provider

    def process(
        self,
        context: PipelineContext,
    ) -> StageResult:

        if not isinstance(
            context.input_data,
            str,
        ):
            raise TypeError(
                "ConversationStage requires string input."
            )

        response = self.conversation.respond(
            context.input_data,
            provider=self.provider,
        )

        return StageResult(
            success=True,
            output=response.content,
            values={
                "llm_response": response,
            },
            metadata={
                "llm_provider": response.provider,
                "llm_model": response.model,
                "llm_usage": dict(
                    response.usage
                ),
                "llm_finish_reason": (
                    response.finish_reason
                ),
            },
        )
