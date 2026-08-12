"""
MaryV2 Reflection System

Reflection evaluates the result of a cognitive cycle.

Reflection does not replace reasoning.

Reasoning asks:
    "What should Mary say or do?"

Reflection asks:
    "Is this reasoning/result good enough?"

This creates the foundation for future:
    - self-evaluation
    - response revision
    - uncertainty handling
    - learning from mistakes
    - goal evaluation
    - autonomous improvement
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from mary.cognition.context import CognitiveContext
from mary.cognition.intent import Intent
from mary.cognition.reasoning import ReasoningResult
from mary.llm.router import LLMRouter


class ReflectionDecision(str, Enum):
    """
    Decision produced by the reflection system.
    """

    ACCEPT = "accept"
    REVISE = "revise"
    ESCALATE = "escalate"


@dataclass
class ReflectionResult:
    """
    Structured result of a reflection cycle.
    """

    decision: ReflectionDecision

    confidence: float = 1.0

    assessment: str = ""

    issues: list[str] = field(
        default_factory=list
    )

    suggestions: list[str] = field(
        default_factory=list
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the reflection result into a serializable dictionary.
        """

        return {
            "decision": self.decision.value,
            "confidence": self.confidence,
            "assessment": self.assessment,
            "issues": self.issues,
            "suggestions": self.suggestions,
            "metadata": self.metadata,
        }


class ReflectionEngine:
    """
    Evaluates reasoning results.

    The reflection engine is intentionally independent from the final
    response system and from any specific LLM provider.
    """

    def __init__(
        self,
        llm: LLMRouter,
    ) -> None:

        self.llm = llm

    def reflect(
        self,
        context: CognitiveContext,
        reasoning: ReasoningResult,
        intent: Intent | None = None,
    ) -> ReflectionResult:
        """
        Evaluate a reasoning result.
        """

        prompt = self._build_prompt(
            context=context,
            reasoning=reasoning,
            intent=intent,
        )

        response = self.llm.generate(
            prompt=prompt,
        )

        return self._parse_response(
            response=response,
        )

    def _build_prompt(
        self,
        context: CognitiveContext,
        reasoning: ReasoningResult,
        intent: Intent | None,
    ) -> str:
        """
        Build the reflection prompt.
        """

        intent_text = (
            intent.intent_type.value
            if intent is not None
            else "unknown"
        )

        return (
            "Evaluate Mary's proposed response.\n\n"

            f"User input:\n"
            f"{context.input_text}\n\n"

            f"Detected intent:\n"
            f"{intent_text}\n\n"

            f"Proposed response:\n"
            f"{reasoning.response}\n\n"

            "Evaluate whether the response is:\n"
            "1. Relevant to the user's input.\n"
            "2. Consistent with the available context.\n"
            "3. Clear and useful.\n"
            "4. Appropriate for the conversation.\n\n"

            "Return a concise evaluation using this format:\n"
            "DECISION: ACCEPT, REVISE, or ESCALATE\n"
            "CONFIDENCE: 0.0 to 1.0\n"
            "ASSESSMENT: brief explanation\n"
            "ISSUES: comma-separated issues or NONE\n"
            "SUGGESTIONS: comma-separated suggestions or NONE"
        )

    def _parse_response(
        self,
        response: str,
    ) -> ReflectionResult:
        """
        Parse the LLM's reflection into a structured result.

        The parser is deliberately defensive because an LLM may not always
        follow the requested format perfectly.
        """

        decision = ReflectionDecision.ACCEPT
        confidence = 0.5
        assessment = ""
        issues: list[str] = []
        suggestions: list[str] = []

        lines = response.splitlines()

        for line in lines:

            stripped = line.strip()

            if not stripped:
                continue

            if ":" not in stripped:
                continue

            key, value = stripped.split(
                ":",
                1,
            )

            key = key.strip().upper()
            value = value.strip()

            if key == "DECISION":

                normalized = value.upper()

                if "REVISE" in normalized:
                    decision = ReflectionDecision.REVISE

                elif "ESCALATE" in normalized:
                    decision = ReflectionDecision.ESCALATE

                else:
                    decision = ReflectionDecision.ACCEPT

            elif key == "CONFIDENCE":

                try:

                    confidence = float(
                        value
                    )

                    confidence = max(
                        0.0,
                        min(
                            1.0,
                            confidence,
                        ),
                    )

                except ValueError:

                    confidence = 0.5

            elif key == "ASSESSMENT":

                assessment = value

            elif key == "ISSUES":

                if value.upper() != "NONE":

                    issues = [
                        item.strip()
                        for item in value.split(",")
                        if item.strip()
                    ]

            elif key == "SUGGESTIONS":

                if value.upper() != "NONE":

                    suggestions = [
                        item.strip()
                        for item in value.split(",")
                        if item.strip()
                    ]

        return ReflectionResult(
            decision=decision,
            confidence=confidence,
            assessment=assessment,
            issues=issues,
            suggestions=suggestions,
        )