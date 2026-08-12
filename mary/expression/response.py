"""
MaryV2 - Response System

Represents Mary's generated responses before they are delivered
through dialogue, voice, avatar, or another output channel.

This module is intentionally a translation/data layer.

It does NOT:

    - call an LLM
    - access the internet
    - modify memory
    - modify personality
    - speak audio
    - control an avatar
    - send messages externally

Those responsibilities belong to other subsystems.

Architecture:

    cognition
        |
        v
    ResponseBuilder
        |
        v
    Response
        |
        +----> dialogue
        +----> voice
        +----> avatar
        +----> future output channels
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from time import time
from typing import Any, Mapping

from .emotion import (
    Emotion,
    EmotionIntensity,
    EmotionalState,
)


# ================================================================
# RESPONSE TYPES
# ================================================================


class ResponseType(str, Enum):
    """
    High-level classification of Mary's response.
    """

    STATEMENT = "statement"
    QUESTION = "question"
    ANSWER = "answer"
    GREETING = "greeting"
    FAREWELL = "farewell"

    CLARIFICATION = "clarification"
    EXPLANATION = "explanation"

    ACKNOWLEDGMENT = "acknowledgment"
    APOLOGY = "apology"
    GRATITUDE = "gratitude"

    ENCOURAGEMENT = "encouragement"
    REFLECTION = "reflection"

    SUGGESTION = "suggestion"
    WARNING = "warning"

    ERROR = "error"
    SILENCE = "silence"


class ResponsePriority(str, Enum):
    """
    Priority used when multiple possible responses exist.
    """

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class DeliveryMode(str, Enum):
    """
    Describes how a response is intended to be delivered.

    Actual delivery belongs to downstream systems.
    """

    TEXT = "text"
    VOICE = "voice"
    AVATAR = "avatar"
    MULTIMODAL = "multimodal"
    INTERNAL = "internal"


# ================================================================
# RESPONSE METADATA
# ================================================================


@dataclass
class ResponseMetadata:
    """
    Metadata describing how a response was produced.
    """

    source: str = "cognition"

    model: str | None = None

    provider: str | None = None

    confidence: float = 1.0

    processing_time: float | None = None

    conversation_turn: int | None = None

    memory_references: list[str] = field(
        default_factory=list
    )

    tool_references: list[str] = field(
        default_factory=list
    )

    reasoning_summary: str | None = None

    tags: list[str] = field(
        default_factory=list
    )

    extra: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(
        self,
    ) -> None:

        self.confidence = _clamp(
            self.confidence
        )

        if self.processing_time is not None:
            self.processing_time = max(
                0.0,
                float(
                    self.processing_time
                ),
            )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "source": self.source,
            "model": self.model,
            "provider": self.provider,
            "confidence": self.confidence,
            "processing_time": self.processing_time,
            "conversation_turn": (
                self.conversation_turn
            ),
            "memory_references": list(
                self.memory_references
            ),
            "tool_references": list(
                self.tool_references
            ),
            "reasoning_summary": (
                self.reasoning_summary
            ),
            "tags": list(
                self.tags
            ),
            "extra": dict(
                self.extra
            ),
        }


# ================================================================
# RESPONSE
# ================================================================


@dataclass
class Response:
    """
    Structured representation of something Mary intends to say.

    A Response is not the same thing as a delivered message.

    It can be transformed by dialogue, voice, and avatar systems
    before reaching the user.
    """

    text: str

    response_type: ResponseType = (
        ResponseType.STATEMENT
    )

    emotion: Emotion = Emotion.NEUTRAL

    emotion_intensity: float = 0.0

    delivery_mode: DeliveryMode = (
        DeliveryMode.TEXT
    )

    priority: ResponsePriority = (
        ResponsePriority.NORMAL
    )

    metadata: ResponseMetadata = field(
        default_factory=ResponseMetadata
    )

    created_at: float = field(
        default_factory=time
    )

    response_id: str | None = None

    directed_to: str | None = None

    should_speak: bool = True

    should_display: bool = True

    interruptible: bool = True

    metadata_extra: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(
        self,
    ) -> None:

        self.text = str(
            self.text
        )

        self.emotion_intensity = _clamp(
            self.emotion_intensity
        )

        if (
            self.response_type
            == ResponseType.SILENCE
        ):
            self.should_speak = False
            self.should_display = False

    # ============================================================
    # PROPERTIES
    # ============================================================

    @property
    def is_empty(
        self,
    ) -> bool:
        """
        Determine whether the response contains meaningful text.
        """

        return not bool(
            self.text.strip()
        )

    @property
    def word_count(
        self,
    ) -> int:
        """
        Return the number of whitespace-separated words.
        """

        return len(
            self.text.split()
        )

    @property
    def emotion_level(
        self,
    ) -> EmotionIntensity:
        """
        Convert emotional intensity into a category.
        """

        if self.emotion_intensity < 0.2:
            return EmotionIntensity.VERY_LOW

        if self.emotion_intensity < 0.4:
            return EmotionIntensity.LOW

        if self.emotion_intensity < 0.6:
            return EmotionIntensity.MODERATE

        if self.emotion_intensity < 0.8:
            return EmotionIntensity.HIGH

        return EmotionIntensity.VERY_HIGH

    # ============================================================
    # TRANSFORMATION
    # ============================================================

    def with_text(
        self,
        text: str,
    ) -> "Response":
        """
        Create a copy with different text.
        """

        return Response(
            text=text,
            response_type=self.response_type,
            emotion=self.emotion,
            emotion_intensity=(
                self.emotion_intensity
            ),
            delivery_mode=self.delivery_mode,
            priority=self.priority,
            metadata=self.metadata,
            created_at=self.created_at,
            response_id=self.response_id,
            directed_to=self.directed_to,
            should_speak=self.should_speak,
            should_display=self.should_display,
            interruptible=self.interruptible,
            metadata_extra=dict(
                self.metadata_extra
            ),
        )

    def with_emotion(
        self,
        emotion: Emotion,
        intensity: float,
    ) -> "Response":
        """
        Create a copy with a different expressive emotion.
        """

        return Response(
            text=self.text,
            response_type=self.response_type,
            emotion=emotion,
            emotion_intensity=intensity,
            delivery_mode=self.delivery_mode,
            priority=self.priority,
            metadata=self.metadata,
            created_at=self.created_at,
            response_id=self.response_id,
            directed_to=self.directed_to,
            should_speak=self.should_speak,
            should_display=self.should_display,
            interruptible=self.interruptible,
            metadata_extra=dict(
                self.metadata_extra
            ),
        )

    # ============================================================
    # SERIALIZATION
    # ============================================================

    def to_dict(
        self,
    ) -> dict[str, Any]:
        """
        Serialize the response.
        """

        return {
            "text": self.text,
            "response_type": (
                self.response_type.value
            ),
            "emotion": self.emotion.value,
            "emotion_intensity": (
                self.emotion_intensity
            ),
            "emotion_level": (
                self.emotion_level.value
            ),
            "delivery_mode": (
                self.delivery_mode.value
            ),
            "priority": (
                self.priority.value
            ),
            "metadata": (
                self.metadata.to_dict()
            ),
            "created_at": self.created_at,
            "response_id": self.response_id,
            "directed_to": self.directed_to,
            "should_speak": self.should_speak,
            "should_display": (
                self.should_display
            ),
            "interruptible": (
                self.interruptible
            ),
            "metadata_extra": dict(
                self.metadata_extra
            ),
        }

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
    ) -> "Response":
        """
        Restore a Response from serialized data.
        """

        metadata_data = data.get(
            "metadata",
            {},
        )

        metadata = (
            metadata_data
            if isinstance(
                metadata_data,
                ResponseMetadata,
            )
            else ResponseMetadata(
                source=str(
                    metadata_data.get(
                        "source",
                        "cognition",
                    )
                ),
                model=metadata_data.get(
                    "model"
                ),
                provider=metadata_data.get(
                    "provider"
                ),
                confidence=float(
                    metadata_data.get(
                        "confidence",
                        1.0,
                    )
                ),
                processing_time=metadata_data.get(
                    "processing_time"
                ),
                conversation_turn=metadata_data.get(
                    "conversation_turn"
                ),
                memory_references=list(
                    metadata_data.get(
                        "memory_references",
                        [],
                    )
                ),
                tool_references=list(
                    metadata_data.get(
                        "tool_references",
                        [],
                    )
                ),
                reasoning_summary=metadata_data.get(
                    "reasoning_summary"
                ),
                tags=list(
                    metadata_data.get(
                        "tags",
                        [],
                    )
                ),
                extra=dict(
                    metadata_data.get(
                        "extra",
                        {},
                    )
                ),
            )
        )

        return cls(
            text=str(
                data.get(
                    "text",
                    "",
                )
            ),
            response_type=ResponseType(
                data.get(
                    "response_type",
                    ResponseType.STATEMENT.value,
                )
            ),
            emotion=Emotion(
                data.get(
                    "emotion",
                    Emotion.NEUTRAL.value,
                )
            ),
            emotion_intensity=float(
                data.get(
                    "emotion_intensity",
                    0.0,
                )
            ),
            delivery_mode=DeliveryMode(
                data.get(
                    "delivery_mode",
                    DeliveryMode.TEXT.value,
                )
            ),
            priority=ResponsePriority(
                data.get(
                    "priority",
                    ResponsePriority.NORMAL.value,
                )
            ),
            metadata=metadata,
            created_at=float(
                data.get(
                    "created_at",
                    time(),
                )
            ),
            response_id=data.get(
                "response_id"
            ),
            directed_to=data.get(
                "directed_to"
            ),
            should_speak=bool(
                data.get(
                    "should_speak",
                    True,
                )
            ),
            should_display=bool(
                data.get(
                    "should_display",
                    True,
                )
            ),
            interruptible=bool(
                data.get(
                    "interruptible",
                    True,
                )
            ),
            metadata_extra=dict(
                data.get(
                    "metadata_extra",
                    {},
                )
            ),
        )


# ================================================================
# RESPONSE BUILDER
# ================================================================


class ResponseBuilder:
    """
    Constructs Responses from cognitive output and emotional state.

    The builder does not generate language.

    Language generation belongs to the cognition/LLM layer.
    """

    def __init__(
        self,
        default_delivery_mode: DeliveryMode = (
            DeliveryMode.TEXT
        ),
    ) -> None:

        self.default_delivery_mode = (
            default_delivery_mode
        )

    # ============================================================
    # BUILD
    # ============================================================

    def build(
        self,
        text: str,
        *,
        response_type: ResponseType = (
            ResponseType.STATEMENT
        ),
        emotional_state: EmotionalState | None = None,
        emotion: Emotion | None = None,
        emotion_intensity: float | None = None,
        delivery_mode: DeliveryMode | None = None,
        priority: ResponsePriority = (
            ResponsePriority.NORMAL
        ),
        metadata: ResponseMetadata | None = None,
        response_id: str | None = None,
        directed_to: str | None = None,
        should_speak: bool = True,
        should_display: bool = True,
        interruptible: bool = True,
        metadata_extra: dict[str, Any] | None = None,
    ) -> Response:
        """
        Build a structured Response.

        If an EmotionalState is supplied and no explicit emotion is
        given, the current primary emotion is used.
        """

        if emotional_state is not None:

            if emotion is None:
                emotion = (
                    emotional_state.primary
                )

            if (
                emotion_intensity
                is None
            ):
                emotion_intensity = (
                    emotional_state.intensity
                )

        if emotion is None:
            emotion = Emotion.NEUTRAL

        if emotion_intensity is None:
            emotion_intensity = 0.0

        return Response(
            text=str(
                text
            ),
            response_type=response_type,
            emotion=emotion,
            emotion_intensity=(
                emotion_intensity
            ),
            delivery_mode=(
                delivery_mode
                if delivery_mode is not None
                else self.default_delivery_mode
            ),
            priority=priority,
            metadata=(
                metadata
                if metadata is not None
                else ResponseMetadata()
            ),
            response_id=response_id,
            directed_to=directed_to,
            should_speak=should_speak,
            should_display=should_display,
            interruptible=interruptible,
            metadata_extra=(
                metadata_extra
                if metadata_extra is not None
                else {}
            ),
        )

    # ============================================================
    # SPECIAL RESPONSES
    # ============================================================

    def silence(
        self,
        *,
        reason: str = "",
    ) -> Response:
        """
        Create an intentional silence response.
        """

        return self.build(
            "",
            response_type=(
                ResponseType.SILENCE
            ),
            should_speak=False,
            should_display=False,
            metadata_extra={
                "reason": reason,
            },
        )

    def question(
        self,
        text: str,
        *,
        emotional_state: EmotionalState | None = None,
    ) -> Response:
        """
        Create a question response.
        """

        return self.build(
            text,
            response_type=(
                ResponseType.QUESTION
            ),
            emotional_state=emotional_state,
        )

    def acknowledgment(
        self,
        text: str,
        *,
        emotional_state: EmotionalState | None = None,
    ) -> Response:
        """
        Create an acknowledgment response.
        """

        return self.build(
            text,
            response_type=(
                ResponseType.ACKNOWLEDGMENT
            ),
            emotional_state=emotional_state,
        )

    def error(
        self,
        text: str,
    ) -> Response:
        """
        Create a structured error response.
        """

        return self.build(
            text,
            response_type=(
                ResponseType.ERROR
            ),
            emotion=Emotion.CONCERN,
            emotion_intensity=0.4,
        )


# ================================================================
# HELPERS
# ================================================================


def _clamp(
    value: float,
    minimum: float = 0.0,
    maximum: float = 1.0,
) -> float:
    """
    Clamp a value between minimum and maximum.
    """

    return max(
        minimum,
        min(
            maximum,
            float(value),
        ),
    )


# ================================================================
# FACTORY
# ================================================================


def create_response_builder(
    default_delivery_mode: DeliveryMode = (
        DeliveryMode.TEXT
    ),
) -> ResponseBuilder:
    """
    Create a ResponseBuilder.
    """

    return ResponseBuilder(
        default_delivery_mode=(
            default_delivery_mode
        )
    )