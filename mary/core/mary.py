"""
MaryV2 - Mary Core

Top-level coordinator for Mary's systems.

Mary is responsible for connecting the major subsystems.
Individual systems remain responsible for their own behavior.
"""

from __future__ import annotations

from typing import Any, Dict

from mary.core.identity import Identity
from mary.core.config import Config

from mary.personality.personality import Personality
from mary.personality.development import PersonalityDevelopment

from mary.relationship.user import UserModel

from mary.learning.learner import Learner

from mary.memory.manager import MemoryManager

from mary.cognition.orchestrator import (
    CognitiveOrchestrator,
    CognitiveCycleResult,
)
from mary.cognition.reasoning import ReasoningEngine
from mary.cognition.reflection import ReflectionEngine


class Mary:
    """
    Top-level coordinator for MaryV2.
    """

    def __init__(self) -> None:

        # ========================================================
        # CONFIGURATION
        # ========================================================

        self.config = Config()

        # ========================================================
        # IDENTITY
        # ========================================================

        self.identity = Identity()

        # ========================================================
        # PERSONALITY
        # ========================================================

        self.personality = Personality(
            name="Mary",
        )

        self.personality_development = PersonalityDevelopment(
            personality=self.personality,
        )

        # ========================================================
        # RELATIONSHIP / USER MODEL
        # ========================================================

        self.user_model = UserModel()

        # ========================================================
        # LEARNING
        # ========================================================

        self.learner = Learner()

        # ========================================================
        # MEMORY
        # ========================================================

        self.memory = MemoryManager()

        # ========================================================
        # COGNITION
        # ========================================================

        self.llm = self._create_llm_router()

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
    # COGNITION
    # ============================================================

    def process(
        self,
        input_text: str,
    ) -> CognitiveCycleResult:
        """
        Process one complete cognitive cycle.

        This is Mary's primary cognitive entry point.

        The method gathers relevant information from Mary's systems,
        passes it into cognition, and returns the complete structured
        cognitive-cycle result.
        """

        if not input_text or not str(input_text).strip():

            raise ValueError(
                "input_text cannot be empty."
            )

        input_text = str(input_text).strip()

        # --------------------------------------------------------
        # MEMORY CONTEXT
        # --------------------------------------------------------

        memory_context = self.memory.build_context(
            input_text,
        )

        # --------------------------------------------------------
        # USER CONTEXT
        # --------------------------------------------------------

        user_context = self._safe_user_context()

        # --------------------------------------------------------
        # PERSONALITY CONTEXT
        # --------------------------------------------------------

        personality_context = self._safe_personality_context()

        # --------------------------------------------------------
        # COGNITIVE CYCLE
        # --------------------------------------------------------

        return self.cognition.process(
            input_text=input_text,
            memories=memory_context.get(
                "relevant_memories",
                [],
            ),
            user_context=user_context,
            personality_context=personality_context,
        )

    # ============================================================
    # STATUS
    # ============================================================

    def status(self) -> Dict[str, Any]:
        """
        Return Mary's current high-level system status.
        """

        return {
            "name": self.personality.name,
            "identity": self._safe_identity(),
            "personality": self.personality.get_traits(),
            "personality_development": (
                self.personality_development.summary()
            ),
            "user": self.user_model.get_identity(),
            "learning": self.learner.summarize(),
            "memory": self.memory.status(),
            "cognition": {
                "reasoning": True,
                "reflection": True,
                "llm": self.llm.provider_name(),
                "model": self.llm.model_name(),
            },
        }

    # ============================================================
    # SELF DESCRIPTION
    # ============================================================

    def describe_self(self) -> str:
        """
        Return a human-readable description of Mary.
        """

        return self.personality.describe()

    # ============================================================
    # PERSONALITY DEVELOPMENT
    # ============================================================

    def personality_development_summary(
        self,
    ) -> Dict[str, Any]:
        """
        Return Mary's current personality-development state.
        """

        return self.personality_development.summary()

    # ============================================================
    # USER
    # ============================================================

    def describe_user(self) -> Dict[str, Any]:
        """
        Return Mary's current structured understanding
        of her creator.
        """

        return self.user_model.to_dict()

    # ============================================================
    # LEARNING
    # ============================================================

    def learn(
        self,
        event_type: str,
        subject: str,
        content: str,
        *,
        source: str | None = None,
        confidence: float = 0.5,
        usefulness: float = 0.5,
        metadata: Dict[str, Any] | None = None,
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

    # ============================================================
    # MEMORY
    # ============================================================

    def remember(
        self,
        content: str,
        *,
        memory_type: str = "episodic",
        importance: float = 0.5,
        metadata: Dict[str, Any] | None = None,
    ):
        """
        Store a memory through the MemoryManager.
        """

        return self.memory.remember(
            content,
            memory_type=memory_type,
            importance=importance,
            metadata=metadata,
        )

    # ============================================================
    # PERSONALITY DEVELOPMENT HELPERS
    # ============================================================

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

        The proposal is not applied automatically.
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
        proposal: Dict[str, Any],
    ) -> bool:
        """
        Apply a previously created personality-development
        proposal.
        """

        return self.personality_development.apply(
            proposal,
        )

    def reject_personality_change(
        self,
        proposal: Dict[str, Any],
        reason: str = "",
    ) -> bool:
        """
        Reject a personality-development proposal.
        """

        return self.personality_development.reject(
            proposal,
            reason=reason,
        )

    # ============================================================
    # INTERNAL
    # ============================================================

    def _create_llm_router(self):
        """
        Create Mary's LLM router.

        The router remains the only layer that knows which
        provider is being used.
        """

        from mary.llm.router import LLMRouter

        return LLMRouter(
            config=self.config,
        )

    def _safe_identity(self) -> Dict[str, Any]:
        """
        Safely serialize Mary's identity regardless of the
        current Identity implementation.
        """

        if hasattr(self.identity, "to_dict"):

            result = self.identity.to_dict()

            if isinstance(result, dict):
                return result

        if hasattr(self.identity, "describe"):

            return {
                "description": self.identity.describe()
            }

        return {
            "type": type(self.identity).__name__
        }

    def _safe_user_context(self) -> Dict[str, Any]:
        """
        Safely expose the current user model to cognition.
        """

        if hasattr(self.user_model, "to_dict"):

            result = self.user_model.to_dict()

            if isinstance(result, dict):
                return result

        if hasattr(self.user_model, "get_identity"):

            result = self.user_model.get_identity()

            if isinstance(result, dict):
                return result

        return {}

    def _safe_personality_context(self) -> Dict[str, Any]:
        """
        Safely expose Mary's personality state to cognition.
        """

        if hasattr(
            self.personality,
            "get_traits",
        ):

            result = self.personality.get_traits()

            if isinstance(result, dict):
                return result

        return {}