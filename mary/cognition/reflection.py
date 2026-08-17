"""
MaryV2 Reflection System

Reflection evaluates the result of a cognitive cycle.

Reflection does not replace reasoning.

Reasoning asks:
    "What should Mary say or do?"

Reflection asks:
    "Is this reasoning/result good enough?"
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from mary.cognition.context import CognitiveContext
from mary.cognition.intent import Intent
from mary.cognition.reasoning import ReasoningResult
from mary.llm.router import LLMRouter
from mary.llm.interface import LLMMessage


class ReflectionDecision(str, Enum):
    """Decision produced by the reflection system."""

    ACCEPT = "accept"
    REVISE = "revise"
    ESCALATE = "escalate"


@dataclass
class ReflectionResult:
    """Structured result of a reflection cycle."""

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
        """Convert the reflection result into a serializable dictionary."""

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
        """Evaluate a reasoning result."""

        # Research reasoning has already passed through the evidence boundary.
        # Reusing that result avoids spending another LLM request merely to
        # restate an audit that cannot change V2's selected response anyway.
        evidence = reasoning.metadata.get("evidence_validation")
        if isinstance(evidence, dict):
            validated = bool(evidence.get("validated"))
            failure = evidence.get("failure")

            return ReflectionResult(
                decision=ReflectionDecision.ACCEPT,
                confidence=0.95 if validated else 0.65,
                assessment=(
                    "Research response passed evidence-grounded synthesis."
                    if validated
                    else "Research response used the safe evidence-only fallback."
                ),
                issues=(
                    []
                    if validated
                    else [str(failure or "evidence synthesis fallback")]
                ),
                metadata={
                    "mode": "evidence_validation_reuse",
                    "validated": validated,
                },
            )

        if reasoning.metadata.get("local_tool_grounded") is True:
            return ReflectionResult(
                decision=ReflectionDecision.ACCEPT,
                confidence=0.95,
                assessment=(
                    "Local tool response was generated from bounded source evidence "
                    "and grounding rules."
                ),
                metadata={
                    "mode": "local_tool_grounding_reuse",
                },
            )

        prompt = self._build_prompt(
            context=context,
            reasoning=reasoning,
            intent=intent,
        )

        response = self.llm.generate(
            messages=[
                LLMMessage(
                    role="system",
                    content=(
                        "You are Mary's reflection system. "
                        "Evaluate the proposed response objectively."
                    ),
                ),
                LLMMessage(
                    role="user",
                    content=prompt,
                ),
            ],
            max_tokens=512,
        )

        result = self._parse_response(
            response=response.content,
        )

        result.metadata.update({
            "provider": response.provider,
            "model": response.model,
            "finish_reason": response.finish_reason,
            "usage": response.usage,
        })

        return result

    def _build_prompt(
        self,
        context: CognitiveContext,
        reasoning: ReasoningResult,
        intent: Intent | None,
    ) -> str:

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

        decision = ReflectionDecision.ACCEPT
        confidence = 0.5
        assessment = ""
        issues: list[str] = []
        suggestions: list[str] = []

        lines = response.splitlines()

        for line in lines:

            stripped = line.strip()

            if not stripped or ":" not in stripped:
                continue

            key, value = stripped.split(
                ":",
                1,
            )

            key = key.strip().upper()
            value = value.strip()

            if key == "DECISION":

                normalized = value.upper()

                if "ESCALATE" in normalized:
                    decision = ReflectionDecision.ESCALATE

                elif "REVISE" in normalized:
                    decision = ReflectionDecision.REVISE

                else:
                    decision = ReflectionDecision.ACCEPT

            elif key == "CONFIDENCE":

                try:
                    confidence = max(
                        0.0,
                        min(
                            1.0,
                            float(value),
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