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
from time import monotonic
import re
from typing import Any

from mary.cognition.context import CognitiveContext
from mary.cognition.continuity import is_conversation_recall_query
from mary.cognition.intent import Intent, IntentType
from mary.cognition.natural_input import normalize_for_matching, looks_like_question
from mary.runtime.introspection import is_personal_runtime_reaction
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

        cycle_started = monotonic()
        context_started = cycle_started
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

        context_completed = monotonic()

        # --------------------------------------------------------
        # INTENT
        # --------------------------------------------------------

        intent_started = monotonic()
        if intent is None:
            intent = self.detect_intent(
                input_text
            )
        intent_completed = monotonic()

        # --------------------------------------------------------
        # REASONING
        # --------------------------------------------------------

        reasoning_started = monotonic()
        reasoning = self.reasoning_engine.reason(
            context=context,
            intent=intent,
        )
        reasoning_completed = monotonic()

        # --------------------------------------------------------
        # REFLECTION
        # --------------------------------------------------------

        reflection_started = monotonic()
        reflection = self.reflection_engine.reflect(
            context=context,
            reasoning=reasoning,
            intent=intent,
        )
        reflection_completed = monotonic()

        # --------------------------------------------------------
        # RESPONSE
        # --------------------------------------------------------

        response_started = monotonic()
        final_response = self._select_response(
            reasoning=reasoning,
            reflection=reflection,
        )
        cycle_completed = monotonic()

        timings = {
            "context_ms": round((context_completed - context_started) * 1000.0, 2),
            "intent_ms": round((intent_completed - intent_started) * 1000.0, 2),
            "reasoning_ms": round((reasoning_completed - reasoning_started) * 1000.0, 2),
            "reflection_ms": round((reflection_completed - reflection_started) * 1000.0, 2),
            "response_select_ms": round((cycle_completed - response_started) * 1000.0, 2),
            "cognition_total_ms": round((cycle_completed - cycle_started) * 1000.0, 2),
        }

        return CognitiveCycleResult(
            context=context,
            intent=intent,
            reasoning=reasoning,
            reflection=reflection,
            final_response=final_response,
            metadata={"timings": timings},
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
            recall_scope = (
                "shared_work"
                if any(phrase in lowered for phrase in (
                    "what have we been working on",
                    "what have we worked on together",
                    "what are we working on together",
                ))
                else "recent_dialogue"
            )
            return Intent(
                intent_type=IntentType.CONVERSATION_RECALL,
                confidence=0.98,
                description=(
                    "Input requests recall from the active/recent dialogue rather "
                    "than long-term memory."
                ),
                parameters={"query": text, "recall_scope": recall_scope},
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
        # MODEL / PROVIDER CONTROL
        # --------------------------------------------------------

        llm_control = self._detect_llm_control(
            text=text,
            lowered=lowered,
        )
        if llm_control is not None:
            return llm_control

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
        # RELATIONAL / CHARACTER FEEDBACK
        # --------------------------------------------------------

        relational_feedback = self._detect_relational_feedback(
            text=text,
            lowered=lowered,
        )
        if relational_feedback is not None:
            return relational_feedback

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

        if looks_like_question(text):

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

    def _detect_relational_feedback(
        self,
        *,
        text: str,
        lowered: str,
    ) -> Intent | None:
        """Recognize natural observations/compliments about Mary as relationship turns.

        This prevents phrases such as ``I can see you care how you talk to me``
        from being mistaken for a literal query about Mary's slang/speech system.
        """

        normalized = normalize_for_matching(text)
        if not normalized:
            return None

        positive_markers = (
            "that's where you shine",
            "i can see a difference",
            "i notice a difference",
            "i like how you",
            "i like that you",
            "i appreciate how you",
            "you actually care",
            "you have care for how you",
            "you feel more like yourself",
            "you sound more like yourself",
            "being a real version of yourself",
            "being an honest version of yourself",
            "that's more you",
            "that feels more like you",
            "i'm proud of you",
            "i am proud of you",
        )
        negative_markers = (
            "that doesn't feel like you",
            "that doesnt feel like you",
            "you don't sound like yourself",
            "you dont sound like yourself",
            "that felt fake",
            "that sounds fake",
            "you sound too robotic",
            "you feel too robotic",
        )

        valence = None
        if any(marker in normalized for marker in positive_markers):
            valence = "positive"
        elif any(marker in normalized for marker in negative_markers):
            valence = "negative"

        if valence is None:
            return None

        return Intent(
            intent_type=IntentType.FEEDBACK,
            confidence=0.94,
            description="Creator is giving relational/character feedback about Mary.",
            parameters={
                "feedback_type": "relational_recognition",
                "valence": valence,
                "content": text,
            },
            source="natural_feedback_detector",
        )

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

        normalized = normalize_for_matching(text)
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
            # Broad shared-work/history questions belong to Mary's durable
            # relationship continuity, not only the active chat window.  This
            # intentionally runs before generic conversation-recall detection.
            shared_work_patterns = (
                # Natural creator phrasing often omits “together”. “we” is
                # already an explicit shared-work cue, so these questions must
                # use durable shared-work continuity instead of free-form model
                # guessing from the active chat window.
                r"\bwhat are we working on(?: right now| now| today)?\b",
                r"\bwhat have we been working on(?: lately| recently| today)?\b",
                r"\bwhat did we work on(?: today| lately| recently)?\b",
                r"\bwhat are we building(?: right now| now| today)?\b",
                r"\bwhat have we been building(?: lately| recently| today)?\b",
                r"\bwhere are we with (?:mary|maryv2|the mary project|the project)\b",
                r"\bwhat do you remember about what we(?:'ve|ve| have) been (?:working on|building|developing|fixing|testing) together(?: lately| recently)?\b",
                r"\bwhat do you remember about what we(?:'ve|ve| have) (?:worked on|built|developed|fixed|tested) together(?: lately| recently)?\b",
                r"\bwhat do you remember we(?:'ve|ve| have) been working on together\b",
                r"\bwhat do you remember we(?:'ve|ve| have) worked on together\b",
                r"\bwhat (?:have|did) we work on together\b",
                r"\bwhat have we been working on together\b",
                r"\bwhat have we worked on together\b",
                r"\bwhat are we working on together\b",
                r"\bwhat have we been building together\b",
                r"\bwhat have we built together\b",
                r"\bwhat projects have we worked on together\b",
                r"\bwhat do you remember about our work together\b",
                # Natural recap wording should resolve to the same durable
                # shared-work path instead of falling through to free-form LLM
                # conversation. Keep this conservative by requiring both a
                # shared/together cue and a concrete work/development verb.
                r"\bremind me (?:about )?what we(?:'ve| have) (?:actually )?(?:(?:been )?(?:working on|building|developing|fixing|testing)|(?:worked on|built|developed|fixed|tested)) together(?: lately| recently)?\b",
            )
            if any(re.search(pattern, normalized) for pattern in shared_work_patterns):
                query_type = "shared_work"

        if query_type is None:
            # Natural questions about what Mary has learned about her creator
            # from recent conversation still belong to the canonical structured
            # creator model.  The time qualifier must not demote the question to
            # generic model-backed dialogue.
            creator_learning_patterns = (
                r"\bwhat have you learned about me from (?:our |the )?(?:recent|latest) conversations?\b",
                r"\bwhat have you learned about me from (?:our |the )?(?:recent|latest) chats?\b",
            )
            if any(re.search(pattern, normalized) for pattern in creator_learning_patterns):
                query_type = "overview"

        if query_type is None:
            # Natural creator-memory phrasing should stay on the local creator
            # model instead of falling through to generic memory or dynamic-web
            # heuristics.  Keep this ownership-specific: "about me" here means
            # Unbe, not Mary's own self-memory.
            creator_memory_patterns = (
                r"\bwhat(?: are)?(?: some)?(?: of the)? things (?:do )?you remember about me\b",
                r"\bwhat(?: are)?(?: some)? memories (?:do )?you have about me\b",
                r"\btell me(?: some)? things you remember about me\b",
            )
            if any(re.search(pattern, normalized) for pattern in creator_memory_patterns):
                query_type = "memory_overview"

        if query_type is None:
            # Questions that explicitly combine Mary's understanding of Unbe with
            # "our relationship" are local relationship-state questions even if
            # they contain the dynamic marker "currently".
            relationship_overview_patterns = (
                r"\bwhat do you (?:currently )?(?:understand|know) about me and (?:our|your) relationship\b",
                r"\bwhat have you learned about me and (?:our|your) relationship\b",
                r"\bhow do you (?:currently )?(?:understand|see) (?:me and )?(?:our|your) relationship\b",
            )
            if any(re.search(pattern, normalized) for pattern in relationship_overview_patterns):
                query_type = "relationship_overview"

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

    def _detect_llm_control(
        self,
        *,
        text: str,
        lowered: str,
    ) -> Intent | None:
        """Detect explicit creator requests about Mary's model routing.

        Provider status questions remain deterministic self-queries. Route changes
        are process-local controls. Paid OpenAI is never made sticky; an explicit
        request to consult it authorizes only the current task.
        """

        normalized = normalize_for_matching(text)

        provider_terms = {
            "llama.cpp": "llama_cpp",
            "llama cpp": "llama_cpp",
            "mac llm": "llama_cpp",
            "mac model": "llama_cpp",
            "ollama": "ollama",
            "local llm": "ollama",
            "local model": "ollama",
            "groq": "groq",
            "gemini": "gemini",
            "openrouter": "openrouter",
            "open router": "openrouter",
            "openai": "openai",
            "open ai": "openai",
        }

        mentioned_provider = None
        for phrase, provider in provider_terms.items():
            if phrase in normalized:
                mentioned_provider = provider
                break

        # Capability/status questions must not silently change routing.
        if mentioned_provider is not None and any(
            phrase in normalized
            for phrase in (
                "can you use", "can u use", "could you use",
                "how can i let you use", "how can i let u use",
                "how do i let you use", "how do i let u use",
                "how can i make you use", "how can i make u use",
                "are you using", "are u using", "you are using",
                "r u using", "do you use", "do u use",
                "which model", "what model", "which provider", "what provider",
            )
        ):
            return Intent(
                intent_type=IntentType.SELF_QUERY,
                confidence=0.99,
                description="Creator asks about Mary's actual model/provider capability or current routing.",
                parameters={
                    "query": text,
                    "self_query_type": "runtime_architecture",
                },
                source="llm_control_detector",
            )

        # Route names are often written as ``normal/free-first`` in Mary's own
        # UI copy. Treat separators as spaces so that exact wording reliably
        # clears a sticky local-only override instead of entering generation.
        routing_text = re.sub(r"[/_-]+", " ", normalized)
        routing_text = " ".join(routing_text.split())
        if any(phrase in routing_text for phrase in (
            "use normal route", "use the normal route", "normal route",
            "go back to free first", "switch back to free first",
            "use free first", "free first", "clear model override",
            "clear provider override", "stop forcing ollama",
        )):
            return Intent(
                intent_type=IntentType.TOOL_USE,
                confidence=0.99,
                description="Creator explicitly returns Mary to configured free-first routing.",
                parameters={
                    "action": "llm_control",
                    "operation": "clear_session",
                },
                source="llm_control_detector",
            )

        command_markers = (
            "use " , "switch to ", "go into ", "go ahead and use", "go ahead an use",
            "fire up ", "route through ", "run through ", "call ",
            "ask ", "consult ",
        )
        explicit_command = mentioned_provider is not None and any(
            marker in normalized for marker in command_markers
        )

        if explicit_command and mentioned_provider == "openai":
            paid_authorized = any(
                phrase in normalized
                for phrase in (
                    "go ahead", "i give you permission", "i give u permission",
                    "you have permission", "u have permission",
                    "use openai", "use open ai", "call openai", "call open ai",
                    "ask openai", "ask open ai", "consult openai", "consult open ai",
                )
            )
            return Intent(
                intent_type=IntentType.TOOL_USE,
                confidence=0.99,
                description="Creator explicitly requests a one-task paid OpenAI expert consultation.",
                parameters={
                    "action": "llm_control",
                    "operation": "paid_expert_once",
                    "provider": "openai",
                    "paid_authorized": paid_authorized,
                    "query": text,
                },
                source="llm_control_detector",
            )

        if explicit_command and mentioned_provider is not None:
            if mentioned_provider == "ollama":
                route = "private"
                provider = None
            else:
                route = None
                provider = mentioned_provider
            return Intent(
                intent_type=IntentType.TOOL_USE,
                confidence=0.99,
                description="Creator explicitly changes Mary's process-local generation route.",
                parameters={
                    "action": "llm_control",
                    "operation": "set_session",
                    "provider": provider,
                    "route": route,
                    "requested_provider": mentioned_provider,
                },
                source="llm_control_detector",
            )

        return None

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

        normalized = normalize_for_matching(text)

        # A turn may mention the current host while still primarily asking for
        # Mary's personal reaction. Keep those hybrid turns conversational and
        # let the runtime layer provide grounded host facts to cognition instead
        # of replacing Mary's voice with a deterministic diagnostic paragraph.
        if is_personal_runtime_reaction(text):
            return None

        patterns: tuple[tuple[str, tuple[str, ...]], ...] = (
            ("runtime_architecture", (
                "what is your underlying architecture running on",
                "what's your underlying architecture running on",
                "what is your underlying architecture",
                "what's your underlying architecture",
                "what is your architecture",
                "what's your architecture",
                "describe your architecture",
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
                "what models can you use right now",
                "what models can u use right now",
                "what providers can you use right now",
                "what providers can u use right now",
                "what models are available right now",
                "what providers are available right now",
                "does anything about how you work change because were not at my pc",
                "does anything about how u work change because were not at my pc",
                "does anything change because were not on my pc",
                "what changes when youre not on my pc",
                "what changes when you are not on my pc",
                "what host are you running on",
                "what environment are you running in",
                "where are you running right now",
                "where are u running right now",
                "where are you running",
                "where are u running",
                "are you running on replit",
                "are you running in replit",
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
            ("development", (
                "do you think you've changed since we started all this",
                "do you think you have changed since we started all this",
                "have you changed since we started all this",
                "have you changed since we started",
                "how have you changed since we started",
                "do you think you've grown since we started",
                "do you think you have grown since we started",
                "have you grown since we started",
                "how have you grown",
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
                "what are you like",
                "are you sarcastic",
                "are you witty",
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
                "are you a hopeless romantic",
                "what are you like romantically",
                "what are you like in a relationship",
                "how are you in relationships",
                "what is your romantic side like",
            )),
            ("reactions", (
                "how do you act when you're angry",
                "how do you act when you are angry",
                "how do you react when you're angry",
                "how do you react when you are angry",
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
                "what are you currently curious about",
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
                "what kind of humor do you like",
                "what kind of humour do you like",
                "what is your sense of humor",
                "what's your sense of humor",
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
            if any(normalized == normalize_for_matching(phrase) for phrase in phrases):
                return self_intent(subtype)

        runtime_markers = (
            "your underlying architecture",
            # Keep technical architecture detection narrow.  A conversational
            # opinion such as "we may have overcomplicated your architecture —
            # what do you think?" must stay a Mary conversation rather than
            # becoming a runtime diagnostic dump.
            "your architecture running",
            "language models fit into your architecture",
            "language model fit into your architecture",
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

        # Runtime/provider questions need to tolerate ordinary chat wording,
        # missing punctuation, and small typos without falling through to a
        # provider that can hallucinate its own identity. Keep this semantic
        # guard deliberately narrow: it only fires when the user is clearly
        # asking about Mary's own providers or the host she is running on.
        runtime_tokens = set(normalized.split())
        provider_subject = bool(
            runtime_tokens.intersection({
                "model", "models", "provider", "providers", "api", "apis",
                "ollama", "groq", "gemini", "openrouter", "openai",
            })
        )
        provider_availability_context = (
            "right now" in normalized
            or "currently" in runtime_tokens
            or "available" in runtime_tokens
            or "using" in runtime_tokens
            or "running" in runtime_tokens
            or "access" in runtime_tokens
            or "use" in runtime_tokens
            or "can" in runtime_tokens
        )
        if (
            looks_like_question(text)
            and provider_subject
            and provider_availability_context
            and bool(runtime_tokens.intersection({"you", "your"}))
        ):
            return self_intent("runtime_architecture")

        host_subject = bool(
            runtime_tokens.intersection({
                "replit", "codespaces", "host", "environment", "device",
                "pc", "computer", "laptop", "mac", "macbook", "phone",
                "iphone", "ipad", "windows", "linux", "macos",
            })
        )
        host_change_context = any(
            marker in normalized
            for marker in (
                "how you work",
                "anything about how you work",
                "does anything change",
                "what changes",
                "work differently",
                "different because",
                "not on my pc",
                "not at my pc",
                "not on the pc",
                "not at the pc",
                "running on",
                "running in",
            )
        )
        if looks_like_question(text) and host_subject and host_change_context:
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
        # A broad strengths/weaknesses question is a grounded self-assessment,
        # not a request for current external information.  Keep it separate from
        # a narrow vulnerability/fear query so Mary can consider both represented
        # qualities and represented limitations.
        if (
            ("your strengths" in normalized or "your current strengths" in normalized)
            and ("weakness" in normalized or "limitations" in normalized)
        ):
            return self_intent("self_assessment")

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

        speech_query_patterns = (
            r"^(?:how|why) do you talk(?:\b|$)",
            r"^(?:how|why) are you talking(?:\b|$)",
            r"^what(?: kind of)? slang do you use(?:\b|$)",
            r"^what are some things you say(?:\b|$)",
            r"^what is your speech(?: style)?(?:\b|$)",
        )
        if (
            "your slang" in normalized
            or any(re.search(pattern, normalized) for pattern in speech_query_patterns)
        ):
            return self_intent("speech")

        if any(marker in normalized for marker in (
            "your long-term goals", "your long term goals", "your personal goals", "you want in life"
        )):
            return self_intent("goals")

        if any(marker in normalized for marker in (
            "you've changed since we started", "you have changed since we started",
            "you changed since we started", "you've grown since we started",
            "you have grown since we started", "how have you changed",
            "how have you grown", "do you think you've changed",
            "do you think you have changed", "have you evolved since we started",
        )):
            return self_intent("development")

        relationship_feeling_patterns = (
            r"^what do you feel (?:in|about|during) (?:our interactions|our conversations|our relationship)(?:\b|$)",
            r"^how do you feel about (?:our interactions|our conversations|our relationship)(?:\b|$)",
            r"^what do you feel when we (?:talk|chat|interact)(?:\b|$)",
            r"^how do you feel when we (?:talk|chat|interact)(?:\b|$)",
            r"^what do you feel (?:talking|speaking) (?:to|with) me(?:\b|$)",
            r"^how do you feel (?:talking|speaking) (?:to|with) me(?:\b|$)",
            r"^what does (?:our relationship|talking with me|talking to me) feel like to you(?:\b|$)",
            r"^what does talking like this feel like from your side(?:\b|$)",
            r"^how does talking like this feel from your side(?:\b|$)",
            r"^what does this conversation feel like from your side(?:\b|$)",
            r"^what is it like for you when we talk like this(?:\b|$)",
        )
        if any(re.search(pattern, normalized) for pattern in relationship_feeling_patterns):
            return self_intent("relationship_feelings")

        # Natural current-state questions must stay local even when they contain
        # words such as "right now" or "today" that would otherwise look like
        # dynamic-web markers.  Keep this scoped to direct questions about Mary's
        # own represented state so topical questions such as "how do you feel
        # about the latest news right now?" can still reach research routing.
        current_state_patterns = (
            r"\bhow are you feeling(?: right now| today| currently| at the moment)?$",
            r"\bhow do you feel(?: right now| today| currently| at the moment)?$",
            r"\bwhat(?:'s| is) your mood(?: right now| today| currently| at the moment)?$",
            r"\bwhat mood are you in(?: right now| today| currently| at the moment)?$",
            r"\bhow(?:'s| is) your mood(?: right now| today| currently| at the moment)?$",
        )
        if (
            "feel about yourself" in normalized
            or "feeling about yourself" in normalized
            or "feel about who you are" in normalized
            or "feeling about who you are" in normalized
            or any(re.search(pattern, normalized) for pattern in current_state_patterns)
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
        dynamic_external_patterns = (
            r"\b(?:latest|current|recent|today|right now|this week)\b.*\b(?:news|weather|price|prices|score|scores|law|laws|version|release|documentation|docs|availability|open|hours)\b",
            r"\b(?:news|weather|price|prices|score|scores|law|laws|version|release|documentation|docs|availability|open|hours)\b.*\b(?:latest|current|recent|today|right now|this week)\b",
            r"\bnear me\b",
            r"\bwhat is the latest\b",
            r"\bwhat(?:'s| is) happening (?:today|right now|this week)\b",
        )

        if (
            lowered.endswith("?")
            and any(re.search(pattern, lowered) for pattern in dynamic_external_patterns)
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
        # Detect explicit requests to store information in memory.
        # Mary only stores automatically when the creator clearly
        # authorizes persistence.

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
                parameters={"content": content},
                source="basic_detector",
            )

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
            if not lowered.startswith(prefix):
                continue

            content = text[len(prefix):].strip()
            if not content:
                continue

            return Intent(
                intent_type=IntentType.MEMORY_STORE,
                confidence=0.95,
                description=(
                    "Input explicitly requests that information be remembered."
                ),
                parameters={"content": content},
                source="basic_detector",
            )

        embedded_authorization_patterns = (
            r"\byou\s+can\s+remember\s+this\b",
            r"\bi\s+(?:want|need)\s+you\s+to\s+remember\s+this\b",
            r"\bplease\s+remember\s+this\b",
            r"\bmake\s+this\s+(?:a\s+)?core\s+memory\b",
            r"\bkeep\s+this\s+(?:as\s+)?(?:a\s+)?core\s+memory\b",
            (
                r"\byou\s+can\s+have\s+this\s+"
                r"(?:as\s+)?(?:a\s+)?core\s+memory"
                r"(?:\s*,?\s*remember\s+this)?\b"
            ),
        )

        for pattern in embedded_authorization_patterns:
            match = re.search(
                pattern,
                text,
                flags=re.IGNORECASE | re.DOTALL,
            )
            if match is None:
                continue

            left = text[:match.start()].rstrip()
            right = text[match.end():].lstrip(" \t\r\n.,;:-")

            if left and right:
                content = f"{left} {right}"
            else:
                content = left or right

            content = re.sub(r"\s+", " ", content).strip()
            content = re.sub(r"\s+([,;:!?])", r"\1", content)
            content = re.sub(r"\.\s*\.", ".", content)
            content = content.strip(" \t\r\n,;:-")

            if not content:
                continue

            return Intent(
                intent_type=IntentType.MEMORY_STORE,
                confidence=0.98,
                description=(
                    "Input contains an explicit natural-language "
                    "authorization to remember the surrounding content."
                ),
                parameters={"content": content},
                source="basic_detector",
            )

        return None

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