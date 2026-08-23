"""Provider-independent dialogue acts for Mary's local conversational mind."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DialogueAct(str, Enum):
    GREET = "greet"
    ACKNOWLEDGE = "acknowledge"
    THANKS_RESPONSE = "thanks_response"
    GOODBYE = "goodbye"
    LAUGH = "laugh"
    REACT = "react"
    STATUS = "status"
    KNOWN_FACT = "known_fact"
    KNOWN_PREFERENCE = "known_preference"
    OPINE = "opine"
    ASK = "ask"
    ANSWER = "answer"
    FOLLOW_UP = "follow_up"
    CLARIFY = "clarify"
    STAY_QUIET = "stay_quiet"
    ESCALATE = "escalate"


@dataclass(frozen=True)
class DialoguePlan:
    act: DialogueAct
    confidence: float
    rationale: str
    local: bool = False
    slots: dict[str, Any] = field(default_factory=dict)
    target_length: str = "micro"

    def to_dict(self) -> dict[str, Any]:
        return {
            "act": self.act.value,
            "confidence": round(float(self.confidence), 3),
            "rationale": self.rationale,
            "local": bool(self.local),
            "slots": dict(self.slots),
            "target_length": self.target_length,
        }
