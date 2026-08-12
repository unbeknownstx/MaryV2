"""
MaryV2 Cognitive Orchestrator

The orchestrator coordinates Mary's cognitive systems.

It is intentionally NOT a replacement for those systems.

The orchestrator:
    1. Creates cognitive context.
    2. Receives or determines intent.
    3. Runs reasoning.
    4. Runs reflection.
    5. Produces a structured cognitive-cycle result.

Future systems such as memory, personality, relationship, knowledge,
tools, learning, and agency can be injected into the cognitive cycle
without turning this file into a monolithic "brain".
"""

from dataclasses import dataclass, field
from typing import Any

from mary.cognition.context import CognitiveContext
from mary.cognition.intent import Intent, IntentType
from mary.cognition.reasoning import (
    ReasoningEngine,
    ReasoningResult,
)
from mary.cognition.reflection import (
    ReflectionDecision,
    ReflectionEngine,
    ReflectionResult,
)


@dataclass
class CognitiveCycleResult:
    """
    Complete result of one cognitive cycle.
    """

    context: CognitiveContext

    intent: Intent | None

    reasoning: ReasoningResult

    reflection: ReflectionResult

    final_response: str

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert the complete cognitive cycle into a dictionary."""

        return {
            "context": self.context.to_dict(),
            "intent": (
                self.intent.to_dict()
                if self.intent is not None
                else None
            ),
            "reasoning": self.reasoning.to_dict(),
            "reflection": self.reflection.to_dict(),
            "final_response": self.final_response,
            "metadata": self.metadata,
        }


class CognitiveOrchestrator:
    """
    Coordinates Mary's cognition pipeline.
    """

    def __init__(
        self,
        reasoning_engine: ReasoningEngine,
        reflection_engine: ReflectionEngine,
    ) -> None:

        self.reasoning_engine = reasoning_engine
        self.reflection_engine = reflection_engine

    def process(
        self,
        input_text: str,
        intent: Intent | None = None,
        *,
        conversation: list[dict[str, Any]] | None = None,
        memories: list[Any] | None = None,
        knowledge: list[Any] | None = None,
        entities: list[Any] | None = None,
        user_context: dict[str, Any] | None = None,
        personality_context: dict[str, Any] | None = None,
        active_goals: list[Any] | None = None,
    ) -> CognitiveCycleResult:
        """
        Run one complete cognitive cycle.
        """

        context = CognitiveContext(
            input_text=input_text,
        )

        if conversation:

            context.conversation.extend(
                conversation
            )

        if memories:

            context.memories.extend(
                memories
            )

        if knowledge:

            context.relevant_knowledge.extend(
                knowledge
            )

        if entities:

            context.entities.extend(
                entities
            )

        if user_context:

            context.user_context.update(
                user_context
            )

        if personality_context:

            context.personality_context.update(
                personality_context
            )

        if active_goals:

            context.active_goals.extend(
                active_goals
            )

        if intent is None:

            intent = self._basic_intent_detection(
                input_text
            )

        reasoning = self.reasoning_engine.reason(
            context=context,
            intent=intent,
        )

        reflection = self.reflection_engine.reflect(
            context=context,
            reasoning=reasoning,
            intent=intent,
        )

        final_response = self._select_response(
            reasoning=reasoning,
            reflection=reflection,
        )

        return CognitiveCycleResult(
            context=context,
            intent=intent,
            reasoning=reasoning,
            reflection=reflection,
            final_response=final_response,
        )

    def _basic_intent_detection(
        self,
        input_text: str,
    ) -> Intent:
        """
        Temporary deterministic intent detection.

        This is intentionally simple.

        The dedicated intent system can later replace this with a hybrid
        rule/model approach without changing the orchestrator interface.
        """

        text = input_text.strip()

        if not text:

            return Intent(
                intent_type=IntentType.UNKNOWN,
                confidence=1.0,
                description="Empty input.",
                source="basic_detector",
            )

        lowered = text.lower()

        if lowered.endswith("?"):

            return Intent(
                intent_type=IntentType.QUESTION,
                confidence=0.8,
                description="Input appears to be a question.",
                source="basic_detector",
            )

        if lowered.startswith(
            (
                "please ",
                "do ",
                "make ",
                "create ",
                "find ",
                "tell me ",
            )
        ):

            return Intent(
                intent_type=IntentType.REQUEST,
                confidence=0.7,
                description="Input appears to contain a request.",
                source="basic_detector",
            )

        if "goal" in lowered:

            return Intent(
                intent_type=IntentType.GOAL,
                confidence=0.8,
                description="Input appears to concern a goal.",
                source="basic_detector",
            )

        return Intent(
            intent_type=IntentType.CONVERSATION,
            confidence=0.6,
            description="Input appears to be general conversation.",
            source="basic_detector",
        )

    def _select_response(
        self,
        reasoning: ReasoningResult,
        reflection: ReflectionResult,
    ) -> str:
        """
        Determine the response produced by the cognitive cycle.

        For the initial V2 implementation, accepted and revised reasoning
        both return the reasoning response.

        Revision loops will be added once the cognitive cycle has been
        validated end-to-end.
        """

        if reflection.decision == ReflectionDecision.ESCALATE:

            return reasoning.response

        return reasoning.response