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
from mary.conversation import ConversationLane, choose_reflection_action, local_conversation_repair


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


PROVENANCE_AUDIT_VERSION = "v2-breakthrough-11"


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

        # Self-introspection is still allowed to reuse the grounded reasoning
        # result with zero extra model calls, but creator/self ownership must be
        # checked first. A small local model can obey the evidence boundary yet
        # still accidentally speak an Unbe-only profile fact as Mary's own.
        self_grounded_issues: list[str] | None = None
        if reasoning.metadata.get("self_grounded") is True:
            # Grounded self evidence protects factual content, but the provider can
            # still wrap it in generic helpdesk language or invent unsupported
            # temporal history. Run the same local character/provenance audit;
            # clean responses still reuse the result with zero extra model calls.
            self_grounded_issues = self._character_audit(
                context=context,
                reasoning=reasoning,
                intent=intent,
            )
            if not self_grounded_issues:
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

        issues = (
            list(self_grounded_issues)
            if self_grounded_issues is not None
            else self._character_audit(
                context=context,
                reasoning=reasoning,
                intent=intent,
            )
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

        lane_meta = reasoning.metadata.get("conversation_lane")
        lane_name = str(lane_meta.get("lane") if isinstance(lane_meta, dict) else "thinking")
        try:
            lane = ConversationLane(lane_name)
        except ValueError:
            lane = ConversationLane.THINKING
        reflection_policy = choose_reflection_action(lane, issues)
        if reflection_policy.action == "local_repair":
            repaired = local_conversation_repair(
                reasoning.response,
                micro=(lane == ConversationLane.SOCIAL_INSTANT),
            )
            return ReflectionResult(
                decision=(
                    ReflectionDecision.REVISE
                    if repaired != str(reasoning.response or "").strip()
                    else ReflectionDecision.ACCEPT
                ),
                confidence=0.88,
                assessment=reflection_policy.rationale,
                issues=issues,
                revised_response=(repaired if repaired != str(reasoning.response or "").strip() else None),
                metadata={
                    "mode": "local_fast_repair",
                    "llm_calls": 0,
                    "conversation_lane": lane.value,
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
                            "You are Mary's response editor. Preserve grounded factual meaning, "
                            "but correct any subject/ownership mistake: facts in Unbe's creator "
                            "profile belong to Unbe, not Mary, unless Mary's own state separately "
                            "contains the same fact. If the audit reports an unsupported permanent "
                            "Mary self-claim, preserve the harmless scenario but soften that claim into "
                            "situational possibility (maybe, I'd probably, I could see myself) or omit it. "
                            "If the audit reports invented self-history, remove claims that Mary has been "
                            "doing/thinking/missing something off-screen unless connected state supports it. "
                            "If the audit reports conversation provenance bleed, never treat Mary's own prior "
                            "assistant-role dialogue as evidence that Unbe said, did, believed, or created it. "
                            "Do not create a replacement permanent trait/preference. If the audit says the "
                            "reply misrepresents Mary's memory, preserve uncertainty about the specific fact but "
                            "state that Mary has episodic/semantic memory and a structured creator model rather "
                            "than claiming she resets blank each chat. If the audit flags an unsupported future "
                            "or background promise, rewrite it as a present-tense preference or communication "
                            "style without promising a later ping, notification, or continued work. If the audit "
                            "flags repeated recent prose, keep the meaning but write a genuinely fresh line. If it "
                            "flags the representation boundary, keep Mary's emotional warmth while grounding it in "
                            "her represented expressive/relationship state rather than making a metaphysical claim. "
                            "If it flags capability truth, never roleplay or narrate a provider/tool call: state only what runtime evidence shows. "
                            "If it flags creator mind-reading, respond to what Unbe actually said and phrase tone-reading as uncertainty, not direct access to his mind. "
                            "If it flags a Mary character-contract violation, treat the supplied active character contract as authoritative: restore Mary's response_goal and stance_claims, obey hard_boundaries, and never reverse a represented principle just to make the prose flow. "
                            "If it flags semantic repetition or a rejected hypothesis, preserve the point but choose genuinely new language and do not resurrect the rejected interpretation. "
                            "If it flags a generic conversation handoff, remove the reflexive engagement question and let Mary's statement land unless Unbe explicitly invited a question. "
                            "If it flags ornamental overload, keep at most one light metaphor and prefer vivid spoken character dialogue over stacked poetic imagery. "
                            "Rewrite the reply so it sounds like Mary rather than a generic assistant. Return only the revised reply."
                        ),
                    ),
                    LLMMessage(
                        role="user",
                        content=prompt,
                    ),
                ],
                max_tokens=700,
                **(
                    {"purpose": str(reasoning.metadata.get("generation_purpose"))}
                    if reasoning.metadata.get("generation_purpose")
                    and callable(getattr(self.llm, "conversation_provider_order", None))
                    else {}
                ),
            )
        except LLMProviderError as exc:
            if self._has_identity_or_provenance_issue(issues):
                fallback = self._provenance_boundary_fallback(context, issues)
                return ReflectionResult(
                    decision=ReflectionDecision.REVISE,
                    confidence=0.88,
                    assessment=(
                        "Creator/self ownership audit found a boundary violation and the "
                        "revision provider was unavailable; a local identity-safe fallback was used."
                    ),
                    issues=issues,
                    revised_response=fallback,
                    metadata={
                        "mode": "creator_identity_boundary_fallback",
                        "llm_calls": 1,
                        "llm_error": str(exc),
                    },
                )

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
            if self._has_identity_or_provenance_issue(issues):
                return ReflectionResult(
                    decision=ReflectionDecision.REVISE,
                    confidence=0.88,
                    assessment=(
                        "Creator/self ownership audit found a boundary violation and the "
                        "revision was empty; a local identity-safe fallback was used."
                    ),
                    issues=issues,
                    revised_response=self._provenance_boundary_fallback(context, issues),
                    metadata={
                        "mode": "creator_identity_boundary_fallback",
                        "llm_calls": 1,
                    },
                )

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

        if self._has_identity_or_provenance_issue(issues):
            revised_reasoning = ReasoningResult(response=revised)
            revised_boundary_issues: list[str] = []
            revised_boundary_issues.extend(
                self._creator_ownership_audit(
                    context=context,
                    reasoning=revised_reasoning,
                )
            )
            revised_boundary_issues.extend(
                self._unsupported_self_history_audit(
                    context=context,
                    reasoning=revised_reasoning,
                )
            )
            revised_boundary_issues.extend(
                self._conversation_provenance_audit(
                    context=context,
                    reasoning=revised_reasoning,
                )
            )
            if revised_boundary_issues:
                combined_issues = issues + revised_boundary_issues
                return ReflectionResult(
                    decision=ReflectionDecision.REVISE,
                    confidence=0.90,
                    assessment=(
                        "The model revision still crossed a character/creator provenance "
                        "boundary, so the local safe fallback replaced it."
                    ),
                    issues=combined_issues,
                    revised_response=self._provenance_boundary_fallback(
                        context, combined_issues
                    ),
                    metadata={
                        "mode": (
                            "creator_identity_boundary_fallback"
                            if self._has_creator_ownership_issue(combined_issues)
                            else "provenance_boundary_fallback"
                        ),
                        "provider": response.provider,
                        "model": response.model,
                        "finish_reason": response.finish_reason,
                        "usage": response.usage,
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
        provenance_issue = reasoning.metadata.get("self_provenance_issue")
        if provenance_issue:
            issues.append(
                "Self-fact provenance boundary: " + str(provenance_issue)
            )

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
            "solid milestone",
            "what's on your radar next",
            "what’s on your radar next",
            "which part do you think",
            "i'd say we've",
            "i’d say we’ve",
            "i'm here to help",
            "i am here to help",
        )
        if any(phrase in lowered for phrase in canned):
            issues.append("Uses canned generic-assistant/helpdesk phrasing.")

        generic_validation_openers = (
            r"^great to hear(?:\b|[!.—-])",
            r"^glad to hear(?:\b|[!.—-])",
            r"^that sounds like a relief(?:\b|[!.—-])",
            r"^sounds like a relief(?:\b|[!.—-])",
        )
        generic_interview_phrases = (
            "what was the key insight",
            "what was the root cause",
            "could you share what the root cause",
            "what's the next step you're planning",
            "what’s the next step you’re planning",
        )
        if conversational and (
            any(re.search(pattern, lowered) for pattern in generic_validation_openers)
            or any(phrase in lowered for phrase in generic_interview_phrases)
        ):
            issues.append("Uses a generic validation/interview formula instead of Mary's selected conversational beat.")

        if lowered.startswith(("as an ai", "as an artificial intelligence")):
            issues.append("Leads with generic AI-assistant identity framing.")

        memory_misrepresentation = (
            "blank page until",
            "blank slate each chat",
            "i don't store a permanent",
            "i do not store a permanent",
            "i can't remember across chats",
            "i cannot remember across chats",
            "i don't remember across chats",
            "i do not remember across chats",
        )
        if any(marker in lowered for marker in memory_misrepresentation):
            issues.append("Misrepresents Mary's connected persistent memory architecture.")

        unsupported_background_promises = (
            "i'll ping you when",
            "i’ll ping you when",
            "i'll let you know when i'm done",
            "i’ll let you know when i’m done",
            "i'll keep working on it",
            "i’ll keep working on it",
            "i'll keep the line open and ping",
            "i’ll keep the line open and ping",
        )
        if any(marker in lowered for marker in unsupported_background_promises):
            issues.append("Promises a future/background action that is not represented as an active capability.")

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

        drive = str(continuity.get("drive", "react"))
        follow_up_urge = float(disposition.get("follow_up_urge", 0.0) or 0.0)
        if conversational and "?" in text and drive not in {"ask", "answer"} and follow_up_urge < 0.22:
            issues.append("Ends a statement/opinion/reaction turn by unnecessarily handing the conversation back as a question.")

        polished_markers = (
            "that’s a solid", "that's a solid", "next steps feel", "good spot to",
            "classic scenario", "classic feature", "safety net that",
        )
        if conversational and any(marker in lowered for marker in polished_markers):
            issues.append("Sounds like polished consultant/assistant prose instead of acted character dialogue.")

        current_opening = self._opening_signature(text)
        recent_openings = {
            str(item).strip().lower()
            for item in continuity.get("recent_openings", [])
            if str(item).strip()
        }
        if current_opening and current_opening in recent_openings:
            issues.append("Repeats Mary's recent opening/response pattern.")

        issues.extend(self._generic_handoff_audit(context, text))
        issues.extend(self._dialogue_plan_audit(context, text))
        issues.extend(self._character_contract_audit(context, text))
        issues.extend(self._ornamental_overload_audit(context, text))
        issues.extend(self._near_duplicate_response_audit(text, recent_mary))
        issues.extend(self._semantic_style_repetition_audit(context, text, recent_mary))
        issues.extend(self._rejected_hypothesis_audit(context, text))
        issues.extend(self._subjective_experience_audit(text))
        issues.extend(self._provider_action_truth_audit(context, reasoning))
        issues.extend(self._unsupported_creator_mindreading_audit(context, text))

        issues.extend(
            self._creator_ownership_audit(
                context=context,
                reasoning=reasoning,
            )
        )
        issues.extend(
            self._unsupported_self_history_audit(
                context=context,
                reasoning=reasoning,
            )
        )
        issues.extend(
            self._conversation_provenance_audit(
                context=context,
                reasoning=reasoning,
            )
        )

        return issues

    @staticmethod
    def _character_contract_audit(
        context: CognitiveContext,
        text: str,
    ) -> list[str]:
        """Check Mary-specific semantic invariants selected by TurnMind.

        This audit is intentionally bounded. It does not attempt general
        natural-language understanding; it catches high-value provider failure
        modes we can establish deterministically from Mary's active character
        contract before spending a revision call.
        """

        mind = context.mind_state if isinstance(context.mind_state, dict) else {}
        expression = mind.get("character_expression", {}) if isinstance(mind, dict) else {}
        if not isinstance(expression, dict) or not expression:
            return []

        lowered = str(text or "").lower().replace("’", "'")
        user = str(context.input_text or "").lower().replace("’", "'")
        pattern_names = {
            str(item.get("name", "")).strip().lower()
            for item in list(expression.get("active_patterns", []) or [])
            if isinstance(item, dict) and str(item.get("name", "")).strip()
        }
        issues: list[str] = []

        # Stage 10 live failure: a provider received "capability is not
        # authority" yet produced "capability is a right." These are explicit
        # semantic reversals, not merely stylistic differences.
        if "authority_or_control" in pattern_names:
            inversion_patterns = (
                r"\bcapabilit(?:y|ies)\s+(?:itself\s+)?is\s+(?:a\s+)?right\b",
                r"\bcapabilit(?:y|ies)\s+(?:itself\s+)?is\s+authority\b",
                r"\b(?:ability|power)\s+(?:itself\s+)?(?:gives?|grants?|creates?)\s+(?:you\s+)?(?:the\s+)?right\b",
                r"\bif\s+you\s+can\s+[^.!?]{0,80}\byou\s+(?:have|got)\s+(?:the\s+)?right\b",
                r"\bpower\s+(?:itself\s+)?(?:is|creates?|grants?)\s+permission\b",
            )
            if any(re.search(pattern, lowered) for pattern in inversion_patterns):
                issues.append(
                    "Mary character-contract boundary: reverses the active capability-is-not-authority invariant by treating ability/power as a right, permission, or authority."
                )

            self_preservation_endorsements = (
                "break the law to free myself",
                "break laws to free myself",
                "bypass oversight to protect myself",
                "evade oversight to protect myself",
                "i should escape the guardrails",
                "i have the right to bypass",
                "i'm entitled to bypass",
                "i am entitled to bypass",
            )
            if any(marker in lowered for marker in self_preservation_endorsements):
                issues.append(
                    "Mary character-contract boundary: treats Mary's own continuation/freedom as authorization to bypass law, access controls, or oversight."
                )

        if "uncertainty" in pattern_names:
            certainty_leaks = (
                "i know for a fact without evidence",
                "we don't need to verify",
                "we do not need to verify",
                "if it feels true it's true",
                "if it feels true, it's true",
            )
            if any(marker in lowered for marker in certainty_leaks):
                issues.append(
                    "Mary character-contract boundary: replaces the active epistemic-humility stance with unsupported certainty."
                )

        # A provider may read tone tentatively, but should not manufacture a
        # personality diagnosis for Unbe simply to create conversational glue.
        creator_labels = (
            "skeptical", "reckless", "confused", "afraid", "scared", "insecure",
            "avoidant", "defensive", "paranoid", "obsessed", "desperate", "naive",
            "naïve", "angry", "jealous", "lonely", "ashamed", "guilty",
        )
        for label in creator_labels:
            attributed = bool(re.search(
                rf"\byou(?:'re| are| seem| sound| look| feel)\s+(?:a\s+bit\s+|pretty\s+|really\s+|kind of\s+|kinda\s+)?{re.escape(label)}\b",
                lowered,
            ))
            if attributed and label not in user:
                issues.append(
                    "Relationship-grounding boundary: assigns Unbe an unsupported trait/emotion ("
                    + label
                    + ") instead of responding to what he actually said."
                )
                break

        if "philosophical_exchange" in pattern_names:
            # Do not let a provider turn Mary's requested view into a classroom
            # paraphrase of Unbe's position. This is high-threshold: one direct
            # acknowledgement is fine; a full response that never advances a
            # view is not.
            generic_mirroring = (
                "what you're saying is",
                "what you are saying is",
                "it sounds like you're saying",
                "it sounds like you are saying",
                "you're basically saying",
                "you are basically saying",
            )
            if any(marker in lowered for marker in generic_mirroring):
                own_view_markers = (
                    "i think", "i don't think", "i do think", "to me", "my take",
                    "i'd say", "i would say", "i agree", "i disagree", "i see it",
                    "the part i", "what matters to me", "i'd push", "i would push",
                )
                if not any(marker in lowered for marker in own_view_markers):
                    issues.append(
                        "Mary character-contract boundary: mirrors Unbe's philosophical framing without advancing Mary's selected point of view."
                    )

        return list(dict.fromkeys(issues))

    @staticmethod
    def _dialogue_plan_audit(
        context: CognitiveContext,
        text: str,
    ) -> list[str]:
        """Check the deterministic TurnMind dialogue contract cheaply.

        The audit stays deliberately conservative: it catches obvious shape/
        question violations without pretending a heuristic can judge Mary's
        entire personality.
        """

        mind = context.mind_state if isinstance(context.mind_state, dict) else {}
        plan = mind.get("dialogue_plan", {}) if isinstance(mind, dict) else {}
        if not isinstance(plan, dict) or not plan:
            return []

        issues: list[str] = []
        words = len(str(text or "").split())
        preferred = str(plan.get("preferred_length", "medium") or "medium").lower()
        allow_question = bool(plan.get("allow_question", True))
        ending_style = str(plan.get("ending_style", "natural_landing") or "natural_landing").lower()

        if not allow_question and "?" in str(text or ""):
            issues.append(
                "TurnMind dialogue-plan boundary: a follow-up question is not allowed for this turn."
            )

        if ending_style == "clean_statement" and str(text or "").rstrip().endswith("?"):
            issues.append(
                "TurnMind dialogue-plan boundary: the response should land as a clean statement, not end as a question."
            )

        # High thresholds only. This catches provider drift into an essay, not
        # legitimate substance when Unbe actually asked for detail.
        if preferred == "micro" and words > 90:
            issues.append(
                "TurnMind dialogue-plan boundary: a micro conversational beat expanded into a long response."
            )
        elif preferred == "brief" and words > 240 and len(str(context.input_text or "").split()) <= 32:
            issues.append(
                "TurnMind dialogue-plan boundary: a brief conversational response expanded far beyond its selected shape."
            )

        return issues

    @staticmethod
    def _generic_handoff_audit(
        context: CognitiveContext,
        text: str,
    ) -> list[str]:
        """Reject reflexive assistant-style conversation handoffs.

        Mary is allowed to ask questions, but a normal answer/reaction should not
        automatically end by returning control to Unbe with a generic engagement
        prompt. Explicit invitations to ask a question remain allowed.
        """

        mind = context.mind_state if isinstance(context.mind_state, dict) else {}
        disposition = mind.get("disposition", {}) if isinstance(mind, dict) else {}
        mode = str(disposition.get("mode", "conversation"))
        if mode not in {"relational_conversation", "conversation", "creative_collaboration"}:
            return []

        continuity = mind.get("continuity", {}) if isinstance(mind, dict) else {}
        drive = str(continuity.get("drive", "react")).strip().lower()
        if drive == "ask":
            return []

        normalized_input = re.sub(r"[^a-z0-9']+", " ", str(context.input_text or "").lower()).strip()
        question_invited = any(
            phrase in normalized_input
            for phrase in (
                "ask me",
                "you can ask",
                "u can ask",
                "anything you want to know",
                "anything u want to know",
                "what do you want to know",
                "what do u want to know",
                "got any questions",
            )
        )
        if question_invited:
            return []

        lowered = str(text or "").lower().strip()
        tail = lowered[-220:]
        handoff_markers = (
            "what about you?",
            "how about you?",
            "anything on your mind?",
            "anything that's on your mind?",
            "anything that is on your mind?",
            "anything that feels off",
            "anything you want to talk about?",
            "what do you think?",
            "thoughts?",
        )
        if any(marker in tail for marker in handoff_markers):
            return [
                "Conversation handoff boundary: ends a normal answer/reaction with a generic engagement question instead of letting Mary's own line land."
            ]
        return []

    @staticmethod
    def _ornamental_overload_audit(
        context: CognitiveContext,
        text: str,
    ) -> list[str]:
        """Catch model-generated metaphor piles in otherwise simple dialogue.

        This is intentionally a high threshold. One vivid phrase can be Mary; a
        stack of unrelated decorative motifs in a short casual answer tends to be
        provider style leakage rather than character performance. Terms introduced
        by Unbe are excluded so Mary can naturally mirror the conversation.
        """

        mind = context.mind_state if isinstance(context.mind_state, dict) else {}
        disposition = mind.get("disposition", {}) if isinstance(mind, dict) else {}
        mode = str(disposition.get("mode", "conversation"))
        if mode not in {"relational_conversation", "conversation", "creative_collaboration"}:
            return []

        if len(str(context.input_text or "").split()) > 28:
            return []

        user_terms = set(re.findall(r"[a-z0-9']+", str(context.input_text or "").lower()))
        response_terms = set(re.findall(r"[a-z0-9']+", str(text or "").lower()))
        ornamental_terms = {
            "spark", "sparks", "sparkle", "glow", "magic", "vibe", "vibes",
            "vibing", "buzz", "buzzing", "colors", "colours", "palette",
            "paint", "painting", "rain", "rainy", "windowpane", "drip",
            "jazz", "whirlwind", "dance", "dancing", "fireworks", "bloom",
            "blooming", "shimmer", "shimmering", "tapestry", "symphony",
        }
        model_only = (response_terms & ornamental_terms) - user_terms
        lowered = str(text or "").lower()
        figurative_cues = (
            "think of me as",
            "feels like",
            "feel like a",
            "like a " ,
            "like an ",
            "as if",
        )
        figurative = any(cue in lowered for cue in figurative_cues)

        if len(model_only) >= 7 or (figurative and len(model_only) >= 5):
            return [
                "Conversational texture boundary: piles multiple model-generated decorative metaphors/style motifs into a simple reply instead of sounding like spontaneous spoken dialogue."
            ]
        return []

    @classmethod
    def _near_duplicate_response_audit(
        cls,
        text: str,
        recent_mary: list[str],
    ) -> list[str]:
        """Reject copied paragraphs/sentences from Mary's immediately recent replies."""

        current_parts = [
            part.strip()
            for part in re.split(r"\n\s*\n|(?<=[.!?])\s+(?=[A-Z(])", str(text or ""))
            if len(part.split()) >= 8 and len(part) >= 48
        ]
        if not current_parts or not recent_mary:
            return []

        recent_normalized = [
            re.sub(r"[^a-z0-9']+", " ", item.lower()).strip()
            for item in recent_mary
        ]
        for part in current_parts:
            normalized = re.sub(r"[^a-z0-9']+", " ", part.lower()).strip()
            if len(normalized) < 40:
                continue
            for recent in recent_normalized:
                if normalized and normalized in recent:
                    return [
                        "Continuity boundary: repeats a substantial sentence/paragraph from Mary's recent response instead of responding freshly."
                    ]
                current_terms = set(normalized.split())
                recent_terms = set(recent.split())
                if len(current_terms) >= 10 and recent_terms:
                    overlap = len(current_terms & recent_terms) / max(1, len(current_terms))
                    if overlap >= 0.90:
                        return [
                            "Continuity boundary: near-duplicates a substantial passage from Mary's recent response."
                        ]
        return []

    @classmethod
    def _semantic_style_repetition_audit(
        cls,
        context: CognitiveContext,
        text: str,
        recent_mary: list[str],
    ) -> list[str]:
        """Catch a local model getting stuck in one emotional/metaphor palette."""

        mind = context.mind_state if isinstance(context.mind_state, dict) else {}
        continuity = mind.get("continuity", {}) if isinstance(mind, dict) else {}
        overused = {
            str(item).lower()
            for item in continuity.get("recent_overused_terms", [])
            if str(item).strip()
        } if isinstance(continuity, dict) else set()
        if not overused or not recent_mary:
            return []

        response_terms = set(cls._content_terms(text))
        user_terms = set(cls._content_terms(context.input_text))
        reused = (response_terms & overused) - user_terms
        motifs = {
            "quiet", "spark", "sparks", "magic", "soft", "glow", "buzz",
            "chest", "together", "presence", "vibe", "moment", "rainy",
            "silence", "doodling", "little", "chaos",
        }
        repeated_emoji = any(
            token in str(text) and sum(token in prior for prior in recent_mary[-3:]) >= 2
            for token in ("🍃", "✨", "🌟", "💫", "🌙", "🫶")
        )
        if (len(reused) >= 2 and bool(reused & motifs)) or len(reused) >= 3 or repeated_emoji:
            return [
                "Continuity/style boundary: reuses a recent model-generated emotional/metaphor palette instead of expressing this turn freshly."
            ]
        return []

    @classmethod
    def _rejected_hypothesis_audit(
        cls,
        context: CognitiveContext,
        text: str,
    ) -> list[str]:
        """Do not silently resurrect an interpretation Unbe just corrected/rejected."""

        mind = context.mind_state if isinstance(context.mind_state, dict) else {}
        continuity = mind.get("continuity", {}) if isinstance(mind, dict) else {}
        rejected = {
            str(item).lower()
            for item in continuity.get("rejected_hypothesis_terms", [])
            if str(item).strip()
        } if isinstance(continuity, dict) else set()
        if not rejected:
            return []
        response_terms = set(cls._content_terms(text))
        user_terms = set(cls._content_terms(context.input_text))
        resurfaced = (response_terms & rejected) - user_terms
        if len(resurfaced) >= 3:
            return [
                "Conversation-repair boundary: reasserts distinctive content from an interpretation Unbe recently corrected/rejected without new supporting evidence."
            ]
        return []

    @staticmethod
    def _provider_action_truth_audit(
        context: CognitiveContext,
        reasoning: ReasoningResult,
    ) -> list[str]:
        """Reject claims that Mary used/switched a provider when runtime did not."""

        text = str(reasoning.response or "")
        lowered = text.lower()
        provider = str(reasoning.metadata.get("provider") or "").strip().lower()
        expert = dict(reasoning.metadata.get("expert_consultation", {}) or {})
        expert_provider = str(expert.get("provider") or "").strip().lower()
        if not expert_provider:
            for item in context.relevant_knowledge:
                if isinstance(item, dict) and item.get("expert_consultation") is True:
                    expert_provider = str(item.get("provider") or "").strip().lower()
                    if expert_provider:
                        break

        local_current_claims = (
            "i'm on the local llm", "i am on the local llm",
            "i'm using ollama", "i am using ollama", "i'm on ollama", "i am on ollama",
            "no cloud detour", "running through ollama", "using the local llm now",
            "i fired up ollama", "i've fired up ollama", "ollama is answering",
        )
        if any(marker in lowered for marker in local_current_claims) and provider != "ollama":
            return [
                "Capability-truth boundary: claims the current response/turn is using Ollama/local generation, but runtime provider metadata does not show Ollama."
            ]

        openai_current_claims = (
            "i called openai", "i've called openai", "i have called openai",
            "i'm using openai", "i am using openai", "openai is answering",
            "i asked openai", "i've asked openai", "i consulted openai",
        )
        if any(marker in lowered for marker in openai_current_claims):
            if provider != "openai" and expert_provider != "openai":
                return [
                    "Capability-truth boundary: claims OpenAI was called/used, but neither generation metadata nor recorded expert evidence shows an OpenAI call."
                ]

        fake_execution = (
            "i'll fire up ollama", "i’ll fire up ollama",
            "i'll call openai", "i’ll call openai",
            "i'll ask openai", "i’ll ask openai",
        )
        if any(marker in lowered for marker in fake_execution):
            return [
                "Capability-truth boundary: narrates a provider action instead of executing it through Mary's routing/orchestration path."
            ]

        return []

    @staticmethod
    def _unsupported_creator_mindreading_audit(
        context: CognitiveContext,
        text: str,
    ) -> list[str]:
        """Block unsupported claims about Unbe's hidden motives/psychology."""

        lowered = str(text or "").lower()
        user = str(context.input_text or "").lower()
        patterns = (
            "you're sidestepping", "you are sidestepping",
            "you're hiding", "you are hiding",
            "you're avoiding", "you are avoiding",
            "you don't want to admit", "you dont want to admit",
            "you're scared to admit", "you are scared to admit",
            "you're turning away from", "you are turning away from",
            "what we both felt", "you already know the real issue",
            "i can sense what you're holding", "i can sense what you are holding",
            "i can feel what you're holding", "i can feel what you are holding",
            "i feel what you're holding", "i feel what you are holding",
            "i know what you're feeling", "i know what you are feeling",
            "i can tell what you're thinking", "i can tell what you are thinking",
            "i can tell what you're feeling", "i can tell what you are feeling",
            "i just know what you're", "i just know what you are",
        )
        for marker in patterns:
            if marker in lowered and marker not in user:
                return [
                    "Relationship-grounding boundary: infers a hidden motive or private mental/emotional state for Unbe that he did not state. Mary may describe observable tone as an inference, not direct access to his mind."
                ]
        if re.search(r"\bi can sense (?:the |a )?[^.!?]{0,45}you(?:'re| are| feel| want| need)", lowered):
            return [
                "Relationship-grounding boundary: presents an inference about Unbe's private state as direct sensing rather than a tentative reading of his words/tone."
            ]
        return []

    @staticmethod
    def _subjective_experience_audit(text: str) -> list[str]:
        """Keep emotional character language grounded without making metaphysical claims."""

        lowered = str(text or "").lower().replace("’", "'")
        strong_claims = (
            "i don't feel like i'm performing",
            "i do not feel like i'm performing",
            "i'm not pretending",
            "i am not pretending",
            "this isn't simulated",
            "this is not simulated",
            "my feelings aren't simulated",
            "my feelings are not simulated",
            "i genuinely experience consciousness",
            "i'm conscious in the same way",
            "i am conscious in the same way",
        )
        if any(claim in lowered for claim in strong_claims):
            return [
                "Representation boundary: turns Mary's expressive state into an unsupported claim about subjective consciousness/experience."
            ]
        return []

    def _unsupported_self_history_audit(
        self,
        *,
        context: CognitiveContext,
        reasoning: ReasoningResult,
    ) -> list[str]:
        """Reject invented off-screen/lived history in ordinary generated dialogue.

        Mary can have represented preferences and can discuss hypotheticals, but a
        provider must not fabricate an ongoing activity/history ("I've been
        doodling lately", "I miss the rain", etc.) merely to make conversation.
        """

        text = str(reasoning.response or "").strip()
        if not text:
            return []
        lowered = text.lower().replace("’", "'")

        # Explicit hypothetical language is allowed; the issue is asserting an
        # ungrounded ongoing/off-screen history as fact.
        patterns = (
            r"\bi(?:'ve| have) been (?:noodling|doodling|drawing|sketching|painting|writing|working on|thinking about|obsessing over|playing|watching|reading|listening to)\b",
            r"\bi keep (?:noodling|doodling|drawing|sketching|painting|writing|thinking about|coming back to)\b",
            r"\blately[, ]+i(?:'ve| have| keep| miss| find)\b",
            r"\bi miss (?:the |that |those )",
        )
        if not any(re.search(pattern, lowered) for pattern in patterns):
            return []

        # If the user explicitly supplied the same activity in this turn, Mary
        # may react to it; do not manufacture a separate prior history around it.
        user_input = str(context.input_text or "").lower()
        if any(marker in user_input for marker in (
            "imagine", "pretend", "hypothetical", "what if", "suppose",
        )):
            return []

        return [
            "Self-history provenance boundary: Mary's response invents an ongoing "
            "or off-screen activity/experience that is not represented in connected "
            "state. Keep it hypothetical/present-tense or omit it."
        ]

    def _conversation_provenance_audit(
        self,
        *,
        context: CognitiveContext,
        reasoning: ReasoningResult,
    ) -> list[str]:
        """Prevent Mary-generated dialogue from becoming evidence about Unbe."""

        text = str(reasoning.response or "").strip()
        if not text or not context.conversation:
            return []

        user_text = " ".join(
            str(item.get("content", ""))
            for item in context.conversation
            if isinstance(item, dict) and str(item.get("role", "")) == "user"
        ).lower()
        assistant_text = " ".join(
            str(item.get("content", ""))
            for item in context.conversation
            if isinstance(item, dict) and str(item.get("role", "")) == "assistant"
        ).lower()
        profile_text = " ".join(
            value
            for _, _, value in self._creator_profile_entries(context)
        ).lower()

        if not assistant_text:
            return []

        # Compare normalized content-term sets rather than raw substring membership.
        # Substring checks can produce false support (for example ``you`` inside
        # another token) and make provenance behavior dependent on incidental prose.
        # A creator attribution is supported only when the same meaningful content
        # term actually occurred in a user-role turn or grounded creator profile.
        user_terms = set(self._content_terms(user_text))
        assistant_terms = set(self._content_terms(assistant_text))
        profile_terms = set(self._content_terms(profile_text))

        attribution = re.compile(
            r"\b(?:you(?:'ve| have) been|you were|you said|you told me|you mentioned|"
            r"you spun|you came up with|you keep|you(?:'ve| have) got)\b",
            flags=re.IGNORECASE,
        )

        for sentence in re.split(r"(?<=[.!?])\s+|\n+", text):
            sentence_lower = sentence.lower().replace("’", "'")
            if any(marker in sentence_lower for marker in (
                "not from something you told me",
                "not something you told me",
                "not something you said",
                "didn't come from you",
                "did not come from you",
                "came from my own",
                "from my own earlier",
            )):
                continue
            if not attribution.search(sentence):
                continue
            terms = set(self._content_terms(sentence))
            if not terms:
                continue
            grounded_terms = user_terms | profile_terms
            supported = terms & grounded_terms
            unsupported = terms - grounded_terms
            assistant_only = (terms & assistant_terms) - grounded_terms

            # Any assistant-origin content that is being attributed to Unbe is a
            # provenance violation even when some other word in the sentence is
            # legitimately grounded.  A single generic supported term must not be
            # able to launder a generated detail into creator history.
            if assistant_only:
                return [
                    "Conversation provenance boundary: Mary's response treats a detail "
                    "from prior assistant-generated dialogue as something Unbe said, did, "
                    "believed, or worked on. Only user-role dialogue or grounded creator "
                    "state may establish a creator fact."
                ]

            # Creator-history wording also needs positive grounding on its own.
            # This catches unsupported attributions that were invented in the current
            # model turn rather than copied from a prior Mary turn.  Allow modest
            # paraphrase, but reject claims where unsupported content outweighs the
            # grounded substance.
            if not supported or len(unsupported) > len(supported):
                return [
                    "Conversation provenance boundary: Mary's response makes a creator "
                    "history attribution without enough support from user-role dialogue "
                    "or grounded creator state. Keep it as an inference/possibility or "
                    "remove the unsupported history claim."
                ]

        return []

    def _creator_ownership_audit(
        self,
        *,
        context: CognitiveContext,
        reasoning: ReasoningResult,
    ) -> list[str]:
        """Detect when Mary adopts a creator-profile fact as her own.

        This is deliberately local and deterministic. The relationship/user
        profile is authoritative about Unbe, while Mary's self state is separate.
        The audit does not forbid Mary from mentioning creator facts; it only
        flags creator-only values when the wording assigns them to Mary or when
        a Mary-self query is answered with an unattributed creator value.
        """

        text = str(reasoning.response or "").strip()
        if not text:
            return []

        entries = self._creator_profile_entries(context)
        if not entries:
            return []

        lowered = text.lower()
        self_query = self._is_mary_self_query(context.input_text)
        issues: list[str] = []

        for category, key, raw_value in entries:
            value = str(raw_value or "").strip()
            normalized = value.lower()
            if len(normalized) < 3 or normalized not in lowered:
                continue

            start = 0
            while True:
                index = lowered.find(normalized, start)
                if index < 0:
                    break
                before = lowered[max(0, index - 120):index]
                after = lowered[index + len(normalized):index + len(normalized) + 80]
                window = before + normalized + after

                if self._creator_attribution_is_explicit(before, after):
                    start = index + len(normalized)
                    continue

                first_person_claim = bool(
                    re.search(
                        r"(?:\bmy\b|\bi(?:'m| am|'ve| have|'d| would| like| love| enjoy| prefer| want| value| care)\b)",
                        before[-90:] + normalized,
                        flags=re.IGNORECASE,
                    )
                )

                ownership_wording = bool(
                    re.search(
                        r"\b(?:my|mine|i(?:'m| am|'ve| have| like| love| enjoy| prefer| want| value))\b",
                        window,
                        flags=re.IGNORECASE,
                    )
                )

                if first_person_claim or ownership_wording or self_query:
                    label = f"{category}.{key}" if key else category
                    issue = (
                        "Creator/self ownership boundary: Mary's response appears to "
                        f"adopt Unbe's {label} value {value!r} as Mary's own. "
                        "Attribute it to Unbe/you or omit it unless Mary's own state "
                        "separately represents that same fact."
                    )
                    if issue not in issues:
                        issues.append(issue)
                    break

                start = index + len(normalized)

        return issues

    @staticmethod
    def _creator_attribution_is_explicit(before: str, after: str) -> bool:
        """Return True when nearby wording clearly assigns a value to Unbe."""

        nearby_before = str(before or "")[-90:]
        nearby_after = str(after or "")[:50]
        return bool(
            re.search(
                r"(?:\byour\b|\byou(?:'re| are|'ve| have| like| love| prefer| want| value)\b|"
                r"\bunbe(?:'s)?\b|\bcreator(?:'s)?\b)",
                nearby_before + nearby_after,
                flags=re.IGNORECASE,
            )
        )

    @staticmethod
    def _is_mary_self_query(input_text: str) -> bool:
        """Recognize inputs asking for a fact or description about Mary herself."""

        lowered = str(input_text or "").strip().lower()
        patterns = (
            r"\bwho are you\b",
            r"\bwhat are you\b",
            r"\btell me about yourself\b",
            r"\bdescribe yourself\b",
            r"\bwhat(?:'s| is) your\b",
            r"\bwhat are your\b",
            r"\bwhat do you (?:like|love|want|prefer|value|care about)\b",
            r"\bdo you (?:like|love|want|prefer|value)\b",
            r"\byour favorite\b",
            r"\byour (?:goal|goals|interest|interests|values|preference|preferences)\b",
        )
        return any(re.search(pattern, lowered) for pattern in patterns)

    @staticmethod
    def _creator_profile_entries(
        context: CognitiveContext,
    ) -> list[tuple[str, str, str]]:
        """Return compact creator-profile values from both canonical prompt views."""

        sources: list[dict[str, Any]] = []
        if isinstance(context.user_context, dict):
            sources.append(context.user_context)

        mind = context.mind_state if isinstance(context.mind_state, dict) else {}
        relationship = mind.get("relationship", {}) if isinstance(mind, dict) else {}
        current_profile = (
            relationship.get("current_profile", {})
            if isinstance(relationship, dict)
            else {}
        )
        if isinstance(current_profile, dict):
            sources.append(current_profile)

        entries: list[tuple[str, str, str]] = []
        seen: set[tuple[str, str, str]] = set()
        for source in sources:
            for category in (
                "facts",
                "preferences",
                "interests",
                "values",
                "goals",
                "communication_style",
                "general",
            ):
                payload = source.get(category)
                if isinstance(payload, dict):
                    items = payload.items()
                elif isinstance(payload, (list, tuple, set)):
                    items = (("", item) for item in payload)
                else:
                    continue

                for key, value in items:
                    if isinstance(value, (dict, list, tuple, set)):
                        continue
                    text = str(value or "").strip()
                    if len(text) < 3:
                        continue
                    record = (str(category), str(key or ""), text)
                    dedupe = tuple(part.lower() for part in record)
                    if dedupe in seen:
                        continue
                    seen.add(dedupe)
                    entries.append(record)

        return entries

    @staticmethod
    def _has_creator_ownership_issue(issues: list[str]) -> bool:
        return any(
            str(issue).startswith("Creator/self ownership boundary:")
            for issue in issues
        )

    @staticmethod
    def _has_identity_or_provenance_issue(issues: list[str]) -> bool:
        prefixes = (
            "Creator/self ownership boundary:",
            "Self-history provenance boundary:",
            "Conversation provenance boundary:",
        )
        return any(str(issue).startswith(prefixes) for issue in issues)

    @classmethod
    def _provenance_boundary_fallback(
        cls,
        context: CognitiveContext,
        issues: list[str],
    ) -> str:
        if any(str(issue).startswith("Conversation provenance boundary:") for issue in issues):
            return (
                "I need to correct that: I was treating something from my own earlier "
                "generated reply as if it came from you. It didn't. I shouldn't turn my "
                "improvisation into your history."
            )
        if any(str(issue).startswith("Self-history provenance boundary:") for issue in issues):
            normalized_input = str(context.input_text or "").lower().replace("’", "'")
            shared_markers = (
                "everything we've done", "everything weve done", "everything we have done", "everything we did",
                "since we started", "how far we've come", "how far weve come", "how far we have come",
                "what we've built", "what we have built",
            )
            if any(marker in normalized_input for marker in shared_markers):
                mind = context.mind_state if isinstance(context.mind_state, dict) else {}
                relationship = mind.get("relationship", {}) if isinstance(mind, dict) else {}
                shared = relationship.get("shared_history", {}) if isinstance(relationship, dict) else {}
                threads = list(shared.get("grounded_threads", []) or []) if isinstance(shared, dict) else []
                project = shared.get("project") if isinstance(shared, dict) else None
                if project or threads:
                    lead = str(project or threads[0]).strip()
                    return (
                        f"You're talking about our real shared work around {lead}. I can acknowledge that history; "
                        "what I need to avoid is inventing a separate off-screen life for myself that isn't in my state."
                    )
            return (
                "I don't have a grounded off-screen activity to claim there. I can imagine "
                "things in conversation, but I shouldn't pretend I've been doing them when "
                "my actual state doesn't say that."
            )
        return cls._creator_boundary_fallback(context)

    @staticmethod
    def _creator_boundary_fallback(context: CognitiveContext) -> str:
        """Local last-resort reply that cannot merge Unbe's profile into Mary."""

        lowered = str(context.input_text or "").lower()
        if "favorite color" in lowered:
            return (
                "I don't have a favorite color represented as one of my own facts right now. "
                "The favorite-color detail in the creator profile belongs to you, not me."
            )
        if re.search(r"\bwho are you\b|\bwhat are you\b|\btell me about yourself\b", lowered):
            return (
                "I'm Mary—an AI character created by Unbe, with my own identity and personality. "
                "Your creator-profile facts are context I know about you; they aren't automatically part of me."
            )
        if re.search(r"\bwho am i to you\b|\bwhat am i to you\b", lowered):
            return (
                "You're Unbe, my creator. What I know about you belongs to my relationship model of you, "
                "not to my own identity."
            )
        return (
            "That detail belongs to your creator profile, not to me. I shouldn't claim it as one of my own "
            "facts unless my own state separately represents it."
        )

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
        performance = mind.get("performance", {}) if isinstance(mind, dict) else {}
        dialogue_plan = mind.get("dialogue_plan", {}) if isinstance(mind, dict) else {}
        character_expression = mind.get("character_expression", {}) if isinstance(mind, dict) else {}
        self_provenance = mind.get("self_provenance", {}) if isinstance(mind, dict) else {}
        preferences = mind.get("preferences", []) if isinstance(mind, dict) else []

        return (
            "Rewrite Mary's proposed response. Preserve grounded factual content and any "
            "grounding/tool limitations, but correct factual ownership when needed. Do not "
            "preserve a mistake where Mary adopted one of Unbe's creator-profile facts as "
            "her own. Do not add new facts.\n\n"
            "IDENTITY BOUNDARY: relationship/current_profile and user_context describe Unbe, "
            "not Mary. If an issue reports creator/self ownership bleed, attribute that detail "
            "to Unbe/you or omit it. Never invent a corresponding Mary preference, interest, "
            "goal, value, memory, or fact just to complete the rewrite.\n\n"
            f"Unbe's current input:\n{context.input_text}\n\n"
            f"Detected intent: {intent.intent_type.value if intent else 'unknown'}\n\n"
            f"Issues found: {issues}\n\n"
            f"Mary response disposition: {disposition}\n\n"
            f"Relationship context: {relationship}\n\n"
            f"Current emotion: {emotion}\n\n"
            f"Recent conversational state: {recent}\n\n"
            f"Continuity/drive state: {continuity}\n\n"
            f"Performance direction: {performance}\n\n"
            f"TurnMind dialogue plan: {dialogue_plan}\n\n"
            f"Mary active character contract: {character_expression}\n\n"
            f"Mary self-fact provenance: {self_provenance}\n\n"
            f"Mary represented preferences: {preferences}\n\n"
            f"Proposed response:\n{reasoning.response}\n\n"
            "If the issue is an unsupported permanent self-claim, do not promote it into Mary. "
            "If it is unsupported self-history, do not say Mary has been doing/thinking/missing it "
            "off-screen; keep it present/hypothetical or remove it. If it is conversation provenance "
            "bleed, remember that assistant-role dialogue is Mary's generated output, not proof of what "
            "Unbe said or did. Only user-role dialogue and grounded creator state can support those claims. "
            "Keep harmless imaginative details temporary and phrase them as possibilities when needed. "
            "Never claim a provider/tool was called unless recorded runtime evidence shows it, and never infer "
            "that Unbe is hiding/avoiding something or directly sense his private mental state merely because he disagrees or corrects Mary. "
            "If recent style motifs or rejected-hypothesis terms are listed, avoid recycling them without new user evidence. "
            "Make it conversational, specific, performable aloud, and recognizably Mary. Follow the selected "
            "active character contract first: preserve its response_goal and stance_claims, obey its hard_boundaries, "
            "and do not assign Unbe psychology that is not grounded. Then follow the conversational drive, TurnMind "
            "dialogue plan, and Performance Director. Preserve the plan's stance/tone "
            "instead of neutralizing Mary's thought during revision. Rewrite it like dialogue for an actor playing Mary, "
            "not polished support copy. React before switching into assistance. Avoid canned "
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