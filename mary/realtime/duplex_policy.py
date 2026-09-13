"""Transport-neutral full-duplex conversation policy for MaryV2."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class DuplexPlan:
    mode: str
    allow_backchannel: bool
    overlap_retrieval: bool
    allow_barge_in: bool
    partial_answer_allowed: bool
    max_backchannels: int
    authority: str = "realtime_policy_only"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DuplexInteractionPolicy:
    """Plan Moshi/Pipecat/LiveKit-style overlap without owning transport."""

    VERSION = "13.32"

    def plan(
        self,
        *,
        cognitive_mode: str,
        knowledge_recommended: bool,
        mary_speaking: bool = False,
    ) -> DuplexPlan:
        mode = str(cognitive_mode or "balanced").lower()
        relational = mode == "relational"
        deliberate = mode == "deliberate"

        if mary_speaking:
            return DuplexPlan(
                mode="yieldable_speech",
                allow_backchannel=False,
                overlap_retrieval=False,
                allow_barge_in=True,
                partial_answer_allowed=False,
                max_backchannels=0,
            )

        return DuplexPlan(
            mode=("conversational_duplex" if relational else "retrieval_overlap" if knowledge_recommended else "responsive_half_duplex"),
            allow_backchannel=relational,
            overlap_retrieval=bool(knowledge_recommended and (deliberate or mode == "balanced")),
            allow_barge_in=True,
            partial_answer_allowed=False,
            max_backchannels=1 if relational else 0,
        )

    def status(self) -> dict[str, Any]:
        return {
            "version": self.VERSION,
            "transport_neutral": True,
            "barge_in": True,
            "retrieval_overlap": True,
            "partial_factual_answer_before_evidence": False,
            "authority": "realtime_policy_only",
        }
