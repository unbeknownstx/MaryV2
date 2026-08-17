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

For externally researched answers, reasoning also performs an evidence audit
before returning its response. The audit can only use temporary research
evidence already supplied in cognitive context.
"""

from dataclasses import dataclass, field
from typing import Any

from mary.cognition.context import CognitiveContext
from mary.cognition.intent import Intent
from mary.learning.evidence import EvidenceValidator
from mary.llm.router import LLMRouter
from mary.llm.interface import LLMMessage


@dataclass
class ReasoningResult:
    """Structured result produced by Mary's reasoning system."""

    response: str
    confidence: float = 1.0
    reasoning_type: str = "general"
    intent: Intent | None = None
    tool_required: bool = False
    action_required: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
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
        evidence_validator: EvidenceValidator | None = None,
    ) -> None:
        self.llm = llm
        self.evidence_validator = (
            evidence_validator
            if evidence_validator is not None
            else EvidenceValidator()
        )

    def reason(
        self,
        context: CognitiveContext,
        intent: Intent | None = None,
    ) -> ReasoningResult:
        """Process cognitive context and produce a reasoning result."""

        # Research uses a single evidence-grounded synthesis call. Source
        # resolution, grounding, and evaluation are deterministic before this
        # point, so a separate free-form draft plus second LLM audit wastes a
        # tight provider TPM budget without improving the V2 boundary.
        if self._has_research_evidence(context):
            validation = self.evidence_validator.synthesize(
                query=context.input_text,
                knowledge=context.relevant_knowledge,
                llm=self.llm,
            )

            return ReasoningResult(
                response=validation.response,
                intent=intent,
                reasoning_type=(
                    intent.intent_type.value
                    if intent is not None
                    else "general"
                ),
                metadata={
                    "provider": validation.metadata.get("provider"),
                    "model": validation.metadata.get("model"),
                    "finish_reason": validation.metadata.get("finish_reason"),
                    "usage": validation.metadata.get("usage", {}),
                    "evidence_validation": validation.to_dict(),
                    "research_mode": "single_pass_grounded_synthesis",
                },
            )

        local_tool_grounded = self._has_local_tool_evidence(
            context
        )

        prompt = self._build_prompt(
            context=context,
            intent=intent,
        )

        generation_kwargs: dict[str, Any] = {}
        if local_tool_grounded:
            # Keep local grounded analysis compact enough to coexist with the
            # exact source evidence under tight provider TPM limits.
            generation_kwargs["max_tokens"] = 1_400

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
            **generation_kwargs,
        )

        final_response = response.content
        metadata: dict[str, Any] = {
            "provider": response.provider,
            "model": response.model,
            "finish_reason": response.finish_reason,
            "usage": response.usage,
            "local_tool_grounded": local_tool_grounded,
        }

        return ReasoningResult(
            response=final_response,
            intent=intent,
            reasoning_type=(
                intent.intent_type.value
                if intent is not None
                else "general"
            ),
            metadata=metadata,
        )

    @staticmethod
    def _has_research_evidence(
        context: CognitiveContext,
    ) -> bool:
        return any(
            isinstance(item, dict)
            and isinstance(
                item.get("research_grounding"),
                dict,
            )
            for item in context.relevant_knowledge
        )

    @staticmethod
    def _has_local_tool_evidence(
        context: CognitiveContext,
    ) -> bool:
        return any(
            isinstance(item, dict)
            and item.get("local_tool") is True
            for item in context.relevant_knowledge
        )

    def _build_prompt(
        self,
        context: CognitiveContext,
        intent: Intent | None,
    ) -> str:
        """Build the cognitive prompt sent to the LLM."""

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
            if any(
                isinstance(item, dict)
                and item.get("local_tool") is True
                for item in context.relevant_knowledge
            ):
                sections.append(
                    "Local tool grounding rules:\n"
                    "The local tool output below is the source of truth for "
                    "claims about the inspected file or workspace. Do not fill "
                    "missing implementation details from generic Python patterns "
                    "or from what a similarly named class would usually do. For "
                    "code analysis, distinguish exact observed structure/source "
                    "from inference. Never invent imports, attributes, method "
                    "signatures, persistence files, side effects, data structures, "
                    "or warnings that are not shown by the tool evidence. If the "
                    "tool marks source as truncated or says the middle was omitted, "
                    "state that limitation when it matters. If a claim cannot be "
                    "verified from the supplied local evidence, say so."
                )

            if any(
                isinstance(item, dict)
                and "research_grounding" in item
                for item in context.relevant_knowledge
            ):
                sections.append(
                    "Research grounding rules:\n"
                    "The external material below is temporary research evidence, "
                    "not automatically trusted memory or permanent knowledge. "
                    "Base factual claims only on evidence actually present in the "
                    "supplied sources. Prefer higher-grounding and primary/official "
                    "sources. For latest/current questions, prefer newer dated evidence "
                    "and do not present stale historical material as current. Treat "
                    "search snippets as incomplete evidence: do not invent missing "
                    "details. If sources conflict or do not support a confident answer, "
                    "state that uncertainty explicitly. Your draft will be audited "
                    "against this evidence before it is returned."
                )

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