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

from typing import Any

from mary.core.config import Config
from mary.core.identity import Identity
from mary.core.lifecycle import Lifecycle

from mary.identity.biography import create_default_biography
from mary.identity.self_model import SelfModel

from mary.personality.personality import Personality
from mary.personality.development import PersonalityDevelopment
from mary.personality.character import Character

from mary.relationship.user import UserModel

from mary.learning.learner import Learner
from mary.learning.evaluator import Evaluator
from mary.learning.researcher import Researcher

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
        # LEARNING
        # ============================================================

        self.learner = Learner()

        self.evaluator = Evaluator(
            llm=self.llm,
        )

        # ============================================================
        # RESEARCHER
        # ============================================================

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
                "event_type": "user_preference",
            },
        )

        if memory is None:

            return (
                "I wasn't able to store that memory."
            )

        return (
            f"Got it. I'll remember that {content}."
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
        """

        if isinstance(
            memory,
            dict,
        ):

            content = memory.get(
                "content"
            )

            if content:

                return str(
                    content
                ).strip()

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

            return str(
                content
            ).strip()

        return None

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