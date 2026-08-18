"""
MaryV2 Cognitive Context

CognitiveContext represents the information currently available to Mary's
cognition pipeline while processing an input.

Context is temporary working information.

It does NOT own:
    - long-term memory
    - personality
    - goals
    - knowledge
    - reasoning
    - decision making

Those systems provide information to the context when needed.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class CognitiveContext:
    """
    Temporary workspace for a single cognitive cycle.
    """

    input_text: str

    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    conversation: list[dict[str, Any]] = field(
        default_factory=list
    )

    memories: list[Any] = field(
        default_factory=list
    )

    relevant_knowledge: list[Any] = field(
        default_factory=list
    )

    entities: list[Any] = field(
        default_factory=list
    )

    user_context: dict[str, Any] = field(
        default_factory=dict
    )

    personality_context: dict[str, Any] = field(
        default_factory=dict
    )

    active_goals: list[Any] = field(
        default_factory=list
    )

    mind_state: dict[str, Any] = field(
        default_factory=dict
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def add_memory(self, memory: Any) -> None:
        """Add a relevant memory to the current context."""

        self.memories.append(memory)

    def add_knowledge(self, knowledge: Any) -> None:
        """Add relevant knowledge to the current context."""

        self.relevant_knowledge.append(knowledge)

    def add_entity(self, entity: Any) -> None:
        """Add a perceived entity to the current context."""

        self.entities.append(entity)

    def add_conversation_entry(
        self,
        role: str,
        content: str,
    ) -> None:
        """Add a conversation entry to the context."""

        self.conversation.append(
            {
                "role": role,
                "content": content,
            }
        )

    def set_user_context(
        self,
        context: dict[str, Any],
    ) -> None:
        """Set information about the current user context."""

        self.user_context = dict(context)

    def set_personality_context(
        self,
        context: dict[str, Any],
    ) -> None:
        """Set personality information relevant to this cognitive cycle."""

        self.personality_context = dict(context)

    def add_goal(self, goal: Any) -> None:
        """Add an active goal relevant to the current context."""

        self.active_goals.append(goal)

    def to_dict(self) -> dict[str, Any]:
        """Convert the context into a serializable dictionary."""

        return {
            "input_text": self.input_text,
            "timestamp": self.timestamp.isoformat(),
            "conversation": self.conversation,
            "memories": self.memories,
            "relevant_knowledge": self.relevant_knowledge,
            "entities": self.entities,
            "user_context": self.user_context,
            "personality_context": self.personality_context,
            "active_goals": self.active_goals,
            "mind_state": self.mind_state,
            "metadata": self.metadata,
        }