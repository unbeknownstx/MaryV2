"""Latency-aware deterministic reflection policy for MaryV2."""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from .lanes import ConversationLane


@dataclass(frozen=True)
class ReflectionPolicyDecision:
    action: str  # accept | local_repair | model_revision
    rationale: str


# Issues involving factual ownership, capability truth, memory truth or creator
# mind-reading stay on the strong revision boundary even for fast dialogue.
_HIGH_RISK_MARKERS = (
    "provenance",
    "ownership",
    "self-fact",
    "identity",
    "mind-reading",
    "mindreading",
    "capability truth",
    "provider/tool call",
    "memory architecture",
    "background action",
    "future/background",
    "invented self-history",
    "unsupported permanent",
    "representation boundary",
)


def choose_reflection_action(lane: ConversationLane, issues: Iterable[str]) -> ReflectionPolicyDecision:
    values = [str(item).strip() for item in issues if str(item).strip()]
    if not values:
        return ReflectionPolicyDecision("accept", "local character audit passed")

    joined = "\n".join(values).lower()
    if any(marker in joined for marker in _HIGH_RISK_MARKERS):
        return ReflectionPolicyDecision(
            "model_revision",
            "audit found an identity/provenance/capability boundary issue",
        )

    # Only bypass a second model call for style defects the deterministic repair
    # below can actually fix. Repetition, rejected hypotheses, ornamental piles,
    # and other semantic problems still use Mary's established revision path.
    local_fixable = (
        "canned generic-assistant/helpdesk phrasing",
        "conversation handoff boundary",
        "over-formats a casual conversational reply as a list",
        "uses a table for a casual conversational reply",
    )
    if (
        lane in {ConversationLane.SOCIAL_INSTANT, ConversationLane.CONVERSATION}
        and all(any(marker in issue.lower() for marker in local_fixable) for issue in values)
    ):
        return ReflectionPolicyDecision(
            "local_repair",
            "simple assistant-style phrasing can be repaired without a second model call",
        )

    return ReflectionPolicyDecision("model_revision", "audit requires semantic revision")


def local_conversation_repair(text: str, *, micro: bool = False) -> str:
    """Conservatively clean assistant-shaped style without inventing content."""
    value = str(text or "").strip()
    if not value:
        return value

    # Convert a few known helpdesk openers into neutral spoken reactions without
    # inventing new factual content.
    value = re.sub(r"^Great to hear that!\s*", "Nice. ", value, flags=re.IGNORECASE)
    value = re.sub(r"^I'm here to help\.?\s*", "I'm here. ", value, flags=re.IGNORECASE)

    # Flatten accidental list formatting in a short spoken response.
    value = re.sub(r"(?m)^\s*[-*]\s+", "", value)
    value = re.sub(r"\n{2,}", " ", value)
    value = re.sub(r"\s+", " ", value).strip()

    # Remove common generic handoff/helpdesk tails while preserving Mary's
    # substantive preceding sentence.
    tails = (
        r"\s*(?:Let me know if (?:you'd|you would) like[^.!?]*[.!?]?)$",
        r"\s*(?:Anything else (?:you'd|you would) like[^.!?]*[.!?]?)$",
        r"\s*(?:What about you\?|How about you\?|What do you think\?|Anything on your mind\?|Thoughts\?)$",
    )
    for pattern in tails:
        value = re.sub(pattern, "", value, flags=re.IGNORECASE).strip()

    # Social-instant replies should sound like one quick beat. Keep up to two
    # sentences rather than cutting at an arbitrary character boundary.
    if micro:
        parts = re.split(r"(?<=[.!?])\s+", value)
        if len(parts) > 2:
            value = " ".join(parts[:2]).strip()
        words = value.split()
        if len(words) > 65:
            value = " ".join(words[:65]).rstrip(" ,;:-") + "…"

    return value or str(text or "").strip()
