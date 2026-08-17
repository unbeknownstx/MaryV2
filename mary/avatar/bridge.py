"""
MaryV2 - Avatar Bridge

Connects Mary's existing expression state to the provider-independent avatar
controller.

The bridge does NOT render an avatar or communicate with external software.
It prepares presentation state that a future frontend adapter can consume.
"""

from __future__ import annotations

from typing import Any

from mary.avatar.controller import AvatarController, AvatarState
from mary.avatar.emotions import AvatarEmotionMapper
from mary.expression.emotion import EmotionManager, EmotionalState
from mary.expression.response import Response


class AvatarBridge:
    """Presentation-layer bridge between Mary expression and an avatar."""

    def __init__(
        self,
        *,
        controller: AvatarController | None = None,
        emotion_mapper: AvatarEmotionMapper | None = None,
        emotion_manager: EmotionManager | None = None,
    ) -> None:
        self.controller = (
            controller
            if controller is not None
            else AvatarController()
        )

        self.emotion_mapper = (
            emotion_mapper
            if emotion_mapper is not None
            else AvatarEmotionMapper()
        )

        self.emotion_manager = emotion_manager

    def ready(self) -> AvatarState:
        return self.controller.ready()

    def sync_emotion(
        self,
        state: EmotionalState | None = None,
    ) -> AvatarState:
        """Synchronize avatar expression with Mary's existing emotion state."""

        if state is None:
            if self.emotion_manager is None:
                return self.controller.state
            state = self.emotion_manager.state

        expression = self.emotion_mapper.map_state(state)

        return self.controller.present(
            expression=expression,
            speaking=self.controller.state.speaking,
            metadata={"event": "emotion_sync"},
        )

    def present_response(
        self,
        response: Response,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> AvatarState:
        """Translate a structured Response into avatar presentation state."""

        if not isinstance(response, Response):
            raise TypeError("response must be a Response instance.")

        emotional_state = EmotionalState(
            primary=response.emotion,
            intensity=response.emotion_intensity,
        )

        if self.emotion_manager is not None:
            emotional_state = self.emotion_manager.state

        expression = self.emotion_mapper.map_state(emotional_state)

        return self.controller.present(
            text=response.text,
            expression=expression,
            speaking=response.should_speak,
            metadata={
                "response_id": response.response_id,
                "delivery_mode": response.delivery_mode.value,
                **(metadata or {}),
            },
        )

    def stop(self) -> AvatarState:
        return self.controller.stop()

    @property
    def state(self) -> AvatarState:
        return self.controller.state
