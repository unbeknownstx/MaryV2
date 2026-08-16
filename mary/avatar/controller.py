"""
MaryV2 - Avatar Controller

Maintains provider-independent presentation state for Mary's avatar.

The controller does NOT render graphics, start Unity/Unreal, access the
internet, open a camera, or control external software. A future frontend
adapter can consume this state or forward it to a selected avatar engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from time import time
from typing import Any

from mary.avatar.emotions import AvatarExpression


class AvatarStatus(str, Enum):
    """High-level state of Mary's avatar presentation layer."""

    INACTIVE = "inactive"
    READY = "ready"
    PRESENTING = "presenting"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class AvatarState:
    """Current provider-independent avatar presentation state."""

    status: AvatarStatus = AvatarStatus.INACTIVE
    expression: str = "neutral"
    emotion: str = "neutral"
    emotion_intensity: float = 0.0
    speaking: bool = False
    visible: bool = True
    text: str = ""
    updated_at: float = field(default_factory=time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "expression": self.expression,
            "emotion": self.emotion,
            "emotion_intensity": self.emotion_intensity,
            "speaking": self.speaking,
            "visible": self.visible,
            "text": self.text,
            "updated_at": self.updated_at,
            "metadata": dict(self.metadata),
        }


class AvatarController:
    """
    Owns Mary's avatar presentation state.

    This is deliberately engine-independent. It can later be paired with
    a Unity, Unreal, Live2D, VRM, web, or other renderer without changing
    Mary's cognition or expression systems.
    """

    def __init__(self) -> None:
        self._state = AvatarState()

    def ready(self) -> AvatarState:
        """Mark the presentation layer as available without rendering."""

        self._state.status = AvatarStatus.READY
        self._touch()
        return self.state

    def present(
        self,
        *,
        text: str = "",
        expression: AvatarExpression | None = None,
        speaking: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> AvatarState:
        """Update presentation state for a response."""

        if self._state.status in {
            AvatarStatus.INACTIVE,
            AvatarStatus.STOPPED,
        }:
            self._state.status = AvatarStatus.READY

        if expression is not None:
            self._state.expression = expression.name
            self._state.emotion = expression.emotion.value
            self._state.emotion_intensity = expression.intensity

        self._state.text = str(text)
        self._state.speaking = bool(speaking)
        self._state.status = AvatarStatus.PRESENTING

        if metadata:
            self._state.metadata.update(metadata)

        self._touch()
        return self.state

    def set_speaking(self, speaking: bool) -> AvatarState:
        self._state.speaking = bool(speaking)
        self._touch()
        return self.state

    def set_visible(self, visible: bool) -> AvatarState:
        self._state.visible = bool(visible)
        self._touch()
        return self.state

    def stop(self) -> AvatarState:
        """Stop presentation state without affecting Mary's lifecycle."""

        self._state.status = AvatarStatus.STOPPED
        self._state.speaking = False
        self._touch()
        return self.state

    @property
    def state(self) -> AvatarState:
        """Return a copy so external callers cannot mutate internal state."""

        return AvatarState(
            status=self._state.status,
            expression=self._state.expression,
            emotion=self._state.emotion,
            emotion_intensity=self._state.emotion_intensity,
            speaking=self._state.speaking,
            visible=self._state.visible,
            text=self._state.text,
            updated_at=self._state.updated_at,
            metadata=dict(self._state.metadata),
        )

    def _touch(self) -> None:
        self._state.updated_at = time()
