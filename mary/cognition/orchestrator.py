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
        # MEMORY RECALL
        # --------------------------------------------------------

        recall_phrases = (
            "what do you remember",
            "what do you know about me",
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
        # WEB / EXTERNAL RESEARCH
        # --------------------------------------------------------

        web_intent = self._detect_web_intent(
            text=text,
            lowered=lowered,
        )

        if web_intent is not None:
            return web_intent

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

    def _detect_tool_control(
        self,
        *,
        text: str,
        lowered: str,
    ) -> Intent | None:
        """Detect explicit creator approval or rejection of a tool request."""

        request_match = re.search(
            r"\brequest_[0-9a-fA-F]+\b",
            text,
        )

        if request_match is None:
            return None

        request_id = request_match.group(0)

        if lowered.startswith((
            "approve ",
            "yes approve ",
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

        if lowered.startswith((
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
            == ReflectionDecision.ESCALATE
        ):
            return reasoning.response

        return reasoning.response