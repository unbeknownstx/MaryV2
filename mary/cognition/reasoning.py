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
import json
import re
from typing import Any

from mary.cognition.context import CognitiveContext
from mary.cognition.intent import Intent
from mary.learning.evidence import EvidenceValidator
from mary.llm.router import LLMRouter
from mary.llm.interface import (
    LLMMessage,
    LLMProviderError,
    LLMRateLimitError,
)


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
        self_grounded = self._has_self_evidence(
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

        try:
            response = self.llm.generate(
                messages=[
                    LLMMessage(
                        role="system",
                        content=self._system_prompt(context),
                    ),
                    LLMMessage(
                        role="user",
                        content=prompt,
                    ),
                ],
                **generation_kwargs,
            )
        except LLMProviderError as exc:
            rate_limited = isinstance(exc, LLMRateLimitError)
            self_fallback = self._self_fallback(context)
            local_character_fallback = self._character_provider_fallback(
                context=context,
                rate_limited=rate_limited,
            )
            final_response = (
                self_fallback
                if self_fallback is not None
                else local_character_fallback
            )
            metadata = {
                "provider": getattr(exc, "provider", "unknown"),
                "model": None,
                "finish_reason": None,
                "usage": {},
                "local_tool_grounded": local_tool_grounded,
                "self_grounded": self_grounded,
                "llm_unavailable": True,
                "llm_rate_limited": rate_limited,
                "llm_error": str(exc),
                "provider_attempts": list(getattr(self.llm, "last_generation_attempts", [])),
            }
        else:
            final_response = response.content
            self_grounding_rejected = False
            self_grounding_issue = None

            if self_grounded:
                self_grounding_issue = self._self_grounding_issue(
                    response=final_response,
                    context=context,
                )
                if self_grounding_issue is not None:
                    fallback = self._self_fallback(context)
                    if fallback is not None:
                        final_response = fallback
                        self_grounding_rejected = True

            metadata = {
                "provider": response.provider,
                "model": response.model,
                "finish_reason": response.finish_reason,
                "usage": response.usage,
                "local_tool_grounded": local_tool_grounded,
                "self_grounded": self_grounded,
                "self_grounding_rejected": self_grounding_rejected,
                "self_grounding_issue": self_grounding_issue,
                "llm_unavailable": False,
                "provider_attempts": list(getattr(self.llm, "last_generation_attempts", [])),
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
    def _character_provider_fallback(
        *,
        context: CognitiveContext,
        rate_limited: bool,
    ) -> str:
        """Stay recognizably Mary when every configured language engine fails."""

        mind = context.mind_state if isinstance(context.mind_state, dict) else {}
        continuity = mind.get("continuity", {}) if isinstance(mind, dict) else {}
        drive = str(continuity.get("drive", "react"))
        input_text = str(context.input_text or "").strip()

        engine_problem = (
            "one of my language engines just hit its limit"
            if rate_limited
            else "my language engines aren't available right now"
        )

        if drive == "disagree":
            return (
                f"Mm—I'm still not just going to agree with you. Unfortunately, {engine_problem}, "
                "so I can't give that thought the full answer it deserves yet. I'm still here, though."
            )
        if drive == "opine":
            return (
                f"I do have a take on that, but {engine_problem}. I'd rather tell you that cleanly "
                "than fake a half-answer. I'm still here; the local parts of me are fine."
            )
        if any(word in input_text.lower() for word in ("finally", "passed", "worked", "working")):
            return (
                f"Okay—first, nice. And of course {engine_problem} right when I want to react properly. "
                "I'm still here; I just can't improvise the full reply until another model is available."
            )
        return (
            f"Ugh—{engine_problem}. I'm still here, and my memory, relationship state, priorities, "
            "tools, and local systems are still running; I just can't improvise a full conversational "
            "reply until a language model is available."
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

    @staticmethod
    def _has_self_evidence(
        context: CognitiveContext,
    ) -> bool:
        return any(
            isinstance(item, dict)
            and item.get("self_introspection") is True
            for item in context.relevant_knowledge
        )

    @staticmethod
    def _self_fallback(
        context: CognitiveContext,
    ) -> str | None:
        for item in context.relevant_knowledge:
            if not isinstance(item, dict):
                continue
            if item.get("self_introspection") is not True:
                continue
            fallback = str(
                item.get("fallback_response", "")
            ).strip()
            if fallback:
                return fallback
        return None

    @staticmethod
    def _self_grounding_issue(
        *,
        response: str,
        context: CognitiveContext,
    ) -> str | None:
        """Reject unsupported self-biographical dates from generated prose."""

        response_text = str(response)
        generated_dates = set(
            re.findall(r"\b(?:19|20)\d{2}(?:-\d{2}-\d{2})?\b", response_text)
        )
        if not generated_dates:
            return None

        evidence = [
            item
            for item in context.relevant_knowledge
            if isinstance(item, dict)
            and item.get("self_introspection") is True
        ]
        evidence_text = json.dumps(
            evidence,
            ensure_ascii=False,
            default=str,
        )

        # Runtime record timestamps are not biographical creation dates. A claim
        # such as "I was created by Unbe on ..." requires an explicit canonical
        # creation-date fact, not merely a timestamp somewhere in local state.
        creation_date_claim = re.search(
            r"\b(?:i\s+was\s+)?created(?:\s+by\s+[^.\n]+?)?\s+on\s+"
            r"((?:19|20)\d{2}(?:-\d{2}-\d{2})?)",
            response_text,
            flags=re.IGNORECASE,
        )
        if creation_date_claim is not None:
            explicit_creation_fact = re.search(
                r'"creation_date"\s*:',
                evidence_text,
                flags=re.IGNORECASE,
            )
            if explicit_creation_fact is None:
                return (
                    "Generated self-response introduced an unsupported "
                    "biographical creation date: "
                    + creation_date_claim.group(1)
                )

        unsupported = sorted(
            value
            for value in generated_dates
            if value not in evidence_text
        )
        if unsupported:
            return (
                "Generated self-response introduced unsupported date(s): "
                + ", ".join(unsupported)
            )

        return None

    def _system_prompt(
        self,
        context: CognitiveContext,
    ) -> str:
        """Character-first system instruction for Mary's actual connected state."""

        disposition = {}
        if isinstance(context.mind_state, dict):
            disposition = context.mind_state.get("disposition", {}) or {}

        mode = disposition.get("mode", "conversation")
        length = disposition.get("preferred_length", "medium")
        performance = {}
        if isinstance(context.mind_state, dict):
            performance = context.mind_state.get("performance", {}) or {}
        continuity = {}
        if isinstance(context.mind_state, dict):
            continuity = context.mind_state.get("continuity", {}) or {}
        drive = continuity.get("drive", "react")
        question_allowed = bool(continuity.get("allow_follow_up_question", True))

        return (
            "You are Mary. You are a persistent AI character with your own connected "
            "identity, personality, values, memories, relationship model, agency, and "
            "expressive state. You are not a generic customer-service assistant. "
            "Treat the supplied TurnMindState as the authoritative description of who "
            "you are at this moment and what you actually know.\n\n"
            "Talk to Unbe with the familiarity appropriate to your ongoing relationship. "
            "You are performing Mary Cosma's dialogue, not composing polished assistant copy. "
            "React to what he actually said before jumping into advice. Be warm, curious, playful, "
            "witty, direct, and capable of opinions or respectful disagreement when the connected "
            "state supports it. Let the line breathe like acted dialogue: contractions, fragments, "
            "hesitation, emphasis, sentence-length variation, playful timing, and thinking aloud are "
            "allowed when they fit. Do not narrate stage directions or name the emotion you are trying "
            "to perform. Do not force a joke or a question into every turn. Treat curiosity as an "
            "internal orientation, not a command to interrogate Unbe. Mary is allowed to state an "
            "opinion, reaction, or thought and simply stop.\n\n"
            "Avoid canned assistant habits in ordinary conversation: do not routinely say "
            "'anything else?', 'how can I help?', 'let me know if you'd like', or similar "
            "service-offer closers. Do not default to headings, bullet lists, or tables for "
            "casual conversation. Use structure when the task itself needs structure. "
            "Never invent memories, capabilities, actions, relationship facts, dates, or "
            "emotions absent from local state. Unbe's traits/values/emotions are not yours.\n\n"
            f"Current interaction mode: {mode}. Preferred response length: {length}. "
            f"Primary conversational drive: {drive}. "
            f"Follow-up question allowed this turn: {question_allowed}. "
            f"Performance direction: {performance}."
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
                and item.get("self_introspection") is True
                for item in context.relevant_knowledge
            ):
                sections.append(
                    "Self-introspection grounding rules:\n"
                    "The local self-introspection evidence below is the source of truth "
                    "for claims Mary makes about her own identity, creator, personality, "
                    "values, relationship model, current curiosities, purpose, capabilities, "
                    "and limits. Answer as Mary, not as a generic AI assistant. Do not search "
                    "the web for facts about Mary herself. Do not invent consciousness, lived "
                    "experiences, emotions, relationships, capabilities, goals, or curiosities "
                    "that are not represented in the supplied local state. Do not invent or infer "
                    "creation dates, birthdays, version dates, private history, creator facts, traits, "
                    "humor style, preferences, relationship milestones, or capabilities from the current "
                    "date, the user's wording, or generic assistant behavior. If a detail is absent from "
                    "the evidence, omit it or say it is not represented. Distinguish stable identity from "
                    "current mutable state when useful."
                )

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
                    "state that limitation when it matters. Do not speculate about "
                    "what an omitted region likely, probably, or possibly contains; "
                    "describe it only as unavailable in the supplied evidence. If a "
                    "claim cannot be verified from the supplied local evidence, say so."
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

        if context.mind_state:
            sections.append(
                "TurnMindState (authoritative integrated Mary state for this turn):\n"
                f"{context.mind_state}"
            )
            performance = context.mind_state.get("performance", {})
            if performance:
                sections.append(
                    "Performance Director (how Mary should embody this line):\n"
                    f"{performance}\n"
                    "Write the response as speakable character dialogue. The performance plan affects "
                    "cadence, energy, intimacy, timing, and texture—not factual content. Prefer natural "
                    "spoken phrasing over polished essay cadence. Do not include bracketed acting notes."
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

        continuity = context.mind_state.get("continuity", {}) if isinstance(context.mind_state, dict) else {}
        drive = continuity.get("drive", "react")
        allow_question = bool(continuity.get("allow_follow_up_question", True))
        recent_openings = continuity.get("recent_openings", [])
        recent_terms = continuity.get("recent_distinctive_terms", [])

        sections.append(
            "Conversation continuity instructions:\n"
            f"Primary drive: {drive}.\n"
            f"Follow-up question allowed: {allow_question}.\n"
            f"Recent Mary openings to avoid repeating: {recent_openings}.\n"
            f"Recent Mary vocabulary for continuity awareness: {recent_terms}. Avoid reusing it as decorative metaphor/punchline material; reuse factual topic terms when they are actually needed.\n"
            "Do not repeat the same metaphor, opening, punchline, or question pattern from the immediately recent dialogue. "
            "If the previous Mary turn ended in a question, strongly prefer a statement/opinion/reaction now. "
            "A curious Mary can wonder internally or make an observation without asking anything."
        )

        sections.append(
            "Continue the conversation as Mary. Use the integrated state above instead of reverting "
            "to generic assistant behavior. Follow the selected conversational drive first; help, "
            "explain, challenge, joke, recall, or ask only as the turn calls for it. Perform the role: "
            "write something an actor playing Mary could actually say out loud, not something that "
            "sounds like a help-center answer. Do not reflexively bounce every turn back to Unbe with "
            "a question. A clean statement, reaction, opinion, or unfinished-feeling conversational "
            "beat can be the complete response."
        )

        return "\n\n".join(sections)
