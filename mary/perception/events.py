"""
MaryV2 Event System

Events represent things that happened to, around, or because of Mary.

Events are intentionally lightweight. They do not contain cognition or
decision-making logic.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


class EventType(str, Enum):
    """Types of events Mary can perceive."""

    USER_MESSAGE = "user_message"
    VOICE_INPUT = "voice_input"
    SYSTEM = "system"
    TOOL_RESULT = "tool_result"
    AVATAR = "avatar"
    AUTONOMY = "autonomy"
    MEMORY = "memory"
    LEARNING = "learning"


@dataclass
class Event:
    """
    A normalized event entering Mary's system.
    """

    type: EventType
    data: Any = None

    id: str = field(
        default_factory=lambda: str(uuid4())
    )

    timestamp: datetime = field(
        default_factory=lambda: datetime.now(
            timezone.utc
        )
    )

    source: str | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert the event into a serializable dictionary."""

        return {
            "id": self.id,
            "type": self.type.value,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "metadata": self.metadata,
        }

    @classmethod
    def user_message(
        cls,
        message: str,
        source: str = "user",
    ) -> "Event":
        """Create a standard user-message event."""

        return cls(
            type=EventType.USER_MESSAGE,
            data=message,
            source=source,
        )

    @classmethod
    def voice_input(
        cls,
        transcript: str,
        source: str = "voice",
    ) -> "Event":
        """Create a standard voice-input event."""

        return cls(
            type=EventType.VOICE_INPUT,
            data=transcript,
            source=source,
        )