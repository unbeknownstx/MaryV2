"""Authoritative desktop conversation state for MaryV2.

This module coordinates presentation/runtime lifecycle only. It does not create
another Mary instance and it does not own cognition, speech synthesis, or
speech recognition. The desktop bridge advances this state as the canonical
MaryApplication, microphone recorder, transcription worker, and browser audio
player enter and leave their respective phases.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DesktopConversationState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    TRANSCRIBING = "transcribing"
    RESPONDING = "responding"
    THINKING = "thinking"
    SPEAKING = "speaking"
    INTERRUPTED = "interrupted"


_ALLOWED_TRANSITIONS: dict[DesktopConversationState, set[DesktopConversationState]] = {
    DesktopConversationState.IDLE: {
        DesktopConversationState.LISTENING,
        DesktopConversationState.RESPONDING,
        DesktopConversationState.THINKING,
        DesktopConversationState.SPEAKING,
    },
    DesktopConversationState.LISTENING: {
        DesktopConversationState.TRANSCRIBING,
        DesktopConversationState.IDLE,
        DesktopConversationState.INTERRUPTED,
    },
    DesktopConversationState.TRANSCRIBING: {
        DesktopConversationState.IDLE,
    },
    DesktopConversationState.RESPONDING: {
        DesktopConversationState.SPEAKING,
        DesktopConversationState.IDLE,
        DesktopConversationState.INTERRUPTED,
    },
    DesktopConversationState.THINKING: {
        DesktopConversationState.SPEAKING,
        DesktopConversationState.IDLE,
        DesktopConversationState.INTERRUPTED,
    },
    DesktopConversationState.SPEAKING: {
        DesktopConversationState.IDLE,
        DesktopConversationState.INTERRUPTED,
    },
    DesktopConversationState.INTERRUPTED: {
        DesktopConversationState.LISTENING,
        DesktopConversationState.RESPONDING,
        DesktopConversationState.THINKING,
        DesktopConversationState.IDLE,
    },
}


@dataclass(frozen=True)
class DesktopConversationSnapshot:
    state: DesktopConversationState
    previous: DesktopConversationState
    reason: str
    sequence: int

    def to_dict(self) -> dict[str, object]:
        return {
            "state": self.state.value,
            "previous": self.previous.value,
            "reason": self.reason,
            "sequence": self.sequence,
        }


class DesktopConversationRuntime:
    """Small deterministic state machine for one desktop Mary session."""

    def __init__(self) -> None:
        self._state = DesktopConversationState.IDLE
        self._sequence = 0
        self._snapshot = DesktopConversationSnapshot(
            state=self._state,
            previous=self._state,
            reason="startup",
            sequence=self._sequence,
        )

    @property
    def state(self) -> DesktopConversationState:
        return self._state

    @property
    def snapshot(self) -> DesktopConversationSnapshot:
        return self._snapshot

    def can_transition(self, target: DesktopConversationState | str) -> bool:
        resolved = DesktopConversationState(target)
        if resolved == self._state:
            return True
        return resolved in _ALLOWED_TRANSITIONS[self._state]

    def transition(
        self,
        target: DesktopConversationState | str,
        *,
        reason: str,
    ) -> DesktopConversationSnapshot:
        resolved = DesktopConversationState(target)
        previous = self._state

        if resolved != previous and resolved not in _ALLOWED_TRANSITIONS[previous]:
            raise ValueError(
                f"Invalid desktop conversation transition: "
                f"{previous.value} -> {resolved.value}"
            )

        if resolved != previous:
            self._sequence += 1
            self._state = resolved

        self._snapshot = DesktopConversationSnapshot(
            state=self._state,
            previous=previous,
            reason=str(reason or "unspecified"),
            sequence=self._sequence,
        )
        return self._snapshot
