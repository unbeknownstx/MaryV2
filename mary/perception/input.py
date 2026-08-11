"""
MaryV2 Input System

Input represents raw information entering Mary.

Perception is responsible for describing where the input came from.
Cognition is responsible for interpreting what the input means.
"""

from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


class InputType(str, Enum):
    """Types of raw input Mary can receive."""

    TEXT = "text"
    AUDIO = "audio"
    IMAGE = "image"
    VIDEO = "video"
    EVENT = "event"
    SYSTEM = "system"


class InputSource(str, Enum):
    """Sources from which input can originate."""

    USER = "user"
    MICROPHONE = "microphone"
    AVATAR = "avatar"
    WEB = "web"
    TOOL = "tool"
    SYSTEM = "system"
    AUTONOMY = "autonomy"


@dataclass
class Input:
    """
    Raw input entering Mary's perception boundary.
    """

    content: Any

    input_type: InputType = InputType.TEXT

    source: InputSource = InputSource.USER

    id: str = field(
        default_factory=lambda: str(uuid4())
    )

    timestamp: datetime = field(
        default_factory=lambda: datetime.now(
            timezone.utc
        )
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert input into a serializable dictionary."""

        return {
            "id": self.id,
            "content": self.content,
            "input_type": self.input_type.value,
            "source": self.source.value,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def text(
        cls,
        content: str,
        source: InputSource = InputSource.USER,
    ) -> "Input":
        """Create a standard text input."""

        return cls(
            content=content,
            input_type=InputType.TEXT,
            source=source,
        )

    @classmethod
    def audio(
        cls,
        content: Any,
        source: InputSource = InputSource.MICROPHONE,
    ) -> "Input":
        """Create an audio input."""

        return cls(
            content=content,
            input_type=InputType.AUDIO,
            source=source,
        )