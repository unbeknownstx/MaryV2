"""
MaryV2 - Mary Core

Top-level coordinator for Mary's systems.

Mary connects the major subsystems while allowing each subsystem
to remain responsible for its own behavior.

Core process flow:

    Input
      ↓
    Context
      ↓
    Intent
      ↓
    Intent-specific system action
      ↓
    Cognition
      ↓
    Response

Mary coordinates systems.

Mary does not replace:
    - cognition
    - memory
    - personality
    - learning
    - relationships
    - LLM routing
"""

from __future__ import annotations

import re
from typing import Any

from mary.core.config import Config
from mary.core.identity import Identity
from mary.core.lifecycle import Lifecycle

from mary.agency.agency import Agency
from mary.autonomy.runtime import AutonomyRuntime

from mary.conversation.service import ConversationService

from mary.expression.dialogue import DialogueManager
from mary.expression.emotion import EmotionManager
from mary.expression.response import ResponseBuilder
from mary.expression.expression import ExpressionSystem

from mary.avatar.bridge import AvatarBridge

from mary.audio import (
    AudioManager,
    NullAudioInputProvider,
    NullAudioOutputProvider,
    create_audio_input_service,
    create_audio_output_service,
)

from mary.identity.biography import create_default_biography
from mary.identity.self_model import SelfModel

from mary.personality.personality import Personality
from mary.personality.development import PersonalityDevelopment
from mary.personality.character import Character

from mary.relationship.user import UserModel

from mary.learning.learner import Learner
from mary.learning.evaluator import Evaluator
from mary.learning.researcher import Researcher

from mary.tools.manager import ToolManager

from mary.knowledge.manager import KnowledgeManager

from mary.memory.manager import MemoryManager

from mary.cognition.orchestrator import (
    CognitiveCycleResult,
    CognitiveOrchestrator,
)
from mary.cognition.reasoning import ReasoningEngine
from mary.cognition.reflection import ReflectionEngine
from mary.cognition.intent import Intent, IntentType


