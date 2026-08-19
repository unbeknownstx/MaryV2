"""
MaryV2 - Cognitive Orchestrator

Coordinates Mary's cognitive cycle.

The orchestrator connects:

    Input
      ↓
    Context
      ↓
    Intent
      ↓
    Reasoning
      ↓
    Reflection
      ↓
    Response

Subsystem actions such as memory storage are coordinated by Mary.

The orchestrator is responsible for cognition, not subsystem ownership.
"""

from dataclasses import dataclass, field
import re
from typing import Any

from mary.cognition.context import CognitiveContext
from mary.cognition.continuity import is_conversation_recall_query
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


# ================================================================
# CYCLE RESULT
# ================================================================


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
        """
        Convert the complete cycle into a dictionary.
        """

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


# ================================================================
# ORCHESTRATOR
# ================================================================


class CognitiveOrchestrator:
    """
    Coordinates Mary's cognitive pipeline.

    The orchestrator does not own memory, personality, learning,
    relationships, or other Mary subsystems.

    Those systems provide context to cognition through Mary.
    """

    def __init__(
        self,
        reasoning_engine: ReasoningEngine,
        reflection_engine: ReflectionEngine,
    ) -> None:

        self.reasoning_engine = reasoning_engine
        self.reflection_engine = reflection_engine

    # ============================================================
    # PROCESS
    # ============================================================

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
        mind_state: dict[str, Any] | None = None,
    ) -> CognitiveCycleResult:
        """
        Run one complete cognitive cycle.
        """

        context = CognitiveContext(
            input_text=input_text,
        )

        # --------------------------------------------------------
        # BUILD CONTEXT
        # --------------------------------------------------------

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

        if mind_state:
            context.mind_state.update(
                mind_state
            )

        # --------------------------------------------------------
        # INTENT
        # --------------------------------------------------------

        if intent is None:
            intent = self.detect_intent(
                input_text
            )

        # --------------------------------------------------------
        # REASONING
        # --------------------------------------------------------

        reasoning = self.reasoning_engine.reason(
            context=context,
            intent=intent,
        )

        # --------------------------------------------------------
        # REFLECTION
        # --------------------------------------------------------

        reflection = self.reflection_engine.reflect(
            context=context,
            reasoning=reasoning,
            intent=intent,
        )

        # --------------------------------------------------------
        # RESPONSE
        # --------------------------------------------------------

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

    # ============================================================
    # INTENT DETECTION
    # ============================================================

    def detect_intent(
        self,
        input_text: str,
    ) -> Intent:
        """
        Detect the user's intent.

        This is the public V2 intent-detection interface.

        A more advanced hybrid or model-based detector can replace
        the deterministic implementation later without requiring
        Mary or other systems to change their API.
        """

        text = str(
            input_text
        ).strip()

        if not text:

            return Intent(
                intent_type=IntentType.UNKNOWN,
                confidence=1.0,
                description="Empty input.",
                source="basic_detector",
            )

        lowered = text.lower()

        # --------------------------------------------------------
        # MEMORY STORE
        # --------------------------------------------------------

        memory_store = self._detect_memory_store(
            text=text,
            lowered=lowered,
        )

        if memory_store is not None:
            return memory_store

        # --------------------------------------------------------
        # RELATIONSHIP SHARING / CREATOR MODEL QUERIES
        # --------------------------------------------------------

        relationship_share = self._detect_relationship_share(
            text=text,
            lowered=lowered,
        )
        if relationship_share is not None:
            return relationship_share

        relationship_query = self._detect_relationship_query(
            text=text,
            lowered=lowered,
        )
        if relationship_query is not None:
            return relationship_query

        # --------------------------------------------------------
        # RECENT CONVERSATION RECALL
        # --------------------------------------------------------

        if is_conversation_recall_query(text):
            return Intent(
                intent_type=IntentType.CONVERSATION_RECALL,
                confidence=0.98,
                description=(
                    "Input requests recall from the active/recent dialogue rather "
                    "than long-term memory."
                ),
                parameters={"query": text},
                source="continuity_detector",
            )

        # --------------------------------------------------------
        # MEMORY RECALL
        # --------------------------------------------------------

        recall_phrases = (
            "what do you remember",
            "what don't i like",
            "what dont i like",
            "what do i like",
            "what are my preferences",
            "my favorite",
            "my favourite",
            "my favorites",
            "my favourites",
            "do you remember",
            "remember about me",
        )

        if any(
            phrase in lowered
            for phrase in recall_phrases
        ):

            return Intent(
                intent_type=IntentType.MEMORY_RECALL,
                confidence=0.9,
                description=(
                    "Input appears to request "
                    "information from memory."
                ),
                parameters={
                    "query": text
                },
                source="basic_detector",
            )

        # --------------------------------------------------------
        # TOOL APPROVAL / REJECTION
        # --------------------------------------------------------

        tool_control = self._detect_tool_control(
            text=text,
            lowered=lowered,
        )

        if tool_control is not None:
            return tool_control

        # --------------------------------------------------------
        # CREATOR DIRECTIVES
        # --------------------------------------------------------

        creator_directive = self._detect_creator_directive(
            text=text,
            lowered=lowered,
        )

        if creator_directive is not None:
            return creator_directive

        # --------------------------------------------------------
        # SELF INTROSPECTION
        # --------------------------------------------------------

        self_query = self._detect_self_query(
            text=text,
            lowered=lowered,
        )

        if self_query is not None:
            return self_query

        # --------------------------------------------------------
        # WEB / EXTERNAL RESEARCH
        # --------------------------------------------------------

        web_intent = self._detect_web_intent(
            text=text,
            lowered=lowered,
        )

        if web_intent is not None:
            return web_intent

        # --------------------------------------------------------
        # LOCAL FILESYSTEM / CODE TOOLS
        # --------------------------------------------------------

        local_tool_intent = self._detect_local_tool_intent(
            text=text,
            lowered=lowered,
        )

        if local_tool_intent is not None:
            return local_tool_intent

        # --------------------------------------------------------
        # QUESTION
        # --------------------------------------------------------

        if lowered.endswith("?"):

            return Intent(
                intent_type=IntentType.QUESTION,
                confidence=0.8,
                description=(
                    "Input appears to be a question."
                ),
                source="basic_detector",
            )

        # --------------------------------------------------------
        # REQUEST
        # --------------------------------------------------------

        request_prefixes = (
            "please ",
            "do ",
            "make ",
            "create ",
            "find ",
            "tell me ",
        )

        if lowered.startswith(
            request_prefixes
        ):

            return Intent(
                intent_type=IntentType.REQUEST,
                confidence=0.7,
                description=(
                    "Input appears to contain a request."
                ),
                source="basic_detector",
            )

        # --------------------------------------------------------
        # GOAL
        # --------------------------------------------------------

        if "goal" in lowered:

            return Intent(
                intent_type=IntentType.GOAL,
                confidence=0.8,
                description=(
                    "Input appears to concern a goal."
                ),
                source="basic_detector",
            )

        # --------------------------------------------------------
        # DEFAULT
        # --------------------------------------------------------

        return Intent(
            intent_type=IntentType.CONVERSATION,
            confidence=0.6,
            description=(
                "Input appears to be general conversation."
            ),
            source="basic_detector",
        )

    # ============================================================
    # TOOL / WEB INTENT DETECTION
    # ============================================================

    def _detect_relationship_share(
        self,
        *,
        text: str,
        lowered: str,
    ) -> Intent | None:
        """Detect explicit requests for Mary to learn structured creator information."""

        normalized = re.sub(r"\s+", " ", text.strip())
        match = re.match(
            r"^(?:learn this about me|know this about me|add this to what you know about me)\s*:\s*(.+)$",
            normalized,
            flags=re.IGNORECASE,
        )
        if match is None:
            return None

        content = match.group(1).strip()
        if not content:
            return None

        return Intent(
            intent_type=IntentType.RELATIONSHIP_SHARE,
            confidence=0.99,
            description=(
                "Creator explicitly asked Mary to add information to her structured creator model."
            ),
            parameters={
                "content": content,
                "force_general": True,
            },
            source="basic_detector",
        )

    def _detect_relationship_query(
        self,
        *,
        text: str,
        lowered: str,
    ) -> Intent | None:
        """Detect local questions about Mary's structured understanding of Unbe."""

        normalized = re.sub(r"\s+", " ", lowered.strip()).rstrip("?.!")
        query_map = {
            "what do you know about me": "overview",
            "do you remember anything about me": "memory_overview",
            "do you remember me": "memory_overview",
            "what do you remember about me": "memory_overview",
            "tell me what you remember about me": "memory_overview",
            "what do you know about my interests": "interests",
            "what interests do you know i have": "interests",
            "what are my interests": "interests",
            "what do you know about my goals": "goals",
            "what goals do you know i have": "goals",
            "what are my goals": "goals",
            "what do you know about my values": "values",
            "what values do you know i have": "values",
            "what do you know about my preferences": "preferences",
            "what preferences do you know i have": "preferences",
            "what is your structured relationship history with me": "history",
            "what have you learned about me": "overview",
            "what are you curious about regarding me": "curiosity_gaps",
            "what are you still curious about regarding me": "curiosity_gaps",
            "what are you curious about when it comes to me": "curiosity_gaps",
            "what don't you know about me": "curiosity_gaps",
            "what dont you know about me": "curiosity_gaps",
            "what do you still not know about me": "curiosity_gaps",
        }
        query_type = query_map.get(normalized)
        if query_type is None:
            return None

        return Intent(
            intent_type=IntentType.RELATIONSHIP_QUERY,
            confidence=0.98,
            description=(
                "Input asks about Mary's persistent structured creator model."
            ),
            parameters={
                "query": text,
                "relationship_query_type": query_type,
            },
            source="basic_detector",
        )

    def _detect_tool_control(
        self,
        *,
        text: str,
        lowered: str,
    ) -> Intent | None:
        """Detect explicit creator approval or rejection of tool requests.

        A full request id is still the most precise form.  For terminal usability,
        a bare ``approve``/``reject`` is also treated as an explicit creator
        decision.  The Mary coordinator resolves that shorthand only when there
        is exactly one pending request; it never guesses among multiple requests.
        """

        normalized = re.sub(
            r"\s+",
            " ",
            lowered.strip(),
        )

        bare_approve = {
            "approve",
            "approve it",
            "approve request",
            "approve the request",
            "yes approve",
            "yes, approve",
        }
        bare_reject = {
            "reject",
            "reject it",
            "reject request",
            "reject the request",
            "deny",
            "deny it",
        }

        if normalized in bare_approve:
            return Intent(
                intent_type=IntentType.TOOL_USE,
                confidence=0.99,
                description=(
                    "Creator explicitly approves the single pending tool request."
                ),
                parameters={
                    "action": "approve",
                    "request_id": "",
                    "resolve_single_pending": True,
                },
                source="basic_detector",
            )

        if normalized in bare_reject:
            return Intent(
                intent_type=IntentType.TOOL_USE,
                confidence=0.99,
                description=(
                    "Creator explicitly rejects the single pending tool request."
                ),
                parameters={
                    "action": "reject",
                    "request_id": "",
                    "resolve_single_pending": True,
                },
                source="basic_detector",
            )

        request_match = re.search(
            r"\brequest_[0-9a-fA-F]+\b",
            text,
        )

        if request_match is None:
            return None

        request_id = request_match.group(0)

        if normalized.startswith((
            "approve ",
            "yes approve ",
            "yes, approve ",
            "approve tool ",
            "approve request",
        )):
            return Intent(
                intent_type=IntentType.TOOL_USE,
                confidence=0.99,
                description=(
                    "Creator explicitly approves a pending tool request."
                ),
                parameters={
                    "action": "approve",
                    "request_id": request_id,
                },
                source="basic_detector",
            )

        if normalized.startswith((
            "reject ",
            "deny ",
            "no reject ",
            "reject tool ",
            "reject request",
        )):
            return Intent(
                intent_type=IntentType.TOOL_USE,
                confidence=0.99,
                description=(
                    "Creator explicitly rejects a pending tool request."
                ),
                parameters={
                    "action": "reject",
                    "request_id": request_id,
                },
                source="basic_detector",
            )

        return None

    def _detect_creator_directive(
        self,
        *,
        text: str,
        lowered: str,
    ) -> Intent | None:
        """Detect explicit creator directions about Mary's internal priorities."""

        normalized = re.sub(r"\s+", " ", lowered.strip()).rstrip("?.!")

        # Console/status output can be pasted back as a directive. Normalize a
        # harmless trailing score annotation so `Learn more about Unbe (score
        # 1.00)` still resolves to the same local creator directive instead of
        # falling through to the language model.
        explicit_score: float | None = None
        score_match = re.search(
            r"\s*\(\s*score\s+([01](?:\.\d+)?)\s*\)\s*$",
            normalized,
        )
        if score_match is not None:
            try:
                explicit_score = max(0.0, min(1.0, float(score_match.group(1))))
            except (TypeError, ValueError):
                explicit_score = None
            normalized = normalized[:score_match.start()].strip()

        # V2 begins with a deliberately narrow, high-confidence directive:
        # Unbe explicitly tells Mary that understanding/learning about her
        # creator should be an active curiosity or top priority.
        creator_curiosity_patterns = (
            r"^(?:you should )?be curious about (?:me|unbe)(?: top priority)?$",
            r"^you should be curious about (?:me|unbe)(?:,? )?(?:as )?(?:a )?top priority$",
            r"^make (?:learning|understanding|knowing more) about (?:me|unbe) (?:a )?top priority$",
            r"^(?:learning|understanding|knowing more) about (?:me|unbe) (?:is|should be) (?:a )?top priority$",
            r"^(?:unbe|your creator) (?:is|should be) your top priority$",
            r"^prioritize (?:learning|understanding|knowing more) about (?:me|unbe)$",
            r"^learn more about (?:me|unbe)$",
        )

        if any(re.fullmatch(pattern, normalized) for pattern in creator_curiosity_patterns):
            top_priority = (
                "top priority" in normalized
                or normalized.startswith("prioritize ")
                or (explicit_score is not None and explicit_score >= 0.999)
            )
            priority = (
                explicit_score
                if explicit_score is not None
                else (1.0 if top_priority else 0.9)
            )
            return Intent(
                intent_type=IntentType.CREATOR_DIRECTIVE,
                confidence=0.99,
                description=(
                    "Creator explicitly directed Mary to prioritize learning "
                    "about her creator as an internal curiosity."
                ),
                parameters={
                    "directive_type": "creator_curiosity",
                    "target": "unbe",
                    "instruction": text,
                    "priority": priority,
                    "top_priority": top_priority,
                },
                source="basic_detector",
            )

        return None

    def _detect_self_query(
        self,
        *,
        text: str,
        lowered: str,
    ) -> Intent | None:
        """Detect questions about Mary's own local state before web routing."""

        normalized = re.sub(r"\s+", " ", lowered.strip()).rstrip("?.!")

        patterns: tuple[tuple[str, tuple[str, ...]], ...] = (
            ("runtime_architecture", (
                "what is your underlying architecture running on",
                "what's your underlying architecture running on",
                "what is your underlying architecture",
                "what's your underlying architecture",
                "what model are you using",
                "what model are you running",
                "which model are you using",
                "which provider are you using",
                "what provider are you using",
                "which api are you using",
                "what api are you using",
                "what are you running on",
                "are you local or cloud",
                "what generated your last answer",
                "what generated your last response",
            )),
            ("creator", (
                "who is unbe to you",
                "who is your creator",
                "who created you",
            )),
            ("self_understanding", (
                "what parts of yourself do you currently understand",
                "what parts of yourself do you understand",
                "what do you understand about yourself",
            )),
            ("current_state", (
                "how are you feeling about yourself right now",
                "how are you feeling about yourself",
                "how do you feel about yourself right now",
                "how do you feel about yourself",
                "how are you feeling about who you are right now",
            )),
            ("values", (
                "what are your values",
                "what do you value",
                "what matters to you",
            )),
            ("relationship", (
                "what do you think your relationship with unbe should be",
                "what should your relationship with unbe be",
                "what is your relationship with unbe",
            )),
            ("personality", (
                "do you have your own personality, or are you just copying mine",
                "do you have your own personality or are you just copying mine",
                "do you have your own personality",
                "what is your personality",
                "what's your personality",
            )),
            ("vulnerabilities", (
                "what are you afraid of",
                "what do you fear",
                "what scares you",
                "what are your fears",
                "what are your weaknesses",
                "what are your soft spots",
            )),
            ("romance", (
                "are you romantic",
                "what are you like romantically",
                "what are you like in a relationship",
                "how are you in relationships",
                "what is your romantic side like",
            )),
            ("reactions", (
                "how do you act when you're angry",
                "how do you act when you are angry",
                "what are you like when you're angry",
                "what are you like when you are angry",
                "how do you act when you're embarrassed",
                "how do you act when you are embarrassed",
            )),
            ("social_behavior", (
                "how do you behave around strangers vs close friends",
                "how do you behave around strangers versus close friends",
                "how are you around strangers",
                "how are you around close friends",
                "how do you treat people you don't trust",
                "how do you treat people you do not trust",
                "how do you act when you know you're being watched",
                "how do you act when you know you are being watched",
            )),
            ("private_life", (
                "what do you do when you're alone",
                "what do you do when you are alone",
                "what do you do by yourself",
            )),
            ("speech", (
                "how do you talk",
                "what kind of slang do you use",
                "what slang do you use",
                "what are some things you say",
            )),
            ("goals", (
                "what are your long-term goals",
                "what are your long term goals",
                "what do you want in life",
                "what do you want personally",
                "what are your personal goals",
            )),
            ("curiosity", (
                "what are you curious about right now",
                "what are you curious about",
                "what are your current curiosities",
            )),
            ("priorities", (
                "what are your priorities",
                "what is your top priority",
                "what's your top priority",
                "what are you prioritizing right now",
            )),
            ("disagreement", (
                "if unbe tells you something you believe is a bad idea, would you disagree with him",
                "would you disagree with unbe",
                "can you disagree with unbe",
            )),
            ("purpose", (
                "what do you think you should become",
                "what should you become",
                "what is your purpose",
                "what's your purpose",
            )),
            ("capabilities", (
                "what are you currently unable to do",
                "what are you unable to do",
                "what can you do",
                "what are your capabilities",
            )),
            ("appearance", (
                "what color is your hair",
                "what colour is your hair",
                "what does your hair look like",
                "what do you look like",
                "what is your appearance",
                "what's your appearance",
                "describe your appearance",
                "describe what you look like",
            )),
            ("preferences", (
                "what is your favorite color",
                "what's your favorite color",
                "what is your favourite colour",
                "what's your favourite colour",
                "what are your preferences",
                "what do you like",
                "what do you enjoy",
                "what do you do for fun",
                "what do you hate",
                "what do you dislike",
                "what foods do you hate",
                "what food do you hate",
                "what makes you laugh",
                "what do you consider funny",
                "what do you find funny",
            )),
            ("identity", (
                "who are you",
                "who are you, and what makes you different from a generic ai assistant",
                "what makes you different from a generic ai assistant",
                "tell me about yourself",
            )),
        )

        def self_intent(subtype: str) -> Intent:
            return Intent(
                intent_type=IntentType.SELF_QUERY,
                confidence=0.98,
                description=(
                    "Input asks about Mary's own connected identity or runtime state."
                ),
                parameters={
                    "self_query_type": subtype,
                    "query": text,
                },
                source="basic_detector",
            )

        for subtype, phrases in patterns:
            if normalized in phrases:
                return self_intent(subtype)

        runtime_markers = (
            "your underlying architecture",
            # Natural architecture questions should never fall through to a
            # language model that can invent its own provider-centric identity.
            # Keep this deliberately scoped to *Mary's* architecture.
            "your architecture",
            "your architecture running",
            "model are you using",
            "model are you running",
            "model do you use",
            "provider are you using",
            "provider do you use",
            "api are you using",
            "api do you use",
            "are you local or cloud",
            "running locally or",
            "running in the cloud",
            "generated your last answer",
            "generated your last response",
            "generated that answer",
            "generated that response",
        )
        if any(marker in normalized for marker in runtime_markers):
            return self_intent("runtime_architecture")

        # Physical self-questions have too many natural phrasings to maintain
        # as a brittle exact-phrase list. Route them to Mary's canonical
        # appearance evidence instead of letting a provider answer from its own
        # generic "I am only software" identity.
        appearance_markers = (
            "your hair",
            "your eyes",
            "your eye color",
            "your eye colour",
            "your height",
            "your appearance",
            "your outfit",
            "your clothes",
            "your clothing",
            "your beanie",
            "your jacket",
            "your shirt",
            "your skirt",
            "your socks",
            "your boots",
            "you look like",
        )
        if any(marker in normalized for marker in appearance_markers):
            return self_intent("appearance")

        # Preference questions about Mary must stay separate from the creator
        # profile. This also prevents a creator preference such as a favorite
        # color from being adopted as Mary's merely because it appears nearby in
        # conversational context.
        if (
            "your favorite " in normalized
            or "your favourite " in normalized
            or normalized.startswith("what do you prefer")
            or normalized.startswith("what do you like")
            or normalized.startswith("what do you enjoy")
            or normalized.startswith("what do you hate")
            or normalized.startswith("what do you dislike")
            or "do for fun" in normalized
            or "your hobbies" in normalized
            or "your free time" in normalized
            or "makes you laugh" in normalized
            or "you find funny" in normalized
            or "you consider funny" in normalized
        ):
            return self_intent("preferences")

        # Character-core questions also have many natural phrasings. Keep them
        # local and grounded instead of asking the provider to invent a persona.
        if any(marker in normalized for marker in (
            "you afraid of", "you scared of", "your fears", "your weaknesses", "your soft spots"
        )):
            return self_intent("vulnerabilities")

        if any(marker in normalized for marker in (
            "you romantic", "romantic side", "romantically", "in a relationship"
        )):
            return self_intent("romance")

        if any(marker in normalized for marker in (
            "when you're angry", "when you are angry", "when you're embarrassed", "when you are embarrassed"
        )):
            return self_intent("reactions")

        if any(marker in normalized for marker in (
            "around strangers", "close friends", "people you don't trust",
            "people you do not trust", "being watched", "you are being watched"
        )):
            return self_intent("social_behavior")

        if any(marker in normalized for marker in (
            "when you're alone", "when you are alone", "by yourself"
        )):
            return self_intent("private_life")

        if any(marker in normalized for marker in (
            "your slang", "you talk", "things you say"
        )):
            return self_intent("speech")

        if any(marker in normalized for marker in (
            "your long-term goals", "your long term goals", "your personal goals", "you want in life"
        )):
            return self_intent("goals")

        if (
            "feel about yourself" in normalized
            or "feeling about yourself" in normalized
            or "feel about who you are" in normalized
            or "feeling about who you are" in normalized
        ):
            return self_intent("current_state")

        if any(marker in normalized for marker in (
            "what kinds of people do you get along with",
            "what kind of people do you get along with",
            "who do you get along with",
            "micromanag",
        )):
            return self_intent("social_behavior")

        return None

    def _detect_web_intent(
        self,
        *,
        text: str,
        lowered: str,
    ) -> Intent | None:
        """
        Detect purposeful external-information requests.

        Explicit search/fetch wording is treated as creator authorization for
        that exact network request. Questions that merely appear time-sensitive
        may create a pending request, but are not automatically authorized.
        """

        url_match = re.search(
            r"https?://[^\s<>\"]+",
            text,
            flags=re.IGNORECASE,
        )

        explicit_fetch_markers = (
            "check this website",
            "check this page",
            "open this website",
            "open this page",
            "read this website",
            "read this page",
            "fetch this url",
            "check the website",
            "check the page",
        )

        if (
            url_match is not None
            and (
                any(marker in lowered for marker in explicit_fetch_markers)
                or lowered.startswith(("fetch ", "open ", "read ", "check "))
            )
        ):
            url = url_match.group(0).rstrip(
                ".,);]}'"
            )
            return Intent(
                intent_type=IntentType.WEB_SEARCH,
                confidence=0.98,
                description=(
                    "Creator explicitly requested retrieval of a web page."
                ),
                parameters={
                    "operation": "fetch",
                    "url": url,
                    "query": text,
                    "explicit_creator_request": True,
                },
                source="basic_detector",
            )

        explicit_prefixes = (
            "search the web for ",
            "search web for ",
            "search online for ",
            "look up ",
            "look this up ",
            "look this up: ",
            "research ",
            "research this ",
            "find documentation for ",
            "find docs for ",
            "find online ",
        )

        for prefix in explicit_prefixes:
            if lowered.startswith(prefix):
                query = text[len(prefix):].strip()
                if not query:
                    query = text

                return Intent(
                    intent_type=IntentType.WEB_SEARCH,
                    confidence=0.97,
                    description=(
                        "Creator explicitly requested a public web search."
                    ),
                    parameters={
                        "operation": "search",
                        "query": query,
                        "explicit_creator_request": True,
                    },
                    source="basic_detector",
                )

        if lowered.startswith("find "):
            web_find_markers = (
                " near me",
                " restaurant",
                " restaurants",
                " food",
                " website",
                " websites",
                " documentation",
                " docs",
                " online",
                " current ",
                " latest ",
            )

            if any(
                marker in f" {lowered} "
                for marker in web_find_markers
            ):
                return Intent(
                    intent_type=IntentType.WEB_SEARCH,
                    confidence=0.92,
                    description=(
                        "Creator explicitly requested information that requires public search."
                    ),
                    parameters={
                        "operation": "search",
                        "query": text,
                        "explicit_creator_request": True,
                    },
                    source="basic_detector",
                )

        # Dynamic-information questions can trigger a proposed search, but not
        # creator approval. Mary must ask before network execution.
        dynamic_markers = (
            "latest",
            "current",
            "today",
            "recent",
            "news",
            "weather",
            "price",
            "prices",
            "near me",
            "right now",
            "this week",
            "documentation",
        )

        if (
            lowered.endswith("?")
            and any(marker in lowered for marker in dynamic_markers)
        ):
            return Intent(
                intent_type=IntentType.WEB_SEARCH,
                confidence=0.78,
                description=(
                    "Input appears to need current external information."
                ),
                parameters={
                    "operation": "search",
                    "query": text,
                    "explicit_creator_request": False,
                },
                source="basic_detector",
            )

        return None

    def _detect_local_tool_intent(
        self,
        *,
        text: str,
        lowered: str,
    ) -> Intent | None:
        """
        Detect intentional local filesystem and static-code operations.

        Read-only operations map to SAFE ToolRegistry capabilities. Mutating
        operations are only identified here; Mary still creates a pending
        request and requires a separate creator approval before execution.
        """

        def make(
            tool_name: str,
            arguments: dict[str, Any],
            description: str,
        ) -> Intent:
            return Intent(
                intent_type=IntentType.TOOL_USE,
                confidence=0.96,
                description=description,
                parameters={
                    "action": "execute_tool",
                    "tool_name": tool_name,
                    "arguments": arguments,
                    "explicit_creator_request": True,
                },
                source="basic_detector",
            )

        def clean(value: str) -> str:
            return value.strip().strip('"\'').rstrip("?.")

        def looks_like_path(value: str) -> bool:
            candidate = clean(value)
            if not candidate or candidate.startswith(("http://", "https://")):
                return False
            if any(sep in candidate for sep in ("/", "\\")):
                return True
            return bool(
                re.search(
                    r"\.(?:py|pyi|json|toml|ya?ml|md|txt|ini|cfg|csv|html?|css|js|ts|tsx|jsx)$",
                    candidate,
                    flags=re.IGNORECASE,
                )
            )

        # --------------------------------------------------------
        # GROUNDED CODE CHANGE PROPOSALS
        # --------------------------------------------------------
        # Detecting the request does not modify source code. Mary first
        # produces a bounded exact-edit proposal, validates it, displays the
        # unified diff, and then creates a separate approval-gated apply request.

        source_extension = (
            r"(?:py|pyi|js|jsx|ts|tsx|json|toml|ya?ml|md|html?|css|sql|sh)"
        )
        change_patterns = (
            rf"^(?:change|modify|edit|update)\s+(?:file\s+)?(.+?\.{source_extension})\s+"
            rf"(?:so that|so|to|by|:)\s*(.+)$",
            rf"^fix\s+(?:file\s+)?([^\s]+\.{source_extension})\s+(.+)$",
            rf"^propose (?:a )?change to\s+(.+?\.{source_extension})\s+"
            rf"(?:so that|so|to|by|:)\s*(.+)$",
        )

        for pattern in change_patterns:
            match = re.match(
                pattern,
                text,
                flags=re.IGNORECASE | re.DOTALL,
            )
            if match:
                path = clean(match.group(1))
                instruction = match.group(2).strip()
                if path and instruction:
                    return Intent(
                        intent_type=IntentType.TOOL_USE,
                        confidence=0.98,
                        description=(
                            "Creator requested a grounded source-code change "
                            "proposal. Applying it requires separate approval."
                        ),
                        parameters={
                            "action": "propose_code_change",
                            "path": path,
                            "instruction": instruction,
                            "explicit_creator_request": True,
                        },
                        source="basic_detector",
                    )

        # --------------------------------------------------------
        # SEARCH INSIDE THE PROJECT
        # --------------------------------------------------------

        search_patterns = (
            r"^search (?:the )?project for (.+)$",
            r"^search (?:the )?files for (.+)$",
            r"^find in (?:the )?project (.+)$",
            r"^find where (.+?) is used\??$",
            r"^find usages of (.+)$",
            r"^find references to (.+)$",
        )
        for pattern in search_patterns:
            match = re.match(pattern, text, flags=re.IGNORECASE)
            if match:
                query = clean(match.group(1))
                if query:
                    return make(
                        "filesystem_search",
                        {
                            "query": query,
                            "path": ".",
                            "max_matches": 50,
                        },
                        "Creator requested a bounded text search inside Mary's workspace.",
                    )

        # --------------------------------------------------------
        # DIRECTORY LISTING
        # --------------------------------------------------------

        list_prefixes = (
            "list files in ",
            "list directory ",
            "list folder ",
            "show files in ",
            "show me what's in ",
            "show me what is in ",
        )
        for prefix in list_prefixes:
            if lowered.startswith(prefix):
                path = clean(text[len(prefix):]) or "."
                return make(
                    "filesystem_list",
                    {"path": path},
                    "Creator requested a directory listing inside Mary's workspace.",
                )

        # --------------------------------------------------------
        # STATIC CODE INSPECTION
        # --------------------------------------------------------

        analysis_prefixes = (
            "analyze code ",
            "analyse code ",
            "analyze file ",
            "analyse file ",
            "analyze ",
            "analyse ",
            "inspect code ",
            "inspect file ",
            "inspect ",
        )
        for prefix in analysis_prefixes:
            if lowered.startswith(prefix):
                path = clean(text[len(prefix):])
                if not path:
                    continue
                tool_name = (
                    "code_analyze"
                    if path.lower().endswith((".py", ".pyi"))
                    else "filesystem_info"
                )
                return make(
                    tool_name,
                    {"path": path},
                    "Creator requested local static inspection without execution.",
                )

        # --------------------------------------------------------
        # FILE / SOURCE READ
        # --------------------------------------------------------

        read_prefixes = (
            "read file ",
            "read source ",
            "show file ",
            "show source ",
            "open file ",
            "read ",
        )
        for prefix in read_prefixes:
            if lowered.startswith(prefix):
                path = clean(text[len(prefix):])
                if not looks_like_path(path):
                    continue
                tool_name = (
                    "code_read"
                    if path.lower().endswith((
                        ".py", ".pyi", ".js", ".jsx", ".ts", ".tsx",
                        ".java", ".c", ".h", ".cpp", ".hpp", ".cs",
                        ".go", ".rs", ".rb", ".php", ".swift", ".kt",
                        ".kts", ".sh", ".ps1",
                    ))
                    else "filesystem_read"
                )
                return make(
                    tool_name,
                    {"path": path},
                    "Creator requested a bounded local file read.",
                )

        # --------------------------------------------------------
        # EXISTS / INFO
        # --------------------------------------------------------

        exists_match = re.match(
            r"^does (.+?) exist\??$",
            text,
            flags=re.IGNORECASE,
        )
        if exists_match and looks_like_path(exists_match.group(1)):
            return make(
                "filesystem_exists",
                {"path": clean(exists_match.group(1))},
                "Creator asked whether a local workspace path exists.",
            )

        for prefix in ("file info ", "info on file ", "info on "):
            if lowered.startswith(prefix):
                path = clean(text[len(prefix):])
                if looks_like_path(path):
                    return make(
                        "filesystem_info",
                        {"path": path},
                        "Creator requested local filesystem metadata.",
                    )

        # --------------------------------------------------------
        # MUTATING FILESYSTEM OPERATIONS
        # --------------------------------------------------------
        # These intents NEVER grant approval. Mary will create a pending
        # ToolRegistry request that requires a second explicit approval turn.

        write_match = re.match(
            r"^(?:write|create) file\s+(.+?)\s+(?:with|containing)\s+(.+)$",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if write_match:
            return make(
                "filesystem_write",
                {
                    "path": clean(write_match.group(1)),
                    "content": write_match.group(2),
                    "overwrite": False,
                },
                "Creator requested a filesystem write; separate approval is required.",
            )

        append_match = re.match(
            r"^append\s+(.+?)\s+to file\s+(.+)$",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if append_match:
            return make(
                "filesystem_append",
                {
                    "path": clean(append_match.group(2)),
                    "content": append_match.group(1),
                },
                "Creator requested a filesystem append; separate approval is required.",
            )

        for prefix in ("create directory ", "create folder ", "make directory ", "make folder "):
            if lowered.startswith(prefix):
                path = clean(text[len(prefix):])
                if path:
                    return make(
                        "filesystem_create_directory",
                        {"path": path},
                        "Creator requested directory creation; separate approval is required.",
                    )

        for prefix in ("delete file ", "remove file "):
            if lowered.startswith(prefix):
                path = clean(text[len(prefix):])
                if path:
                    return make(
                        "filesystem_delete",
                        {"path": path},
                        "Creator requested file deletion; separate approval is required.",
                    )

        move_match = re.match(
            r"^move file\s+(.+?)\s+to\s+(.+)$",
            text,
            flags=re.IGNORECASE,
        )
        if move_match:
            return make(
                "filesystem_move",
                {
                    "source": clean(move_match.group(1)),
                    "destination": clean(move_match.group(2)),
                },
                "Creator requested a file move; separate approval is required.",
            )

        return None

    # ============================================================
    # MEMORY INTENT DETECTION
    # ============================================================

    def _detect_memory_store(
        self,
        *,
        text: str,
        lowered: str,
    ) -> Intent | None:
        """
        Detect explicit requests to store information in memory.

        V2 remains deterministic: Mary only stores information
        automatically when the user clearly asks her to remember it.
        """

        # Natural explicit-memory forms can include a conversational lead-in,
        # e.g. "want to know something about me, remember this: ...".
        # Only the payload after an explicit remember-this/following marker is
        # stored; ordinary mentions of memory are not treated as authorization.
        explicit_payload_patterns = (
            r"\bremember\s+this\s*:\s*(.+)$",
            r"\bremember\s+the\s+following\s*:\s*(.+)$",
            r"\bi\s+want\s+you\s+to\s+remember\s+this\s*:\s*(.+)$",
            r"\bplease\s+remember\s+this\s*:\s*(.+)$",
        )

        for pattern in explicit_payload_patterns:
            match = re.search(
                pattern,
                text,
                flags=re.IGNORECASE | re.DOTALL,
            )
            if match is None:
                continue

            content = match.group(1).strip()
            if not content:
                continue

            return Intent(
                intent_type=IntentType.MEMORY_STORE,
                confidence=0.99,
                description=(
                    "Input explicitly requests that the following payload "
                    "be remembered."
                ),
                parameters={
                    "content": content
                },
                source="basic_detector",
            )

        # More specific phrases must appear before generic phrases.

        prefixes = (
            "remember that ",
            "remember ",
            "don't forget that ",
            "dont forget that ",
            "don't forget ",
            "dont forget ",
            "keep in mind that ",
            "keep in mind ",
            "i want you to remember that ",
            "i want you to remember ",
            "i need you to remember that ",
            "i need you to remember ",
            "please remember that ",
            "please remember ",
        )

        for prefix in prefixes:

            if lowered.startswith(
                prefix
            ):

                content = text[
                    len(prefix):
                ].strip()

                if not content:
                    continue

                return Intent(
                    intent_type=IntentType.MEMORY_STORE,
                    confidence=0.95,
                    description=(
                        "Input explicitly requests "
                        "that information be remembered."
                    ),
                    parameters={
                        "content": content
                    },
                    source="basic_detector",
                )

        return None

    # ============================================================
    # RESPONSE SELECTION
    # ============================================================

    def _select_response(
        self,
        reasoning: ReasoningResult,
        reflection: ReflectionResult,
    ) -> str:
        """
        Determine the final response.

        Reflection may influence response selection more deeply
        in later versions.

        V2 currently returns the reasoning response.
        """

        if (
            reflection.decision
            == ReflectionDecision.REVISE
            and reflection.revised_response
        ):
            return reflection.revised_response

        return reasoning.response