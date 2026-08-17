"""
MaryV2 - Expression Coordinator

Coordinates Mary's expressive communication systems.

The expression layer connects:

    Emotional state
        ↓
    Structured response
        ↓
    Dialogue state
        ↓
    Text / Voice / Avatar

This coordinator does not perform cognition, call an LLM, access the
internet, retrieve long-term memory, execute tools, synthesize speech,
or control the avatar.

Those responsibilities remain with their dedicated MaryV2 subsystems.
"""

from __future__ import annotations

from typing import Any

from mary.expression.dialogue import DialogueManager
from mary.expression.emotion import EmotionManager
from mary.expression.response import Response, ResponseBuilder


class ExpressionSystem:
    """
    Coordinator for Mary's expression layer.

    The coordinator references the existing emotion, response, and
    dialogue systems. These objects may be injected so Mary can expose
    the same shared subsystem instances at the top level without
    creating duplicate state.
    """

    def __init__(
        self,
        *,
        emotion: EmotionManager | None = None,
        response: ResponseBuilder | None = None,
        dialogue: DialogueManager | None = None,
    ) -> None:

        self.emotion = (
            emotion
            if emotion is not None
            else EmotionManager()
        )

        self.response = (
            response
            if response is not None
            else ResponseBuilder()
        )

        self.dialogue = (
            dialogue
            if dialogue is not None
            else DialogueManager()
        )

    # ============================================================
    # RESPONSE COORDINATION
    # ============================================================

    def build_response(
        self,
        text: str,
        **kwargs: Any,
    ) -> Response:
        """
        Build a structured response using Mary's current emotional
        state unless an explicit emotional state or emotion was given.
        """

        if (
            "emotional_state" not in kwargs
            and "emotion" not in kwargs
        ):
            kwargs["emotional_state"] = self.emotion.state

        return self.response.build(
            text,
            **kwargs,
        )

    def record_response(
        self,
        response: Response,
    ) -> None:
        """
        Record a structured response in the current dialogue state.
        """

        self.dialogue.add_response(
            response
        )

    # ============================================================
    # STATUS
    # ============================================================

    def status(
        self,
    ) -> dict[str, Any]:
        """
        Return a high-level view of Mary's expression layer.
        """

        return {
            "emotion": self.emotion.snapshot(),
            "dialogue": self.dialogue.snapshot(),
            "response_builder": type(
                self.response
            ).__name__,
        }