class Mary:
    """
    Top-level coordinator for MaryV2.

    Mary owns subsystem instances and coordinates communication
    between them.

    Subsystems remain responsible for their own internal behavior.
    """

    def __init__(self) -> None:

        # ============================================================
        # CONFIGURATION
        # ============================================================

        self.config = Config()

        # ============================================================
        # LIFECYCLE
        # ============================================================

        self.lifecycle = Lifecycle()

        self.lifecycle.initialize()
        self.lifecycle.ready()

        # ============================================================
        # IDENTITY
        # ============================================================

        self.identity = Identity()

        # ============================================================
        # PERSONALITY
        # ============================================================

        self.personality = Personality(
            name="Mary",
        )

        self.personality_development = PersonalityDevelopment(
            personality=self.personality,
        )

        # ============================================================
        # CHARACTER
        # ============================================================

        self.character = Character()

        # ============================================================
        # SELF MODEL
        # ============================================================

        self.self_model = SelfModel(
            name="Mary",
            personality=self.personality,
            character=self.character,
        )

        # ============================================================
        # BIOGRAPHY
        # ============================================================

        self.biography = create_default_biography()

        # ============================================================
        # RELATIONSHIP
        # ============================================================

        self.user_model = UserModel()

        # ============================================================
        # LLM
        # ============================================================

        self.llm = self._create_llm_router()

        # ============================================================
        # TOOLS
        # ============================================================

        self.tools = ToolManager(
            workspace_root=self.config.paths.root,
        )

        # ============================================================
        # CONVERSATION
        # ============================================================

        self.conversation = ConversationService(
            router=self.llm,
        )

        # ============================================================
        # EXPRESSION
        # ============================================================

        self.emotion = EmotionManager()

        self.response = ResponseBuilder()

        self.dialogue = DialogueManager()

        self.expression = ExpressionSystem(
            emotion=self.emotion,
            response=self.response,
            dialogue=self.dialogue,
        )

        # ============================================================
        # AVATAR
        # ============================================================

        self.avatar = AvatarBridge(
            emotion_manager=self.emotion,
        )

        # ============================================================
        # AUDIO
        # ============================================================

        self.audio = AudioManager(
            input_service=create_audio_input_service(
                NullAudioInputProvider(),
            ),
            output_service=create_audio_output_service(
                NullAudioOutputProvider(),
            ),
        )

        # ============================================================
        # LEARNING
        # ============================================================

        self.learner = Learner()

        self.evaluator = Evaluator(
            llm=self.llm,
        )

        # ============================================================
        # RESEARCHER
        # ============================================================

        # Web execution is intentionally NOT injected directly here.
        # Mary coordinates approved ToolRegistry results into Researcher so
        # Researcher cannot bypass the creator-approval boundary.
        self.researcher = Researcher(
            web_tool=None,
        )

        # ============================================================
        # KNOWLEDGE
        # ============================================================

        self.knowledge = KnowledgeManager()

        # ============================================================
        # MEMORY
        # ============================================================

        self.memory = MemoryManager()

        # ============================================================
        # COGNITION
        # ============================================================

        self.reasoning = ReasoningEngine(
            llm=self.llm,
        )

        self.reflection = ReflectionEngine(
            llm=self.llm,
        )

        self.cognition = CognitiveOrchestrator(
            reasoning_engine=self.reasoning,
            reflection_engine=self.reflection,
        )

        # ============================================================
        # AGENCY
        # ============================================================

        self.agency = Agency()
        self.agency.load()

        # ============================================================
        # AUTONOMY
        # ============================================================

        self.autonomy = AutonomyRuntime()

    # ================================================================
    # PRIMARY ENTRY POINT
    # ================================================================

    def process(
        self,
        input_text: str,
    ) -> CognitiveCycleResult:
        """
        Process one complete MaryV2 interaction.
        """

        input_text = self._normalize_input(
            input_text
        )

        context = self._build_context(
            input_text
        )

        intent = self._detect_intent(
            input_text
        )

        system_response: str | None = None
        external_knowledge: list[Any] = []
        external_sources: list[dict[str, Any]] = []

        if intent.intent_type == IntentType.WEB_SEARCH:
            web_action = self._handle_web_intent(
                intent,
                original_input=input_text,
            )
            system_response = web_action.get(
                "system_response"
            )
            external_knowledge = list(
                web_action.get(
                    "knowledge",
                    [],
                )
            )
            external_sources = list(
                web_action.get(
                    "sources",
                    [],
                )
            )

        elif intent.intent_type == IntentType.TOOL_USE:
            tool_action = self._handle_tool_control(
                intent
            )
            system_response = tool_action.get(
                "system_response"
            )
            external_knowledge = list(
                tool_action.get(
                    "knowledge",
                    [],
                )
            )
            external_sources = list(
                tool_action.get(
                    "sources",
                    [],
                )
            )

        else:
            system_response = self._handle_intent(
                intent
            )

        if system_response is not None:
            context["memory"] = self.memory.build_context(
                input_text
            )

        result = self.cognition.process(
            input_text=input_text,
            intent=intent,
            memories=context["memory"].get(
                "relevant_memories",
                [],
            ),
            knowledge=external_knowledge,
            user_context=context["user"],
            personality_context=context["personality"],
        )

        if system_response is not None:
            result.final_response = system_response
            result.metadata.update(
                {
                    "handled_by": "mary",
                    "system_action": (
                        intent.intent_type.value
                        if intent is not None
                        else None
                    ),
                }
            )

        elif external_sources:
            result.final_response = (
                result.final_response.rstrip()
                + self._format_source_footer(
                    external_sources
                )
            )
            result.metadata.update(
                {
                    "handled_by": "mary_research",
                    "web_sources": external_sources,
                }
            )

        return result

    # ================================================================
    # INPUT
    # ================================================================

    def _normalize_input(
        self,
        input_text: str,
    ) -> str:
        """
        Validate and normalize input.
        """

        if input_text is None:

            raise ValueError(
                "input_text cannot be None."
            )

        text = str(
            input_text
        ).strip()

        if not text:

            raise ValueError(
                "input_text cannot be empty."
            )

        return text

    # ================================================================
    # CONTEXT
    # ================================================================

    def _build_context(
        self,
        input_text: str,
    ) -> dict[str, Any]:
        """
        Build the subsystem context required for one cognitive cycle.
        """

        return {
            "memory": self.memory.build_context(
                input_text
            ),
            "user": self._user_context(),
            "personality": self._personality_context(),
        }

    # ================================================================
    # INTENT
    # ================================================================

    def _detect_intent(
        self,
        input_text: str,
    ) -> Intent:
        """
        Ask cognition to classify the user's intent.
        """

        return self.cognition.detect_intent(
            input_text
        )

    def _handle_intent(
        self,
        intent: Intent | None,
    ) -> str | None:
        """
        Execute deterministic subsystem actions.
        """

        if intent is None:
            return None

        if intent.intent_type == IntentType.MEMORY_STORE:

            return self._handle_memory_store(
                intent
            )

        if intent.intent_type == IntentType.MEMORY_RECALL:

            return self._handle_memory_recall(
                intent
            )

        return None

    # ================================================================
    # TOOLS / WEB RESEARCH
    # ================================================================

    def _handle_web_intent(
        self,
        intent: Intent,
        *,
        original_input: str,
    ) -> dict[str, Any]:
        """Handle a purposeful web search or web-page retrieval request."""

        operation = str(
            intent.parameters.get(
                "operation",
                "search",
            )
        ).strip().lower()

        explicit = bool(
            intent.parameters.get(
                "explicit_creator_request",
                False,
            )
        )

        if operation == "fetch":
            tool_name = "web_fetch"
            url = str(
                intent.parameters.get(
                    "url",
                    "",
                )
            ).strip()
            arguments = {
                "url": url,
            }
            query = str(
                intent.parameters.get(
                    "query",
                    url,
                )
            ).strip()
        else:
            tool_name = "web_search"
            query = str(
                intent.parameters.get(
                    "query",
                    original_input,
                )
            ).strip()
            arguments = {
                "query": query,
                "limit": 5,
            }

        reason = (
            "Creator requested external information for: "
            f"{original_input}"
        )

        if not explicit:
            request = self.tools.request(
                tool_name,
                arguments,
                reason=reason,
            )

            if request.status != "pending":
                return {
                    "system_response": (
                        "I couldn't create the required tool request."
                    )
                }

            return {
                "system_response": (
                    "Current external information would help answer that. "
                    f"I created {request.request_id} for {tool_name}. "
                    "To authorize exactly that request, say: "
                    f"approve {request.request_id}"
                )
            }

        request, tool_result = (
            self.tools.execute_explicit_creator_request(
                tool_name,
                arguments,
                reason=reason,
            )
        )

        return self._research_from_tool_result(
            tool_result,
            query=query,
            tool_name=tool_name,
            request_id=request.request_id,
        )

    def _handle_tool_control(
        self,
        intent: Intent,
    ) -> dict[str, Any]:
        """Handle creator approval/rejection of a pending tool request."""

        action = str(
            intent.parameters.get(
                "action",
                "",
            )
        ).strip().lower()

        request_id = str(
            intent.parameters.get(
                "request_id",
                "",
            )
        ).strip()

        request = self.tools.registry.get_request(
            request_id
        )

        if request is None:
            return {
                "system_response": (
                    f"I don't have a pending tool request named {request_id}."
                )
            }

        if action == "reject":
            rejected = self.tools.reject(
                request_id
            )
            return {
                "system_response": (
                    f"Rejected {request_id}."
                    if rejected
                    else f"{request_id} could not be rejected."
                )
            }

        if action != "approve":
            return {
                "system_response": (
                    "I don't recognize that tool-control action."
                )
            }

        token = self.tools.approve(
            request_id,
            reason="Explicit creator approval in conversation.",
        )

        if token is None:
            return {
                "system_response": (
                    f"{request_id} could not be approved."
                )
            }

        tool_result = self.tools.execute_approved(
            request_id
        )

        if request.tool_name in {
            "web_search",
            "web_fetch",
        }:
            query = str(
                request.arguments.get(
                    "query",
                    request.arguments.get(
                        "url",
                        "",
                    ),
                )
            ).strip()

            return self._research_from_tool_result(
                tool_result,
                query=query,
                tool_name=request.tool_name,
                request_id=request_id,
            )

        if not tool_result.success:
            return {
                "system_response": (
                    f"{request.tool_name} failed: "
                    f"{tool_result.error or 'unknown error'}"
                )
            }

        return {
            "system_response": (
                f"{request.tool_name} completed: "
                f"{tool_result.result}"
            )
        }

    def _research_from_tool_result(
        self,
        tool_result: Any,
        *,
        query: str,
        tool_name: str,
        request_id: str,
    ) -> dict[str, Any]:
        """Route approved web output through Researcher and Evaluator."""

        if not getattr(
            tool_result,
            "success",
            False,
        ):
            return {
                "system_response": (
                    f"{tool_name} failed: "
                    f"{getattr(tool_result, 'error', None) or 'unknown error'}"
                )
            }

        raw_result = getattr(
            tool_result,
            "result",
            None,
        )

        if raw_result is None:
            raw_sources: Any = []
        elif isinstance(raw_result, (list, tuple, dict)):
            raw_sources = raw_result
        else:
            to_dict = getattr(
                raw_result,
                "to_dict",
                None,
            )
            raw_sources = [
                to_dict()
                if callable(to_dict)
                else raw_result
            ]

        research_request = self.researcher.create_request(
            query,
            purpose=(
                "Answer the creator's current request using "
                "approved external information."
            ),
            source_limit=5,
            metadata={
                "tool_request_id": request_id,
                "tool_name": tool_name,
            },
        )

        research_result = self.researcher.complete_with_sources(
            research_request,
            raw_sources,
        )

        if not research_result.sources:
            return {
                "system_response": (
                    "The web request completed, but it returned no usable sources."
                )
            }

        knowledge: list[dict[str, Any]] = []
        source_cards: list[dict[str, Any]] = []

        for source in research_result.sources[:5]:
            statement = (
                source.content.strip()
                or source.title.strip()
            )

            evaluation = self.evaluator.evaluate(
                subject=query,
                statement=statement,
                source=source,
                context=query,
                metadata={
                    "url": source.url,
                    "research_request_id": research_request.id,
                },
            )

            knowledge.append(
                {
                    "title": source.title,
                    "url": source.url,
                    "content": statement[:4000],
                    "source_type": source.source_type,
                    "evaluation": {
                        "recommendation": evaluation.recommendation,
                        "confidence": evaluation.confidence,
                        "reliability": evaluation.reliability,
                    },
                }
            )

            source_cards.append(
                {
                    "title": source.title,
                    "url": source.url,
                    "confidence": evaluation.confidence,
                    "recommendation": evaluation.recommendation,
                }
            )

        return {
            "knowledge": knowledge,
            "sources": source_cards,
        }

    @staticmethod
    def _format_source_footer(
        sources: list[dict[str, Any]],
    ) -> str:
        """Append compact source attribution to a researched response."""

        unique: list[tuple[str, str]] = []
        seen: set[str] = set()

        for source in sources:
            url = str(
                source.get("url", "")
            ).strip()
            title = str(
                source.get("title", "Source")
            ).strip() or "Source"

            key = url or title
            if not key or key in seen:
                continue

            seen.add(key)
            unique.append((title, url))

        if not unique:
            return ""

        lines = ["", "", "Sources:"]
        for title, url in unique[:5]:
            lines.append(
                f"- {title}: {url}"
                if url
                else f"- {title}"
            )

        return "\n".join(lines)

    # ================================================================
    # MEMORY STORE
    # ================================================================

    def _handle_memory_store(
        self,
        intent: Intent,
    ) -> str:
        """
        Handle an explicit request to store information.
        """

        content = intent.parameters.get(
            "content"
        )

        if content is None:

            return (
                "What would you like me to remember?"
            )

        content = str(
            content
        ).strip()

        if not content:

            return (
                "What would you like me to remember?"
            )

        memory = self.remember(
            content,
            memory_type="episodic",
            importance=0.8,
            metadata={
                "source": "interaction",
                "event_type": "user_statement",
                "owner": "creator",
                "speaker": "Unbe",
                "perspective": "creator_first_person",
            },
        )

        if memory is None:

            return (
                "I wasn't able to store that memory."
            )

        rendered_content = (
            self._creator_to_second_person(
                content
            )
        )

        return (
            "Got it. I'll remember that "
            f"{rendered_content}."
        )

    # ================================================================
    # MEMORY RECALL
    # ================================================================

    def _handle_memory_recall(
        self,
        intent: Intent,
    ) -> str:
        """
        Handle an explicit request to recall information.
        """

        query = intent.parameters.get(
            "query",
            "",
        )

        query = str(
            query
        ).strip()

        if self._is_broad_memory_query(
            query
        ):

            memories = self._all_available_memories()

            if not memories:

                return (
                    "I don't have any stored memories "
                    "about you yet."
                )

        else:

            memories = self.memory.recall(
                query,
                limit=5,
            )

            if not memories:

                return (
                    "I don't have a stored memory "
                    "that answers that."
                )

        return self._format_memory_response(
            memories
        )

    def _is_broad_memory_query(
        self,
        query: str,
    ) -> bool:
        """
        Determine whether the user is asking for a broad memory
        summary rather than a specific retrieval.
        """

        lowered = query.lower()

        phrases = (
            "what do you remember about me",
            "what do you know about me",
            "tell me what you remember about me",
            "what do you remember",
            "what are my preferences",
        )

        return any(
            phrase in lowered
            for phrase in phrases
        )

    def _all_available_memories(
        self,
    ) -> list[Any]:
        """
        Return Mary's available stored memories.
        """

        episodic = list(
            self.memory.episodic.all()
        )

        if episodic:
            return episodic

        semantic = list(
            self.memory.semantic.all()
        )

        return semantic

    # ================================================================
    # MEMORY RESPONSE
    # ================================================================

    def _format_memory_response(
        self,
        memories: list[Any],
    ) -> str:
        """
        Convert memory records into a deterministic,
        human-readable response.
        """

        if not memories:

            return (
                "I don't have any relevant memories stored."
            )

        statements: list[str] = []

        for memory in memories:

            statement = self._memory_to_text(
                memory
            )

            if statement:

                statements.append(
                    statement
                )

        if not statements:

            return (
                "I found stored memories, but I couldn't "
                "turn them into an answer."
            )

        statements = list(
            dict.fromkeys(
                statements
            )
        )

        if len(statements) == 1:

            return (
                f"I remember that {statements[0]}"
            )

        lines = "\n".join(
            f"- {statement}"
            for statement in statements
        )

        return (
            "Here's what I remember:\n"
            f"{lines}"
        )

    def _memory_to_text(
        self,
        memory: Any,
    ) -> str | None:
        """
        Extract human-readable text from a memory representation.

        Creator-owned episodic memories are rendered from Mary's
        speaking perspective. The raw stored content is not mutated.
        """

        if isinstance(
            memory,
            dict,
        ):

            content = memory.get(
                "content"
            )

            if content:

                text = str(
                    content
                ).strip()

                if self._memory_is_creator_owned(
                    memory
                ):
                    return self._creator_to_second_person(
                        text
                    )

                return text

            subject = memory.get(
                "subject"
            )

            predicate = memory.get(
                "predicate"
            )

            value = memory.get(
                "value"
            )

            if (
                subject is not None
                and predicate is not None
                and value is not None
            ):

                return (
                    f"{subject} "
                    f"{predicate} "
                    f"{value}"
                ).strip()

            return None

        content = getattr(
            memory,
            "content",
            None,
        )

        if content:

            text = str(
                content
            ).strip()

            if self._memory_is_creator_owned(
                memory
            ):
                return self._creator_to_second_person(
                    text
                )

            return text

        return None

    def _memory_is_creator_owned(
        self,
        memory: Any,
    ) -> bool:
        """
        Determine whether a memory statement belongs to Mary's creator.

        New memories carry explicit ownership metadata. The
        user_preference fallback preserves correct rendering for older
        V2 memories written before ownership metadata was introduced.
        """

        if isinstance(memory, dict):
            metadata = memory.get(
                "metadata",
                {},
            )
            event_type = memory.get(
                "event_type"
            )
        else:
            metadata = getattr(
                memory,
                "metadata",
                {},
            )
            event_type = getattr(
                memory,
                "event_type",
                None,
            )

        if not isinstance(metadata, dict):
            metadata = {}

        owner = str(
            metadata.get(
                "owner",
                "",
            )
        ).strip().lower()

        if owner in {
            "creator",
            "user",
            "unbe",
        }:
            return True

        if owner in {
            "mary",
            "self",
        }:
            return False

        legacy_event_type = str(
            metadata.get(
                "event_type",
                event_type or "",
            )
        ).strip().lower()

        return legacy_event_type == "user_preference"

    @classmethod
    def _creator_to_second_person(
        cls,
        text: str,
    ) -> str:
        """
        Render creator-authored first-person text for Mary speaking back
        to the creator.

        Only text outside double/curly-double quoted spans is shifted,
        preserving quoted first-person speech. The stored memory itself
        remains unchanged.
        """

        text = str(text).strip()

        if not text:
            return text

        parts = re.split(
            r'("[^"\n]*"|“[^”\n]*”)',
            text,
        )

        rendered: list[str] = []

        for index, part in enumerate(parts):
            if index % 2 == 1:
                rendered.append(part)
                continue

            rendered.append(
                cls._shift_first_person_segment(
                    part
                )
            )

        return "".join(rendered)

    @classmethod
    def _shift_first_person_segment(
        cls,
        text: str,
    ) -> str:
        """Shift creator first-person pronouns to second person."""

        replacements = (
            (r"\bI\s+am\b", "you are"),
            (r"\bI\s+was\b", "you were"),
            (r"\bI'm\b", "you're"),
            (r"\bI've\b", "you've"),
            (r"\bI'll\b", "you'll"),
            (r"\bI'd\b", "you'd"),
            (r"\bmyself\b", "yourself"),
            (r"\bmine\b", "yours"),
            (r"\bmy\b", "your"),
            (r"\bme\b", "you"),
            (r"\bI\b", "you"),
        )

        result = text

        for pattern, replacement in replacements:
            result = re.sub(
                pattern,
                lambda match, value=replacement: (
                    cls._match_case(
                        match.group(0),
                        value,
                    )
                ),
                result,
                flags=re.IGNORECASE,
            )

        return result

    @staticmethod
    def _match_case(
        source: str,
        replacement: str,
    ) -> str:
        """Apply simple source capitalization to replacement text."""

        if source.isupper() and len(source) > 1:
            return replacement.upper()

        if source[:1].isupper():
            return (
                replacement[:1].upper()
                + replacement[1:]
            )

        return replacement

    # ================================================================
    # STATUS
    # ================================================================

    def status(
        self,
    ) -> dict[str, Any]:
        """
        Return Mary's current high-level system status.
        """

        return {
            "name": self.personality.name,
            "identity": self._identity_context(),
            "personality": (
                self._personality_context()
            ),
            "personality_development": (
                self.personality_development.summary()
            ),
            "user": self._user_context(),
            "learning": self.learner.summarize(),
            "memory": self.memory.status(),
            "tools": self.tools.status(),
            "cognition": {
                "reasoning": True,
                "reflection": True,
                "llm": self.llm.provider_name(),
                "model": self.llm.model_name(),
            },
        }

    # ================================================================
    # SELF DESCRIPTION
    # ================================================================

    def describe_self(
        self,
    ) -> str:
        """
        Return Mary's human-readable self description.
        """

        return self.personality.describe()

    # ================================================================
    # IDENTITY
    # ================================================================

    def _identity_context(
        self,
    ) -> dict[str, Any]:
        """
        Safely expose Mary's identity as structured context.
        """

        to_dict = getattr(
            self.identity,
            "to_dict",
            None,
        )

        if callable(
            to_dict
        ):

            result = to_dict()

            if isinstance(
                result,
                dict,
            ):
                return result

        describe = getattr(
            self.identity,
            "describe",
            None,
        )

        if callable(
            describe
        ):

            return {
                "description": describe()
            }

        return {
            "type": type(
                self.identity
            ).__name__
        }

    # ================================================================
    # USER
    # ================================================================

    def describe_user(
        self,
    ) -> dict[str, Any]:
        """
        Return Mary's structured understanding of her creator.
        """

        return self._user_context()

    def _user_context(
        self,
    ) -> dict[str, Any]:
        """
        Safely expose the current user-model context.
        """

        to_dict = getattr(
            self.user_model,
            "to_dict",
            None,
        )

        if callable(
            to_dict
        ):

            result = to_dict()

            if isinstance(
                result,
                dict,
            ):
                return result

        get_identity = getattr(
            self.user_model,
            "get_identity",
            None,
        )

        if callable(
            get_identity
        ):

            result = get_identity()

            if isinstance(
                result,
                dict,
            ):
                return result

        return {}

    # ================================================================
    # PERSONALITY
    # ================================================================

    def _personality_context(
        self,
    ) -> dict[str, Any]:
        """
        Safely expose Mary's personality state.
        """

        get_traits = getattr(
            self.personality,
            "get_traits",
            None,
        )

        if not callable(
            get_traits
        ):

            return {}

        result = get_traits()

        if isinstance(
            result,
            dict,
        ):

            return result

        return {}

    def personality_development_summary(
        self,
    ) -> dict[str, Any]:
        """
        Return Mary's current personality-development state.
        """

        return self.personality_development.summary()

    def propose_personality_change(
        self,
        trait: str,
        amount: float,
        reason: str,
        *,
        confidence: float = 0.5,
        source: str = "experience",
    ):
        """
        Propose a controlled personality change.
        """

        return self.personality_development.propose_change(
            trait=trait,
            change=amount,
            reason=reason,
            confidence=confidence,
            source=source,
        )

    def apply_personality_change(
        self,
        proposal: dict[str, Any],
    ) -> bool:
        """
        Apply an approved personality-development proposal.
        """

        return self.personality_development.apply(
            proposal,
        )

    def reject_personality_change(
        self,
        proposal: dict[str, Any],
        reason: str = "",
    ) -> bool:
        """
        Reject a personality-development proposal.
        """

        return self.personality_development.reject(
            proposal,
            reason=reason,
        )

    # ================================================================
    # LEARNING
    # ================================================================

    def learn(
        self,
        event_type: str,
        subject: str,
        content: str,
        *,
        source: str | None = None,
        confidence: float = 0.5,
        usefulness: float = 0.5,
        metadata: dict[str, Any] | None = None,
    ):
        """
        Record something Mary may learn from.
        """

        return self.learner.record(
            event_type=event_type,
            subject=subject,
            content=content,
            source=source,
            confidence=confidence,
            usefulness=usefulness,
            metadata=metadata,
        )

    # ================================================================
    # MEMORY
    # ================================================================

    def remember(
        self,
        content: str,
        *,
        memory_type: str = "episodic",
        importance: float = 0.5,
        metadata: dict[str, Any] | None = None,
    ):
        """
        Store a memory through Mary's MemoryManager.
        """

        return self.memory.remember(
            content,
            memory_type=memory_type,
            importance=importance,
            metadata=metadata,
        )

    # ================================================================
    # INTERNAL
    # ================================================================

    def _create_llm_router(
        self,
    ):
        """
        Create Mary's LLM router.
        """

        from mary.llm.router import LLMRouter

        return LLMRouter(
            config=self.config,
        )