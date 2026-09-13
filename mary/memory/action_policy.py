"""Bounded memory-action policy for MaryV2.

This module proposes what *kind* of memory operation may be appropriate. It does
not write memory. Canonical MemoryManager/RelationshipManager/project owners
remain the only systems that may persist their state.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


def _clamp(value: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0.0
    return max(0.0, min(1.0, number))


@dataclass(frozen=True)
class MemoryActionDecision:
    action: str
    reason: str
    importance: float
    confidence: float
    persistence: str
    requires_review: bool
    source: str
    authority: str = "memory_policy_only"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MemoryActionPolicy:
    """AgeMem-style operation selection without creating a second memory owner."""

    VERSION = "13.30"

    def decide(
        self,
        *,
        content: str,
        source: str = "interaction",
        importance: float = 0.5,
        confidence: float = 0.5,
        explicit_remember: bool = False,
        structured_fact: bool = False,
        changed_fact: bool = False,
        relationship_owned: bool = False,
        temporary: bool = False,
    ) -> MemoryActionDecision:
        text = " ".join(str(content or "").split())
        source = str(source or "interaction")[:80]
        importance = _clamp(importance)
        confidence = _clamp(confidence)

        if not text:
            return MemoryActionDecision(
                "ignore", "empty_content", importance, confidence,
                "none", False, source,
            )

        if relationship_owned:
            return MemoryActionDecision(
                "relationship_owner",
                "relationship continuity has its own canonical owner",
                importance,
                confidence,
                "delegate",
                False,
                source,
            )

        if temporary:
            return MemoryActionDecision(
                "working",
                "temporary/session evidence should remain short-lived",
                importance,
                confidence,
                "working_only",
                False,
                source,
            )

        if structured_fact and changed_fact:
            return MemoryActionDecision(
                "temporal_update_candidate",
                "changed structured fact should preserve old/new validity",
                importance,
                confidence,
                "candidate_only",
                True,
                source,
            )

        if structured_fact and (explicit_remember or confidence >= 0.82):
            return MemoryActionDecision(
                "semantic_candidate",
                "structured durable fact is eligible for semantic review",
                importance,
                confidence,
                "candidate_only",
                True,
                source,
            )

        if explicit_remember or importance >= 0.72:
            return MemoryActionDecision(
                "episodic_candidate",
                "explicit or high-value experience is eligible for episodic storage",
                importance,
                confidence,
                "candidate_only",
                False,
                source,
            )

        return MemoryActionDecision(
            "ignore",
            "insufficient durable significance",
            importance,
            confidence,
            "none",
            False,
            source,
        )

    def status(self) -> dict[str, Any]:
        return {
            "version": self.VERSION,
            "mutates_memory": False,
            "automatic_semantic_promotion": False,
            "preserves_temporal_history": True,
            "relationship_owner_respected": True,
            "authority": "memory_policy_only",
        }
