"""Deterministic stream-output planning for MaryV2 13.3.

The streaming attention path decides whether a social event deserves Mary's
attention.  This module makes the next boundary explicit: *where* should a
response be expressed?  Voice, typed chat, both, a silent reaction, or defer.

It is presentation policy only.  It cannot create a Mary response, call a
provider, authorize tools, or mutate identity/memory/relationship state.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class StreamOutputMode(str, Enum):
    DROP = "drop"
    REACT = "react"
    CHAT = "chat"
    SPEAK = "speak"
    BOTH = "both"
    WAIT = "wait"


@dataclass(frozen=True)
class StreamResponsePlan:
    mode: StreamOutputMode
    reason: str
    target_identity: str = ""
    reply_to_message_id: str = ""
    score: float = 0.0
    interruptible: bool = True
    voice_priority: int = 50
    chat_priority: int = 50

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["mode"] = self.mode.value
        payload["score"] = round(max(0.0, min(1.0, float(self.score))), 3)
        payload["voice_priority"] = max(0, min(100, int(self.voice_priority)))
        payload["chat_priority"] = max(0, min(100, int(self.chat_priority)))
        return payload


def plan_stream_response(
    *,
    action: str,
    score: float,
    direct_to_mary: bool,
    creator_speaking: bool,
    floor_disposition: str = "not_considered",
    target_identity: str = "",
    reply_to_message_id: str = "",
    prefer_voice: bool = True,
) -> StreamResponsePlan:
    """Return one deterministic surface plan from already-bounded social state.

    Direct chat can still receive a typed acknowledgement while the creator has
    the conversational floor.  Mary never steals the audio floor merely because
    chat was salient.
    """

    normalized_action = str(action or "ignore").strip().casefold()
    floor = str(floor_disposition or "not_considered").strip().casefold()
    bounded_score = max(0.0, min(1.0, float(score)))

    if normalized_action == "ignore" or floor == "drop":
        return StreamResponsePlan(
            StreamOutputMode.DROP,
            "social event was below response threshold",
            target_identity=target_identity,
            reply_to_message_id=reply_to_message_id,
            score=bounded_score,
        )

    if normalized_action == "notice":
        return StreamResponsePlan(
            StreamOutputMode.REACT,
            "event is worth acknowledging nonverbally but not answering",
            target_identity=target_identity,
            reply_to_message_id=reply_to_message_id,
            score=bounded_score,
        )

    if creator_speaking or floor == "wait":
        if direct_to_mary:
            return StreamResponsePlan(
                StreamOutputMode.CHAT,
                "creator owns audio floor; direct viewer may receive typed reply",
                target_identity=target_identity,
                reply_to_message_id=reply_to_message_id,
                score=bounded_score,
                voice_priority=20,
                chat_priority=80,
            )
        return StreamResponsePlan(
            StreamOutputMode.WAIT,
            "creator owns conversational floor",
            target_identity=target_identity,
            reply_to_message_id=reply_to_message_id,
            score=bounded_score,
            voice_priority=25,
            chat_priority=40,
        )

    if direct_to_mary and bounded_score >= 0.82:
        return StreamResponsePlan(
            StreamOutputMode.BOTH,
            "high-salience direct address can be spoken and replied to in chat",
            target_identity=target_identity,
            reply_to_message_id=reply_to_message_id,
            score=bounded_score,
            voice_priority=80,
            chat_priority=75,
        )

    if prefer_voice:
        return StreamResponsePlan(
            StreamOutputMode.SPEAK,
            "response candidate is best expressed by the cohost voice",
            target_identity=target_identity,
            reply_to_message_id=reply_to_message_id,
            score=bounded_score,
            voice_priority=65,
            chat_priority=35,
        )

    return StreamResponsePlan(
        StreamOutputMode.CHAT,
        "response candidate is configured for typed chat",
        target_identity=target_identity,
        reply_to_message_id=reply_to_message_id,
        score=bounded_score,
        voice_priority=35,
        chat_priority=65,
    )
