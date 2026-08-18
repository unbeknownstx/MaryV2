"""
MaryV2 Intent System

Intent represents what an input appears to be trying to accomplish.

Intent detection is separate from reasoning. Detecting an intent does not
mean Mary has decided what to do about it.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class IntentType(str, Enum):
    """Core intents recognized by Mary."""

    CONVERSATION = "conversation"
    QUESTION = "question"
    REQUEST = "request"
    COMMAND = "command"

    GOAL = "goal"
    INFORMATION = "information"
    CREATIVE = "creative"

    EMOTIONAL_SUPPORT = "emotional_support"
    FEEDBACK = "feedback"

    TOOL_USE = "tool_use"
    WEB_SEARCH = "web_search"

    MEMORY_STORE = "memory_store"
    MEMORY_RECALL = "memory_recall"
    CONVERSATION_RECALL = "conversation_recall"
    SELF_QUERY = "self_query"
    CREATOR_DIRECTIVE = "creator_directive"
    RELATIONSHIP_SHARE = "relationship_share"
    RELATIONSHIP_QUERY = "relationship_query"

    UNKNOWN = "unknown"


@dataclass
class Intent:
    """
    Structured representation of an interpreted user intent.
    """

    intent_type: IntentType

    confidence: float = 1.0

    description: str | None = None

    entities: list[Any] = field(
        default_factory=list
    )

    parameters: dict[str, Any] = field(
        default_factory=dict
    )

    source: str = "system"

    def add_entity(self, entity: Any) -> None:
        """Attach an entity relevant to the intent."""

        self.entities.append(entity)

    def to_dict(self) -> dict[str, Any]:
        """Convert the intent into a serializable dictionary."""

        return {
            "intent_type": self.intent_type.value,
            "confidence": self.confidence,
            "description": self.description,
            "entities": self.entities,
            "parameters": self.parameters,
            "source": self.source,
        }