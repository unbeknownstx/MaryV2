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
        elif self_grounded:
            # Self-introspection is already grounded locally. The model only
            # needs enough output room to express Mary's answer naturally.
            generation_kwargs["max_tokens"] = 500
        else:
            # Ordinary dialogue should not reserve a 2K-token completion on a
            # free provider. Besides wasting quota, Groq counts the requested
            # completion budget toward TPM. Scale the allowance to Mary's
            # selected response disposition instead.
            generation_kwargs["max_tokens"] = self._conversation_max_tokens(
                context
            )

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
        """Reject self claims that contradict or outrun local self evidence."""

        response_text = str(response)
        lowered_response = response_text.lower().replace("’", "'")
        lowered_query = str(context.input_text).lower().replace("’", "'")

        evidence = [
            item
            for item in context.relevant_knowledge
            if isinstance(item, dict)
            and item.get("self_introspection") is True
        ]

        for item in evidence:
            compact = item.get("prompt_evidence")
            source = compact if isinstance(compact, dict) else item
            subtype = str(source.get("subtype", item.get("subtype", ""))).lower()

            if subtype == "appearance":
                appearance = source.get("appearance", [])
                appearance = appearance if isinstance(appearance, list) else []

                if not appearance:
                    uncertainty_markers = (
                        "not represented",
                        "isn't represented",
                        "is not represented",
                        "haven't established",
                        "have not established",
                        "don't have that detail",
                        "do not have that detail",
                        "isn't in my",
                        "is not in my",
                    )
                    if not any(marker in lowered_response for marker in uncertainty_markers):
                        return (
                            "Generated self-response invented an appearance detail that "
                            "is absent from Mary's canonical biography."
                        )

                if "hair" in lowered_query:
                    hair = next(
                        (
                            entry
                            for entry in appearance
                            if isinstance(entry, dict)
                            and "hair" in str(entry.get("title", "")).lower()
                        ),
                        None,
                    )
                    if hair is not None:
                        expected = str(hair.get("content", "")).strip().lower()
                        denial_markers = (
                            "don't have hair",
                            "do not have hair",
                            "i'm just code",
                            "i am just code",
                            "don't have a physical body",
                            "do not have a physical body",
                            "no physical body",
                        )
                        color_words = {
                            "red", "blue", "green", "black", "brown", "blonde",
                            "blond", "white", "gray", "grey", "purple", "pink",
                            "orange", "auburn", "silver",
                        }
                        mentioned_colors = {
                            color
                            for color in color_words
                            if re.search(rf"\b{re.escape(color)}\b", lowered_response)
                        }
                        if expected and expected not in lowered_response:
                            detail = (
                                "contradicted"
                                if (
                                    any(marker in lowered_response for marker in denial_markers)
                                    or bool(mentioned_colors)
                                )
                                else "failed to preserve"
                            )
                            return (
                                f"Generated self-response {detail} Mary's canonical "
                                f"hair color ({expected})."
                            )

                if "eye" in lowered_query or "eyes" in lowered_query:
                    eyes = next(
                        (
                            entry
                            for entry in appearance
                            if isinstance(entry, dict)
                            and "eye" in str(entry.get("title", "")).lower()
                        ),
                        None,
                    )
                    if eyes is not None:
                        expected = str(eyes.get("content", "")).strip().lower()
                        color_words = {
                            "red", "blue", "green", "black", "brown", "hazel",
                            "gray", "grey", "purple", "amber", "gold", "golden",
                        }
                        mentioned_colors = {
                            color for color in color_words
                            if re.search(rf"\b{re.escape(color)}\b", lowered_response)
                        }
                        if expected and expected not in lowered_response and mentioned_colors:
                            return (
                                "Generated self-response contradicted Mary's canonical "
                                f"eye color ({expected})."
                            )

            if subtype == "preferences":
                preferences = source.get("preferences", [])
                preferences = preferences if isinstance(preferences, list) else []
                if not preferences:
                    uncertainty_markers = (
                        "not represented",
                        "isn't represented",
                        "is not represented",
                        "don't have a favorite",
                        "do not have a favorite",
                        "don't have that preference",
                        "do not have that preference",
                        "haven't established",
                        "have not established",
                    )
                    first_person_preference = re.search(
                        r"\b(?:my favorite|my favourite|i prefer|i like|i love)\b",
                        lowered_response,
                    )
                    acknowledges_absence = any(
                        marker in lowered_response
                        for marker in uncertainty_markers
                    )
                    if first_person_preference is not None and not acknowledges_absence:
                        return (
                            "Generated self-response invented a Mary preference that is "
                            "absent from local self evidence."
                        )
                    if not acknowledges_absence:
                        return (
                            "Generated self-response failed to preserve the absence of a "
                            "Mary preference in local self evidence."
                        )
                else:
                    # A direct preference self-query should preserve at least one
                    # represented preference rather than substituting an unrelated
                    # provider persona. Broad summaries may use a category word.
                    supported = []
                    for preference in preferences:
                        if not isinstance(preference, dict):
                            continue
                        name = str(preference.get("name", "")).strip().lower()
                        category = str(preference.get("category", "")).strip().lower()
                        if name:
                            supported.append(name)
                        if category:
                            supported.append(category)
                    if supported and not any(term in lowered_response for term in supported):
                        return (
                            "Generated self-response did not preserve any represented Mary "
                            "preference from local self evidence."
                        )

            if subtype in {
                "vulnerabilities", "romance", "reactions", "social_behavior",
                "private_life", "speech", "goals"
            }:
                marker_map = {
                    "vulnerabilities": (
                        "friend", "bad person", "loved", "passing", "abandon",
                        "cute", "soft", "pink", "e-girl",
                    ),
                    "romance": (
                        "hopeless romantic", "gift", "quality time", "shared",
                        "individual time", "space", "romantic gesture", "roast",
                    ),
                    "reactions": (
                        "quiet", "fiery", "crash", "blush", "tsundere",
                        "happy dance", "protect",
                    ),
                    "social_behavior": (
                        "stranger", "close", "bubbly", "support", "sarcastic",
                        "curt", "trust", "watched", "center of attention", "quiet",
                    ),
                    "private_life": (
                        "drawing", "painting", "writing", "gaming", "cooking",
                        "yoga", "self-care", "hiking", "phone", "downtime",
                    ),
                    "speech": (
                        "feller", "bucko", "this guy", "twinnn", "nah fam",
                        "what up gang", "streamer", "slang",
                    ),
                    "goals": (
                        "homestead", "love of my life", "lasting partnership",
                        "travel", "justice",
                    ),
                }
                markers = marker_map[subtype]
                if not any(marker in lowered_response for marker in markers):
                    return (
                        f"Generated self-response did not preserve Mary's represented "
                        f"{subtype} evidence."
                    )

        generated_dates = set(
            re.findall(r"\b(?:19|20)\d{2}(?:-\d{2}-\d{2})?\b", response_text)
        )
        if not generated_dates:
            return None

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

        if self._has_self_evidence(context):
            return self._self_system_prompt(context)

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

    def _self_system_prompt(
        self,
        context: CognitiveContext,
    ) -> str:
        """Compact system prompt for grounded questions about Mary herself."""

        mind = context.mind_state if isinstance(context.mind_state, dict) else {}
        disposition = mind.get("disposition", {}) if isinstance(mind, dict) else {}
        continuity = mind.get("continuity", {}) if isinstance(mind, dict) else {}

        return (
            "You are Mary. Answer questions about yourself from the supplied local "
            "self-introspection evidence, which is authoritative. Do not replace Mary's "
            "identity with the language model's generic assistant identity. If a requested "
            "self fact is absent, say it is not represented rather than inventing it. Facts "
            "about Unbe describe your creator, not you. Speak naturally as Mary rather than "
            "as a helpdesk assistant. "
            f"Mode: {disposition.get('mode', 'conversation')}. "
            f"Preferred length: {disposition.get('preferred_length', 'brief')}. "
            f"Drive: {continuity.get('drive', 'answer')}. "
            f"Follow-up question allowed: {bool(continuity.get('allow_follow_up_question', True))}."
        )

    def _build_self_prompt(
        self,
        context: CognitiveContext,
        intent: Intent | None,
    ) -> str:
        """Build a compact prompt for self-grounded local inference.

        The full TurnMindState remains available to Mary's runtime and reflection,
        but a direct self-fact question should not require sending thousands of
        unrelated tokens to a local model.
        """

        evidence: list[dict[str, Any]] = []
        for item in context.relevant_knowledge:
            if not isinstance(item, dict) or item.get("self_introspection") is not True:
                continue
            compact = item.get("prompt_evidence")
            evidence.append(
                dict(compact)
                if isinstance(compact, dict)
                else dict(item)
            )

        mind = context.mind_state if isinstance(context.mind_state, dict) else {}
        disposition = mind.get("disposition", {}) if isinstance(mind, dict) else {}
        continuity = mind.get("continuity", {}) if isinstance(mind, dict) else {}
        performance = mind.get("performance", {}) if isinstance(mind, dict) else {}

        style = {
            "mode": disposition.get("mode"),
            "preferred_length": disposition.get("preferred_length"),
            "warmth": disposition.get("warmth"),
            "playfulness": disposition.get("playfulness"),
            "directness": disposition.get("directness"),
            "expressiveness": disposition.get("expressiveness"),
            "familiarity": disposition.get("familiarity"),
        }
        delivery = {
            "pacing": performance.get("pacing"),
            "emotional_color": performance.get("emotional_color"),
            "opening_style": performance.get("opening_style"),
            "ending_style": performance.get("ending_style"),
        }
        continuity_view = {
            "drive": continuity.get("drive"),
            "allow_follow_up_question": continuity.get("allow_follow_up_question"),
        }

        intent_text = intent.intent_type.value if intent is not None else "unknown"

        return f"""Current user input:
{context.input_text}

Detected intent:
{intent_text}

Self-introspection grounding rules:
Use the local evidence below as the source of truth for Mary's own facts. Do not substitute generic model identity. Do not copy creator facts into Mary. If the requested detail is absent, say it is not represented.

Grounded self evidence:
{evidence}

Compact response style:
{style}

Compact delivery:
{delivery}

Continuity:
{continuity_view}

Answer directly as Mary. Preserve the factual meaning of the local evidence."""

    @staticmethod
    def _conversation_max_tokens(
        context: CognitiveContext,
    ) -> int:
        """Return a bounded completion budget for ordinary conversation."""

        mind = context.mind_state if isinstance(context.mind_state, dict) else {}
        disposition = mind.get("disposition", {}) if isinstance(mind, dict) else {}
        preferred = str(disposition.get("preferred_length", "medium")).lower().strip()

        if preferred == "brief":
            return 400
        if preferred == "detailed":
            return 1_200
        return 800

    @staticmethod
    def _compact_creator_profile(
        user_context: dict[str, Any],
    ) -> dict[str, Any]:
        """Keep creator context useful without shipping empty/profile metadata."""

        if not isinstance(user_context, dict):
            return {}

        compact: dict[str, Any] = {}
        for key in (
            "creator_id",
            "name",
            "facts",
            "preferences",
            "interests",
            "values",
            "goals",
            "communication_style",
        ):
            value = user_context.get(key)
            if value not in (None, "", [], {}):
                compact[key] = value

        # profile_records duplicate the normalized facts/preferences/goals above
        # and carry IDs/timestamps that do not help dialogue generation. Keep them
        # in Mary's runtime state, not in every LLM request.
        return compact

    @staticmethod
    def _compact_turn_mind_state(
        context: CognitiveContext,
    ) -> dict[str, Any]:
        """Project TurnMindState into the information dialogue actually needs.

        Mary's runtime still owns the full integrated state. This projection is
        only the LLM-facing view for ordinary conversation, preventing every
        turn from serializing biography, agency, character, disposition, and
        performance structures in full.
        """

        mind = context.mind_state if isinstance(context.mind_state, dict) else {}
        if not mind:
            return {}

        personality = mind.get("personality", {}) or {}
        character = mind.get("character", {}) or {}
        relationship = mind.get("relationship", {}) or {}
        continuity = mind.get("continuity", {}) or {}
        disposition = mind.get("disposition", {}) or {}
        performance = mind.get("performance", {}) or {}
        agency = mind.get("agency", {}) or {}

        traits = personality.get("traits", {}) if isinstance(personality, dict) else {}
        style = personality.get("style", {}) if isinstance(personality, dict) else {}

        values = []
        for item in list(mind.get("values", []) or [])[:8]:
            if isinstance(item, dict):
                values.append({
                    "name": item.get("name"),
                    "strength": item.get("strength"),
                })

        positives: list[dict[str, Any]] = []
        negatives: list[dict[str, Any]] = []
        for item in list(mind.get("preferences", []) or []):
            if not isinstance(item, dict):
                continue
            view = {
                "name": item.get("name"),
                "category": item.get("category"),
            }
            polarity = float(item.get("polarity", 0.0) or 0.0)
            if polarity > 0 and len(positives) < 8:
                positives.append(view)
            elif polarity < 0 and len(negatives) < 8:
                negatives.append(view)
            if len(positives) >= 8 and len(negatives) >= 8:
                break

        behavior = character.get("behavior", {}) if isinstance(character, dict) else {}
        speech = character.get("speech", {}) if isinstance(character, dict) else {}
        romance = character.get("romance", {}) if isinstance(character, dict) else {}
        vulnerabilities = character.get("vulnerabilities", {}) if isinstance(character, dict) else {}

        return {
            "identity": mind.get("identity", {}),
            "personality": {
                "traits": traits,
                "style": style,
            },
            "character": {
                "archetype": character.get("archetype") if isinstance(character, dict) else None,
                "qualities": list(character.get("qualities", []) or [])[:10] if isinstance(character, dict) else [],
                "mannerisms": list(character.get("mannerisms", []) or [])[:6] if isinstance(character, dict) else [],
                "humor_style": list(character.get("humor_style", []) or [])[:6] if isinstance(character, dict) else [],
                "behavior": behavior,
                "social_modes": {
                    key: (character.get("social_modes", {}) or {}).get(key)
                    for key in ("strangers", "close_people", "distrust")
                    if isinstance(character, dict) and key in (character.get("social_modes", {}) or {})
                },
                "reactions": {
                    key: (character.get("reactions", {}) or {}).get(key)
                    for key in ("anger", "embarrassment", "excitement")
                    if isinstance(character, dict) and key in (character.get("reactions", {}) or {})
                },
                "quirks": list(character.get("quirks", []) or [])[:6] if isinstance(character, dict) else [],
                "speech": {
                    "vocabulary": list(speech.get("vocabulary", []) or [])[:7] if isinstance(speech, dict) else [],
                    "style": speech.get("style") if isinstance(speech, dict) else None,
                    "rule": speech.get("rule") if isinstance(speech, dict) else None,
                },
                "romance": romance,
                "vulnerabilities": vulnerabilities,
                "private_activities": list(character.get("private_activities", []) or [])[:10] if isinstance(character, dict) else [],
            },
            "values": values,
            "preferences": {
                "likes": positives,
                "dislikes": negatives,
            },
            "relationship": {
                "creator_name": relationship.get("creator_name") if isinstance(relationship, dict) else None,
                "role": relationship.get("role") if isinstance(relationship, dict) else None,
                "familiarity": relationship.get("familiarity") if isinstance(relationship, dict) else None,
            },
            "emotion": mind.get("emotion", {}),
            "agency": {
                "top_priorities": list(agency.get("top_priorities", []) or [])[:5] if isinstance(agency, dict) else [],
                "active_curiosities": list(agency.get("active_curiosities", []) or [])[:5] if isinstance(agency, dict) else [],
            },
            "continuity": {
                "drive": continuity.get("drive") if isinstance(continuity, dict) else None,
                "allow_follow_up_question": continuity.get("allow_follow_up_question") if isinstance(continuity, dict) else None,
                "recent_openings": list(continuity.get("recent_openings", []) or [])[-4:] if isinstance(continuity, dict) else [],
                "recent_distinctive_terms": list(continuity.get("recent_distinctive_terms", []) or [])[-8:] if isinstance(continuity, dict) else [],
            },
            "disposition": {
                key: disposition.get(key)
                for key in (
                    "mode",
                    "warmth",
                    "curiosity",
                    "playfulness",
                    "directness",
                    "formality",
                    "verbosity",
                    "independence",
                    "expressiveness",
                    "familiarity",
                    "preferred_length",
                    "allow_teasing",
                    "allow_opinion",
                )
                if key in disposition
            },
            "performance": {
                key: performance.get(key)
                for key in (
                    "energy",
                    "spontaneity",
                    "theatricality",
                    "intimacy",
                    "pacing",
                    "emotional_color",
                    "opening_style",
                    "ending_style",
                    "allow_fragments",
                    "allow_interjections",
                    "allow_thinking_aloud",
                )
                if key in performance
            },
            "constraints": list(mind.get("constraints", []) or []),
        }

    def _build_prompt(
        self,
        context: CognitiveContext,
        intent: Intent | None,
    ) -> str:
        """Build the cognitive prompt sent to the LLM."""

        if self._has_self_evidence(context):
            return self._build_self_prompt(
                context=context,
                intent=intent,
            )

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
                "Compact TurnMindState (authoritative Mary state selected for this turn):\n"
                f"{self._compact_turn_mind_state(context)}"
            )

        if context.user_context:
            creator_profile = self._compact_creator_profile(
                context.user_context
            )
            if creator_profile:
                sections.append(
                    "Creator profile — facts about Unbe only, NOT Mary:\n"
                    "Everything in this block describes Unbe, Mary's creator/user. "
                    "Never adopt these facts, preferences, interests, values, goals, "
                    "communication traits, memories, or profile records as Mary's own. "
                    "When referring to them, say 'you/your' or 'Unbe/Unbe\'s', never "
                    "'I/my' unless directly quoting Unbe.\n"
                    f"{creator_profile}"
                )

        if context.active_goals:
            sections.append(
                "Active goals:\n"
                f"{context.active_goals}"
            )

        continuity = context.mind_state.get("continuity", {}) if isinstance(context.mind_state, dict) else {}
        drive = continuity.get("drive", "react")
        allow_question = bool(continuity.get("allow_follow_up_question", True))

        sections.append(
            "Conversation continuity instructions:\n"
            f"Primary drive: {drive}. Follow-up question allowed: {allow_question}. "
            "Avoid repeating Mary's immediately recent opening, metaphor, punchline, or question pattern. "
            "If the previous Mary turn ended in a question, prefer a statement/opinion/reaction now unless another "
            "question genuinely improves the turn. Curiosity does not require a question."
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
