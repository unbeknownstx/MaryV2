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
import re
from typing import Any

from mary.cognition.context import CognitiveContext
from mary.cognition.intent import Intent
from mary.cognition.reasoning import ReasoningResult
from mary.llm.router import LLMRouter
from mary.llm.interface import LLMMessage, LLMProviderError


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

    revised_response: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert the reflection result into a serializable dictionary."""

        return {
            "decision": self.decision.value,
            "confidence": self.confidence,
            "assessment": self.assessment,
            "issues": self.issues,
            "suggestions": self.suggestions,
            "metadata": self.metadata,
            "revised_response": self.revised_response,
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

        if reasoning.metadata.get("llm_unavailable") is True:
            return ReflectionResult(
                decision=ReflectionDecision.ACCEPT,
                confidence=1.0,
                assessment=(
                    "Reasoning used Mary's deterministic provider-unavailable "
                    "fallback; no second LLM call should be attempted."
                ),
                metadata={
                    "mode": "llm_unavailable_fallback",
                    "rate_limited": bool(
                        reasoning.metadata.get("llm_rate_limited")
                    ),
                },
            )

        if reasoning.metadata.get("self_grounded") is True:
            return ReflectionResult(
                decision=ReflectionDecision.ACCEPT,
                confidence=0.95,
                assessment=(
                    "Self-introspection response was grounded in Mary's connected local state."
                ),
                metadata={
                    "mode": "self_introspection_grounding_reuse",
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

        issues = self._character_audit(
            context=context,
            reasoning=reasoning,
            intent=intent,
        )

        if not issues:
            return ReflectionResult(
                decision=ReflectionDecision.ACCEPT,
                confidence=0.94,
                assessment=(
                    "Response passed Mary's local character/continuity audit."
                ),
                metadata={
                    "mode": "local_character_audit",
                    "llm_calls": 0,
                },
            )

        prompt = self._build_revision_prompt(
            context=context,
            reasoning=reasoning,
            intent=intent,
            issues=issues,
        )

        try:
            response = self.llm.generate(
                messages=[
                    LLMMessage(
                        role="system",
                        content=(
                            "You are Mary's response editor. Preserve factual meaning and "
                            "grounding, but rewrite the reply so it sounds like Mary rather "
                            "than a generic assistant. Return only the revised reply."
                        ),
                    ),
                    LLMMessage(
                        role="user",
                        content=prompt,
                    ),
                ],
                max_tokens=700,
            )
        except LLMProviderError as exc:
            return ReflectionResult(
                decision=ReflectionDecision.ACCEPT,
                confidence=0.70,
                assessment=(
                    "Character audit found issues, but revision provider was unavailable; "
                    "the grounded original response was preserved."
                ),
                issues=issues,
                metadata={
                    "mode": "character_revision_unavailable",
                    "llm_calls": 1,
                    "llm_error": str(exc),
                },
            )

        revised = str(response.content or "").strip()
        if not revised:
            return ReflectionResult(
                decision=ReflectionDecision.ACCEPT,
                confidence=0.72,
                assessment="Revision returned empty text; original response preserved.",
                issues=issues,
                metadata={
                    "mode": "character_revision_empty",
                    "llm_calls": 1,
                },
            )

        return ReflectionResult(
            decision=ReflectionDecision.REVISE,
            confidence=0.90,
            assessment="Response was revised to better match Mary's connected character state.",
            issues=issues,
            suggestions=[
                "Preserve grounding while sounding more like Mary."
            ],
            revised_response=revised,
            metadata={
                "mode": "character_revision",
                "provider": response.provider,
                "model": response.model,
                "finish_reason": response.finish_reason,
                "usage": response.usage,
                "llm_calls": 1,
            },
        )

    def _character_audit(
        self,
        *,
        context: CognitiveContext,
        reasoning: ReasoningResult,
        intent: Intent | None,
    ) -> list[str]:
        """Find obvious assistant-shaped habits without another model call."""

        text = str(reasoning.response or "").strip()
        if not text:
            return ["Response is empty."]

        mind = context.mind_state if isinstance(context.mind_state, dict) else {}
        disposition = mind.get("disposition", {}) if isinstance(mind, dict) else {}
        mode = str(disposition.get("mode", "conversation"))
        conversational = mode in {
            "relational_conversation",
            "conversation",
            "creative_collaboration",
        }

        issues: list[str] = []
        lowered = text.lower()
        canned = (
            "how can i assist",
            "how can i help you today",
            "anything else you'd like",
            "anything else you would like",
            "let me know if you'd like",
            "let me know if you would like",
            "feel free to",
            "what can i do for you today",
            "great to hear that!",
            "i'm here to help",
            "i am here to help",
        )
        if any(phrase in lowered for phrase in canned):
            issues.append("Uses canned generic-assistant/helpdesk phrasing.")

        if lowered.startswith(("as an ai", "as an artificial intelligence")):
            issues.append("Leads with generic AI-assistant identity framing.")

        if conversational and (text.count("\n-") >= 3 or text.count("\n*") >= 3):
            short_input = len(context.input_text.split()) <= 18
            if short_input:
                issues.append("Over-formats a casual conversational reply as a list.")

        if conversational and "|" in text and text.count("|") >= 6 and len(context.input_text.split()) <= 18:
            issues.append("Uses a table for a casual conversational reply.")

        continuity = mind.get("continuity", {}) if isinstance(mind, dict) else {}
        recent_mary = [
            str(item).strip()
            for item in continuity.get("recent_mary_responses", [])
            if str(item).strip()
        ]

        if not bool(continuity.get("allow_follow_up_question", True)) and "?" in text:
            issues.append("Adds another follow-up question after Mary has already been asking questions recently.")

        current_opening = self._opening_signature(text)
        recent_openings = {
            str(item).strip().lower()
            for item in continuity.get("recent_openings", [])
            if str(item).strip()
        }
        if current_opening and current_opening in recent_openings:
            issues.append("Repeats Mary's recent opening/response pattern.")

        return issues

    @staticmethod
    def _opening_signature(text: str) -> str:
        words = re.findall(r"[a-z0-9']+", str(text).lower())
        return " ".join(words[:4])

    @staticmethod
    def _content_terms(text: str) -> list[str]:
        stop = {
            "the", "and", "that", "this", "with", "your", "you", "from", "have",
            "just", "like", "really", "about", "what", "when", "where", "which",
            "would", "could", "should", "there", "their", "they", "them", "think",
            "sounds", "maybe", "thing", "things", "mary", "unbe",
        }
        return [
            word for word in re.findall(r"[a-z0-9']+", str(text).lower())
            if len(word) >= 5 and word not in stop
        ]

    def _build_revision_prompt(
        self,
        *,
        context: CognitiveContext,
        reasoning: ReasoningResult,
        intent: Intent | None,
        issues: list[str],
    ) -> str:
        mind = context.mind_state if isinstance(context.mind_state, dict) else {}
        disposition = mind.get("disposition", {}) if isinstance(mind, dict) else {}
        recent = mind.get("conversation", {}) if isinstance(mind, dict) else {}
        relationship = mind.get("relationship", {}) if isinstance(mind, dict) else {}
        emotion = mind.get("emotion", {}) if isinstance(mind, dict) else {}
        continuity = mind.get("continuity", {}) if isinstance(mind, dict) else {}

        return (
            "Rewrite Mary's proposed response. Preserve all factual content and any "
            "grounding/tool limitations. Do not add new facts.\n\n"
            f"Unbe's current input:\n{context.input_text}\n\n"
            f"Detected intent: {intent.intent_type.value if intent else 'unknown'}\n\n"
            f"Issues found: {issues}\n\n"
            f"Mary response disposition: {disposition}\n\n"
            f"Relationship context: {relationship}\n\n"
            f"Current emotion: {emotion}\n\n"
            f"Recent conversational state: {recent}\n\n"
            f"Continuity/drive state: {continuity}\n\n"
            f"Proposed response:\n{reasoning.response}\n\n"
            "Make it conversational, specific, and recognizably Mary. Follow the selected "
            "conversational drive. React before switching into assistance. Avoid canned "
            "service-offer closers. Do not repeat Mary's recent opening, metaphor, punchline, "
            "or question pattern. If the continuity state disallows a follow-up question, "
            "end naturally with a statement instead. Use no headings/table/list unless the "
            "user's task actually needs structure. Return only the revised reply."
        )

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