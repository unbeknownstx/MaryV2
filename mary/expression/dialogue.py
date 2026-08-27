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

    Dialogue history is short-term/session state, not identity or long-term
    memory. One DialogueManager may therefore host multiple bounded
    conversation sessions while still belonging to the same Mary.

    Selecting a different conversation never creates another Mary and never
    duplicates relationship, memory, personality, agency, growth, or workspace
    state.
    """

    DEFAULT_SESSION_ID = "creator-primary"

    def __init__(
        self,
        *,
        max_history: int = 50,
        initial_state: DialogueState | None = None,
        max_sessions: int = 32,
    ) -> None:
        if max_history < 1:
            raise ValueError(
                "max_history must be at least 1."
            )

        if max_sessions < 1:
            raise ValueError(
                "max_sessions must be at least 1."
            )

        initial = (
            initial_state
            if initial_state is not None
            else DialogueState(
                max_history=max_history
            )
        )

        self._max_history = int(
            initial.max_history
        )
        self.max_sessions = int(
            max_sessions
        )

        initial_session_id = self._normalize_session_id(
            initial.metadata.get(
                "conversation_id"
            )
            or self.DEFAULT_SESSION_ID
        )

        initial.metadata[
            "conversation_id"
        ] = initial_session_id

        self._sessions: dict[
            str,
            DialogueState,
        ] = {
            initial_session_id: initial
        }

        self._active_session_id = (
            initial_session_id
        )

    # ============================================================
    # SESSION OWNERSHIP
    # ============================================================

    @staticmethod
    def _normalize_session_id(
        value: Any,
    ) -> str:
        text = str(
            value
            or DialogueManager.DEFAULT_SESSION_ID
        ).strip()

        if not text:
            text = DialogueManager.DEFAULT_SESSION_ID

        # The protocol already sanitizes conversation IDs before they reach
        # Mary. This final guard keeps direct/local callers bounded too.
        safe = "".join(
            character
            if (
                character.isalnum()
                or character
                in "._:/-"
            )
            else "_"
            for character in text
        ).strip("_")

        return (
            safe[:160]
            or DialogueManager.DEFAULT_SESSION_ID
        )

    @property
    def active_session_id(
        self,
    ) -> str:
        return self._active_session_id

    @property
    def session_count(
        self,
    ) -> int:
        return len(
            self._sessions
        )

    @property
    def state(
        self,
    ) -> DialogueState:
        return self._sessions[
            self._active_session_id
        ]

    @state.setter
    def state(
        self,
        value: DialogueState,
    ) -> None:
        if not isinstance(
            value,
            DialogueState,
        ):
            raise TypeError(
                "DialogueManager.state must be a DialogueState."
            )

        value.metadata[
            "conversation_id"
        ] = self._active_session_id

        self._sessions[
            self._active_session_id
        ] = value

    def select_session(
        self,
        conversation_id: str | None,
    ) -> DialogueState:
        """
        Select/create one bounded short-term conversation session.

        Mary Core serializes creator turns, so switching sessions occurs only
        between turns. Direct callers receive the same protection here.
        """

        session_id = self._normalize_session_id(
            conversation_id
        )

        if (
            session_id
            != self._active_session_id
            and self.state.active_turn is not None
            and not self.state.active_turn.completed
        ):
            raise RuntimeError(
                "Cannot switch dialogue sessions while a turn is active."
            )

        existing = self._sessions.get(
            session_id
        )

        if existing is None:
            # Avoid keeping a phantom default session when the very first real
            # protocol/local conversation uses another explicit ID.
            if (
                len(self._sessions) == 1
                and self._active_session_id == self.DEFAULT_SESSION_ID
                and self._state_is_pristine(
                    self.state
                )
            ):
                initial = self._sessions.pop(
                    self.DEFAULT_SESSION_ID
                )
                initial.metadata[
                    "conversation_id"
                ] = session_id
                self._sessions[
                    session_id
                ] = initial
                existing = initial
            else:
                self._ensure_session_capacity()

                existing = DialogueState(
                    max_history=self._max_history,
                    metadata={
                        "conversation_id": session_id,
                    },
                )

                self._sessions[
                    session_id
                ] = existing

        self._active_session_id = session_id

        return existing

    @staticmethod
    def _state_is_pristine(
        state: DialogueState,
    ) -> bool:
        return (
            state.turn_number == 0
            and state.active_turn is None
            and not state.history
        )

    def _ensure_session_capacity(
        self,
    ) -> None:
        if len(
            self._sessions
        ) < self.max_sessions:
            return

        candidates = [
            (
                session_id,
                state,
            )
            for session_id, state
            in self._sessions.items()
            if session_id
            != self._active_session_id
            and (
                state.active_turn is None
                or state.active_turn.completed
            )
        ]

        if not candidates:
            raise RuntimeError(
                "Dialogue session capacity reached."
            )

        oldest_session_id, _ = min(
            candidates,
            key=lambda item: (
                item[1].last_activity
            ),
        )

        del self._sessions[
            oldest_session_id
        ]

    def session_ids(
        self,
    ) -> tuple[str, ...]:
        return tuple(
            self._sessions.keys()
        )

    def session_status(
        self,
    ) -> dict[str, Any]:
        return {
            "active_conversation_id": (
                self.active_session_id
            ),
            "session_count": (
                self.session_count
            ),
            "max_sessions": (
                self.max_sessions
            ),
            "sessions": {
                session_id: {
                    "turn_number": state.turn_number,
                    "message_count": len(
                        state.history
                    ),
                    "mode": state.mode.value,
                    "last_activity": state.last_activity,
                }
                for session_id, state
                in self._sessions.items()
            },
            "semantics": (
                "bounded short-term dialogue sessions around one Mary; "
                "identity, relationship, memory, growth and workspace state "
                "remain shared canonical character state"
            ),
        }

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
        Begin a new conversational turn in the active session.
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

        message_metadata = dict(
            metadata
            or {}
        )
        message_metadata.setdefault(
            "conversation_id",
            self.active_session_id,
        )

        message = DialogueMessage(
            role=SpeakerRole.USER,
            content=user_text,
            turn=turn.number,
            metadata=message_metadata,
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
        Mark the active dialogue session as being processed.
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
        Add Mary's generated response to the active session.
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
                "conversation_id": (
                    self.active_session_id
                ),
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
        Determine the conversational mode resulting from a response.
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
        Return the active dialogue session to idle after delivery.
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
        Return recent dialogue messages from the active session.
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
        Return recent message text from the active session.
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
        Produce role/content history for only the active session.

        This method does not call an LLM and does not access long-term memory.
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
        Clear only the active conversation session.

        Other session histories remain available to the same Mary.
        """

        self.state = DialogueState(
            max_history=self._max_history,
            metadata={
                "conversation_id": (
                    self.active_session_id
                ),
            },
        )

    def clear_all_sessions(
        self,
    ) -> None:
        """
        Clear all short-term dialogue sessions without touching Mary memory.
        """

        self._sessions = {
            self.DEFAULT_SESSION_ID: (
                DialogueState(
                    max_history=self._max_history,
                    metadata={
                        "conversation_id": (
                            self.DEFAULT_SESSION_ID
                        ),
                    },
                )
            )
        }
        self._active_session_id = (
            self.DEFAULT_SESSION_ID
        )

    # ============================================================
    # SNAPSHOT
    # ============================================================

    def snapshot(
        self,
    ) -> dict[str, Any]:
        """
        Return a serializable snapshot for the active dialogue session.
        """

        snapshot = self.state.to_dict()
        snapshot[
            "conversation_id"
        ] = self.active_session_id
        snapshot[
            "session_count"
        ] = self.session_count
        return snapshot

    def snapshot_all(
        self,
    ) -> dict[str, Any]:
        """
        Return bounded metadata plus state for every process-local session.
        """

        return {
            "active_conversation_id": (
                self.active_session_id
            ),
            "max_sessions": (
                self.max_sessions
            ),
            "sessions": {
                session_id: state.to_dict()
                for session_id, state
                in self._sessions.items()
            },
        }

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

