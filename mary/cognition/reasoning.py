"""
MaryV2 Reasoning System

The reasoning system is responsible for turning cognitive context and intent
into a structured reasoning result.

Reasoning does not own:
    - memory
    - personality
    - goals
    - relationship state
    - provider-specific LLM logic
    - final presentation

The LLM layer is accessed through the LLM router abstraction.
"""

from dataclasses import dataclass, field
from typing import Any

from mary.cognition.context import CognitiveContext
from mary.cognition.intent import Intent
from mary.llm.router import LLMRouter
from mary.llm.interface import LLMMessage


@dataclass
class ReasoningResult:
    """
    Structured result produced by Mary's reasoning system.
    """

    response: str

    confidence: float = 1.0

    reasoning_type: str = "general"

    intent: Intent | None = None

    tool_required: bool = False

    action_required: bool = False

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert the reasoning result into a serializable dictionary."""

        return {
            "response": self.response,
            "confidence": self.confidence,
            "reasoning_type": self.reasoning_type,
            "intent": (
                self.intent.to_dict()
                if self.intent is not None
                else None
            ),
            "tool_required": self.tool_required,
            "action_required": self.action_required,
            "metadata": self.metadata,
        }


class ReasoningEngine:
    """
    Mary's reasoning engine.

    The engine coordinates context, intent, and the LLM router without
    coupling cognition to a specific LLM provider.
    """

    def __init__(
        self,
        llm: LLMRouter,
    ) -> None:

        self.llm = llm

    def reason(
        self,
        context: CognitiveContext,
        intent: Intent | None = None,
    ) -> ReasoningResult:
        """
        Process cognitive context and produce a reasoning result.
        """

        prompt = self._build_prompt(
            context=context,
            intent=intent,
        )

        response = self.llm.generate(
            messages=[
                LLMMessage(
                    role="system",
                    content=(
                        "You are Mary, an AI assistant. "
                        "Respond naturally, directly, and consistently "
                        "with the supplied cognitive context."
                    ),
                ),
                LLMMessage(
                    role="user",
                    content=prompt,
                ),
            ],
        )

        return ReasoningResult(
            response=response.content,
            intent=intent,
            reasoning_type=(
                intent.intent_type.value
                if intent is not None
                else "general"
            ),
            metadata={
                "provider": response.provider,
                "model": response.model,
                "finish_reason": response.finish_reason,
                "usage": response.usage,
            },
        )

    def _build_prompt(
        self,
        context: CognitiveContext,
        intent: Intent | None,
    ) -> str:
        """
        Build the cognitive prompt sent to the LLM.
        """

        sections: list[str] = []

        sections.append(
            f"Current user input:\n{context.input_text}"
        )

        if intent is not None:

            sections.append(
                "Detected intent:\n"
                f"{intent.intent_type.value}"
            )

            if intent.description:

                sections.append(
                    "Intent description:\n"
                    f"{intent.description}"
                )

        if context.conversation:

            sections.append(
                "Recent conversation:\n"
                f"{context.conversation}"
            )

        if context.memories:

            sections.append(
                "Relevant memories:\n"
                f"{context.memories}"
            )

        if context.relevant_knowledge:

            sections.append(
                "Relevant knowledge:\n"
                f"{context.relevant_knowledge}"
            )

        if context.entities:

            sections.append(
                "Relevant entities:\n"
                f"{context.entities}"
            )

        if context.user_context:

            sections.append(
                "User context:\n"
                f"{context.user_context}"
            )

        if context.personality_context:

            sections.append(
                "Personality context:\n"
                f"{context.personality_context}"
            )

        if context.active_goals:

            sections.append(
                "Active goals:\n"
                f"{context.active_goals}"
            )

        sections.append(
            "Respond naturally and directly to the user."
        )

        return "\n\n".join(sections)