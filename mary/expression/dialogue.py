"""
MaryV2 - Dialogue System

Manages conversational state around Mary's responses.

This module coordinates dialogue state but does NOT perform
cognition itself.

It does NOT:

    - call an LLM
    - access the internet
    - retrieve memories
    - modify personality
    - execute tools
    - synthesize speech
    - control an avatar

Those responsibilities belong to their respective subsystems.

Architecture:

    perception
        |
        v
    cognition
        |
        v
    response
        |
        v
    dialogue
        |
        +----> text
        +----> voice
        +----> avatar

The dialogue manager maintains the conversational state required
by those downstream systems.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from time import time
from typing import Any, Iterable, Mapping

from .emotion import Emotion
from .response import (
    DeliveryMode,
    Response,
    ResponsePriority,
    ResponseType,
)


# ================================================================
# DIALOGUE MODES
# ================================================================


class DialogueMode(str, Enum):
    """
    Current conversational mode.
    """

    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    RESPONDING = "responding"

    CLARIFYING = "clarifying"
    EXPLAINING = "explaining"

    REFLECTING = "reflecting"
    CASUAL = "casual"

    GOODBYE = "goodbye"


# ================================================================
# SPEAKER
# ================================================================


class SpeakerRole(str, Enum):
    """
    Role of a participant in the dialogue.
    """

    USER = "user"
    MARY = "mary"
    SYSTEM = "system"
    TOOL = "tool"


# ================================================================
# DIALOGUE MESSAGE
# ================================================================


@dataclass
class DialogueMessage:
    """
    A single conversational message.

    This is intentionally separate from memory.

    Dialogue history represents what happened in the current
    conversational context. The memory subsystem decides what,
    if anything, should become long-term memory.
    """

    role: SpeakerRole

    content: str

    timestamp: float = field(
        default_factory=time
    )

    turn: int | None = None

    response_id: str | None = None

    emotion: Emotion | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(
        self,
    ) -> None:

        self.content = str(
            self.content
        )

    @property
    def is_empty(
        self,
    ) -> bool:
        return not bool(
            self.content.strip()
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "role": self.role.value,
            "content": self.content,
            "timestamp": self.timestamp,
            "turn": self.turn,
            "response_id": self.response_id,
            "emotion": (
                self.emotion.value
                if self.emotion is not None
                else None
            ),
            "metadata": dict(
                self.metadata
            ),
        }

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
    ) -> "DialogueMessage":
        emotion_value = data.get(
            "emotion"
        )

        emotion = None

        if emotion_value is not None:
            try:
                emotion = Emotion(
                    emotion_value
                )
            except ValueError:
                emotion = None

        return cls(
            role=SpeakerRole(
                data.get(
                    "role",
                    SpeakerRole.USER.value,
                )
            ),
            content=str(
                data.get(
                    "content",
                    "",
                )
            ),
            timestamp=float(
                data.get(
                    "timestamp",
                    time(),
                )
            ),
            turn=data.get(
                "turn"
            ),
            response_id=data.get(
                "response_id"
            ),
            emotion=emotion,
            metadata=dict(
                data.get(
                    "metadata",
                    {},
                )
            ),
        )


# ================================================================
# DIALOGUE TURN
# ================================================================


@dataclass
class DialogueTurn:
    """
    Represents one user-to-Mary conversational turn.

    A turn may contain:

        user message
        Mary's response
        optional metadata
    """

    number: int

    user_message: DialogueMessage | None = None

    mary_response: DialogueMessage | None = None

    started_at: float = field(
        default_factory=time
    )

    completed_at: float | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    @property
    def completed(
        self,
    ) -> bool:
        return (
            self.user_message is not None
            and self.mary_response is not None
        )

    def complete(
        self,
    ) -> None:
        self.completed_at = time()

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "number": self.number,
            "user_message": (
                self.user_message.to_dict()
                if self.user_message
                else None
            ),
            "mary_response": (
                self.mary_response.to_dict()
                if self.mary_response
                else None
            ),
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "metadata": dict(
                self.metadata
            ),
        }


# ================================================================
# DIALOGUE STATE
# ================================================================


@dataclass
class DialogueState:
    """
    Current state of the conversation.
    """

    mode: DialogueMode = (
        DialogueMode.IDLE
    )

    turn_number: int = 0

    active_turn: DialogueTurn | None = None

    history: list[
        DialogueMessage
    ] = field(
        default_factory=list
    )

    max_history: int = 50

    started_at: float = field(
        default_factory=time
    )

    last_activity: float = field(
        default_factory=time
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(
        self,
    ) -> None:

        if self.max_history < 1:
            raise ValueError(
                "max_history must be at least 1."
            )

    # ============================================================
    # HISTORY
    # ============================================================

    def add_message(
        self,
        message: DialogueMessage,
    ) -> None:
        """
        Add a message to dialogue history.
        """

        self.history.append(
            message
        )

        self.last_activity = time()

        self._trim_history()

    def _trim_history(
        self,
    ) -> None:
        if len(
            self.history
        ) <= self.max_history:
            return

        self.history = self.history[
            -self.max_history:
        ]

    # ============================================================
    # MODE
    # ============================================================

    def set_mode(
        self,
        mode: DialogueMode,
    ) -> None:
        self.mode = mode
        self.last_activity = time()

    # ============================================================
    # SERIALIZATION
    # ============================================================

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "turn_number": self.turn_number,
            "active_turn": (
                self.active_turn.to_dict()
                if self.active_turn
                else None
            ),
            "history": [
                message.to_dict()
                for message in self.history
            ],
            "max_history": self.max_history,
            "started_at": self.started_at,
            "last_activity": self.last_activity,
            "metadata": dict(
                self.metadata
            ),
        }

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
    ) -> "DialogueState":
        history = [
            DialogueMessage.from_dict(
                item
            )
            for item in data.get(
                "history",
                [],
            )
        ]

        active_turn_data = data.get(
            "active_turn"
        )

        active_turn = None

        if isinstance(
            active_turn_data,
            Mapping,
        ):
            user_data = (
                active_turn_data.get(
                    "user_message"
                )
            )

            mary_data = (
                active_turn_data.get(
                    "mary_response"
                )
            )

            user_message = (
                DialogueMessage.from_dict(
                    user_data
                )
                if isinstance(
                    user_data,
                    Mapping,
                )
                else None
            )

            mary_response = (
                DialogueMessage.from_dict(
                    mary_data
                )
                if isinstance(
                    mary_data,
                    Mapping,
                )
                else None
            )

            active_turn = DialogueTurn(
                number=int(
                    active_turn_data.get(
                        "number",
                        0,
                    )
                ),
                user_message=user_message,
                mary_response=mary_response,
                started_at=float(
                    active_turn_data.get(
                        "started_at",
                        time(),
                    )
                ),
                completed_at=(
                    active_turn_data.get(
                        "completed_at"
                    )
                ),
                metadata=dict(
                    active_turn_data.get(
                        "metadata",
                        {},
                    )
                ),
            )

        return cls(
            mode=DialogueMode(
                data.get(
                    "mode",
                    DialogueMode.IDLE.value,
                )
            ),
            turn_number=int(
                data.get(
                    "turn_number",
                    0,
                )
            ),
            active_turn=active_turn,
            history=history,
            max_history=int(
                data.get(
                    "max_history",
                    50,
                )
            ),
            started_at=float(
                data.get(
                    "started_at",
                    time(),
                )
            ),
            last_activity=float(
                data.get(
                    "last_activity",
                    time(),
                )
            ),
            metadata=dict(
                data.get(
                    "metadata",
                    {},
                )
            ),
        )


# ================================================================
# DIALOGUE MANAGER
# ================================================================


class DialogueManager:
    """
    Coordinates Mary's conversational state.

    The manager does not generate responses.

    It receives generated Response objects and records them as
    dialogue events.
    """

    def __init__(
        self,
        *,
        max_history: int = 50,
        initial_state: DialogueState | None = None,
    ) -> None:

        self.state = (
            initial_state
            if initial_state is not None
            else DialogueState(
                max_history=max_history
            )
        )

    # ============================================================
    # TURN MANAGEMENT
    # ============================================================

    def begin_turn(
        self,
        user_text: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> DialogueTurn:
        """
        Begin a new conversational turn.
        """

        if self.state.active_turn is not None:
            if not self.state.active_turn.completed:
                raise RuntimeError(
                    "A dialogue turn is already active."
                )

        self.state.turn_number += 1

        turn = DialogueTurn(
            number=self.state.turn_number
        )

        message = DialogueMessage(
            role=SpeakerRole.USER,
            content=user_text,
            turn=turn.number,
            metadata=(
                metadata
                if metadata is not None
                else {}
            ),
        )

        turn.user_message = message

        self.state.active_turn = turn

        self.state.set_mode(
            DialogueMode.LISTENING
        )

        self.state.add_message(
            message
        )

        return turn

    # ============================================================
    # THINKING
    # ============================================================

    def begin_thinking(
        self,
    ) -> None:
        """
        Mark the dialogue as being processed.
        """

        self.state.set_mode(
            DialogueMode.THINKING
        )

    # ============================================================
    # RESPONSE
    # ============================================================

    def add_response(
        self,
        response: Response,
    ) -> DialogueMessage:
        """
        Add Mary's generated response to the active turn.
        """

        if self.state.active_turn is None:
            raise RuntimeError(
                "Cannot add a response without an active turn."
            )

        turn = self.state.active_turn

        message = DialogueMessage(
            role=SpeakerRole.MARY,
            content=response.text,
            turn=turn.number,
            response_id=response.response_id,
            emotion=response.emotion,
            metadata={
                "response_type": (
                    response.response_type.value
                ),
                "emotion_intensity": (
                    response.emotion_intensity
                ),
                "delivery_mode": (
                    response.delivery_mode.value
                ),
                "priority": (
                    response.priority.value
                ),
                "should_speak": (
                    response.should_speak
                ),
                "should_display": (
                    response.should_display
                ),
                "interruptible": (
                    response.interruptible
                ),
                **response.metadata_extra,
            },
        )

        turn.mary_response = message

        self.state.add_message(
            message
        )

        self.state.set_mode(
            self._mode_for_response(
                response
            )
        )

        turn.complete()

        return message

    # ============================================================
    # RESPONSE MODE
    # ============================================================

    def _mode_for_response(
        self,
        response: Response,
    ) -> DialogueMode:
        """
        Determine the conversational mode resulting from a
        response.
        """

        mapping = {
            ResponseType.CLARIFICATION: (
                DialogueMode.CLARIFYING
            ),
            ResponseType.EXPLANATION: (
                DialogueMode.EXPLAINING
            ),
            ResponseType.REFLECTION: (
                DialogueMode.REFLECTING
            ),
            ResponseType.FAREWELL: (
                DialogueMode.GOODBYE
            ),
        }

        return mapping.get(
            response.response_type,
            DialogueMode.RESPONDING,
        )

    # ============================================================
    # FINISH
    # ============================================================

    def finish_turn(
        self,
    ) -> None:
        """
        Return dialogue to an idle state after delivery.
        """

        if self.state.active_turn is not None:
            if (
                self.state.active_turn.completed
            ):
                self.state.set_mode(
                    DialogueMode.IDLE
                )

    # ============================================================
    # HISTORY
    # ============================================================

    def recent_messages(
        self,
        limit: int = 10,
    ) -> list[DialogueMessage]:
        """
        Return recent dialogue messages.
        """

        if limit <= 0:
            return []

        return self.state.history[
            -limit:
        ]

    def recent_text(
        self,
        limit: int = 10,
    ) -> list[str]:
        """
        Return recent message text.
        """

        return [
            message.content
            for message in self.recent_messages(
                limit
            )
        ]

    def messages_for_llm(
        self,
        limit: int | None = None,
    ) -> list[dict[str, str]]:
        """
        Produce a simple role/content representation suitable
        for an LLM adapter.

        This method does not call an LLM.
        """

        messages = (
            self.state.history
            if limit is None
            else self.recent_messages(
                limit
            )
        )

        return [
            {
                "role": self._llm_role(
                    message.role
                ),
                "content": message.content,
            }
            for message in messages
            if not message.is_empty
        ]

    @staticmethod
    def _llm_role(
        role: SpeakerRole,
    ) -> str:
        """
        Map dialogue roles to common LLM roles.
        """

        if role == SpeakerRole.MARY:
            return "assistant"

        if role == SpeakerRole.SYSTEM:
            return "system"

        return "user"

    # ============================================================
    # CLEAR
    # ============================================================

    def clear(
        self,
    ) -> None:
        """
        Clear active conversational state and history.
        """

        self.state = DialogueState(
            max_history=self.state.max_history
        )

    # ============================================================
    # SNAPSHOT
    # ============================================================

    def snapshot(
        self,
    ) -> dict[str, Any]:
        """
        Return a serializable dialogue snapshot.
        """

        return self.state.to_dict()


# ================================================================
# FACTORY
# ================================================================


def create_dialogue_manager(
    *,
    max_history: int = 50,
) -> DialogueManager:
    """
    Create a DialogueManager.
    """

    return DialogueManager(
        max_history=max_history
    )


# ================================================================
# UTILITY
# ================================================================


def messages_to_text(
    messages: Iterable[DialogueMessage],
) -> str:
    """
    Convert dialogue messages into a readable transcript.

    This is intended for logging, debugging, or prompt preparation.
    """

    lines: list[str] = []

    for message in messages:
        role = message.role.value.capitalize()

        lines.append(
            f"{role}: {message.content}"
        )

    return "\n".join(
        lines
    )