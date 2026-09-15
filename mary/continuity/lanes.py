"""Reflex/deliberative lane arbitration for realtime Mary presence."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CognitionLaneDecision:
    reflex: bool
    deliberative: bool
    reflex_cues: tuple[str, ...]
    reason: str


class CognitionLaneRouter:
    """Choose timing lanes without creating a second Mary or second cognition owner.

    Reflex cues are presentation/attention hints only. Any substantive answer,
    durable decision, tool use, or memory interpretation stays deliberative.
    """

    VERSION = 1

    def decide(
        self,
        *,
        event_type: str,
        direct_address: bool = False,
        complexity: float = 0.5,
        tool_required: bool = False,
        memory_required: bool = False,
        speech_active: bool = False,
    ) -> CognitionLaneDecision:
        event = str(event_type).strip().lower()
        complexity = max(0.0, min(float(complexity), 1.0))
        cues: list[str] = []

        if direct_address:
            cues.extend(["orient_to_speaker", "acknowledge_presence"])
        elif event in {"voice_activity", "chat_mention", "scene_change"}:
            cues.append("orient_attention")

        if speech_active:
            cues.append("listen_attentive")

        deliberative = bool(
            direct_address
            or complexity >= 0.25
            or tool_required
            or memory_required
            or event in {"creator_turn", "chat_message", "task", "question"}
        )
        reflex = bool(cues)
        if not reflex and not deliberative:
            return CognitionLaneDecision(False, False, (), "ignore_or_note")
        if reflex and deliberative:
            reason = "immediate_presence_then_deliberation"
        elif reflex:
            reason = "presentation_reflex_only"
        else:
            reason = "deliberative_only"
        return CognitionLaneDecision(reflex, deliberative, tuple(dict.fromkeys(cues)), reason)

    def status(self) -> dict[str, Any]:
        return {
            "version": self.VERSION,
            "policy": "reflex controls attention/presentation only; TurnMind remains cognition authority",
        }
