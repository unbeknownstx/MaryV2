"""Realtime conversation lifecycle glue for MaryV2.

This is intentionally transport-neutral. Audio/VAD/STT frontends submit bounded
signals; the loop decides whether to keep listening, commit a creator turn, or
cancel Mary's current generation/speech after confirmed barge-in.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from mary.realtime.streaming import TurnCancellation
from mary.realtime.turn_end import TurnEndDecision, TurnEndEvidence, TurnEndPolicy


@dataclass(frozen=True)
class RealtimeLoopDecision:
    action: str
    turn_end: dict[str, Any]
    generation_cancelled: bool = False
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RealtimeConversationLoop:
    """Coordinate listening/commit/barge-in without owning Mary cognition."""

    VERSION = "13.18"

    def __init__(self, *, turn_end: TurnEndPolicy | None = None, barge_in_ms: int = 140) -> None:
        self.turn_end = turn_end or TurnEndPolicy()
        self.barge_in_ms = max(80, min(1200, int(barge_in_ms)))

    def observe(
        self,
        evidence: TurnEndEvidence,
        *,
        creator_speech_ms: float = 0.0,
        mary_speaking: bool = False,
        cancellation: TurnCancellation | None = None,
    ) -> RealtimeLoopDecision:
        creator_speech_ms = max(0.0, float(creator_speech_ms or 0.0))
        if mary_speaking and evidence.speech_active and creator_speech_ms >= self.barge_in_ms:
            cancelled = False
            if cancellation is not None:
                cancellation.cancel("creator_barge_in")
                cancelled = cancellation.cancelled
            return RealtimeLoopDecision(
                action="yield_floor",
                turn_end=TurnEndDecision(False, 0.0, self.turn_end.settle_ms, "barge_in").to_dict(),
                generation_cancelled=cancelled,
                reason="confirmed_creator_barge_in",
            )

        decision = self.turn_end.decide(evidence)
        if decision.complete:
            action = "commit_creator_turn"
        elif evidence.speech_active:
            action = "listen"
        else:
            action = "settle"
        return RealtimeLoopDecision(
            action=action,
            turn_end=decision.to_dict(),
            generation_cancelled=False,
            reason=decision.reason,
        )

    def status(self) -> dict[str, Any]:
        return {
            "version": self.VERSION,
            "barge_in_ms": self.barge_in_ms,
            "turn_end": self.turn_end.status(),
            "transport": "provider_neutral",
            "cognition_authority": "Mary Core",
        }
