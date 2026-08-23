"""Deterministic MaryV2 conversation-lane classification.

A lane controls latency expectations and how much cognition/reflection may sit on
Mary's response-critical path.  It does not replace intent, identity, memory,
or provider routing; it is a small policy projection over those systems.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import Any


class ConversationLane(str, Enum):
    SOCIAL_INSTANT = "social_instant"
    CONVERSATION = "conversation"
    THINKING = "thinking"
    EXPERT = "expert"


@dataclass(frozen=True)
class LaneDecision:
    lane: ConversationLane
    rationale: str
    latency_target_ms: int
    allow_model_revision: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "lane": self.lane.value,
            "rationale": self.rationale,
            "latency_target_ms": self.latency_target_ms,
            "allow_model_revision": self.allow_model_revision,
        }


_SOCIAL = (
    r"^\s*(?:hey|hi|hello|yo|sup|hiya|morning|afternoon|evening)(?:\s+mary)?[!.?\s]*$",
    r"^\s*(?:lol|lmao|haha+|hehe+|nice|damn|wow|holy damn|no way|yep|yeah|nah|okay|ok)[!.?\s]*$",
    r"\b(?:good to see you|missed you|youre actually here|you're actually here|im here|i'm here)\b",
)

_DEEP = (
    r"\b(?:analy[sz]e|debug|architecture|root cause|deep dive|investigate|research|verify|compare|design|refactor)\b",
    r"\b(?:code|python|javascript|typescript|database|api|websocket|algorithm|tests?|stack trace)\b",
    r"\b(?:step by step|think carefully|reason through|hard problem|complex)\b",
)

_EXPERT = (
    r"\b(?:ask|use|consult) (?:the )?(?:openai|expert|paid expert)\b",
    r"\bexpert (?:opinion|analysis|review)\b",
)


def _matches(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def classify_conversation_lane(
    input_text: str,
    *,
    intent_name: str = "",
    preferred_length: str = "",
    explicit_paid_authorization: bool = False,
) -> LaneDecision:
    """Classify one turn without calling a model.

    EXPERT still requires the existing explicit paid-authorization boundary; a
    phrase mentioning OpenAI does not bypass governance by itself.
    """

    text = str(input_text or "").strip()
    lowered = text.lower()
    words = len(re.findall(r"\b[\w']+\b", lowered))
    intent = str(intent_name or "").strip().lower()
    preferred = str(preferred_length or "").strip().lower()

    if explicit_paid_authorization and _matches(lowered, _EXPERT):
        return LaneDecision(
            ConversationLane.EXPERT,
            "creator explicitly authorized a paid specialist turn",
            20_000,
            True,
        )

    if _matches(lowered, _DEEP) or intent in {"web_search", "tool_use", "information", "command", "request"}:
        return LaneDecision(
            ConversationLane.THINKING,
            "turn contains technical/research/task signals",
            12_000,
            True,
        )

    if (
        preferred == "micro"
        or words <= 8 and (_matches(lowered, _SOCIAL) or "?" not in text)
    ):
        return LaneDecision(
            ConversationLane.SOCIAL_INSTANT,
            "short social/reactive turn",
            1_800,
            False,
        )

    return LaneDecision(
        ConversationLane.CONVERSATION,
        "ordinary personal conversation",
        3_500,
        False,
    )
