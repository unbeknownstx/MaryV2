"""Conversation-facing bridge into Mary's real relationship curiosity state.

This module exists so an explicit invitation such as "ask me anything" does not
fall through to a language model that invents a generic curiosity.  Mary already
has a structured RelationshipCuriosityDevelopment system; this bridge simply
turns one unresolved gap into one natural, bounded question when the creator
invites it.

It never browses, never autonomously interrogates the creator, and never writes
new creator facts.  Learning still occurs only when the creator actually shares
something that the existing relationship-learning boundary accepts.
"""

from __future__ import annotations

import re
from typing import Any

from mary.cognition.natural_input import normalize_for_matching


class ConversationLearningBridge:
    VERSION = "v2-breakthrough-10"

    _INVITATION_PATTERNS: tuple[str, ...] = (
        r"\bask me anything\b",
        r"\bask anything of me\b",
        r"\bask me (?:something|whatever you want)\b",
        r"\bwhat (?:do|would) (?:u|you) want to know about me\b",
        r"\bif (?:u|you) could ask me (?:anything|something)\b",
        r"\bwhat would (?:u|you) actually want to know\b",
        r"\byou(?:re|'re| are) here to learn\b",
        r"\bu(?:re|'re| are) here to learn\b",
    )

    _QUESTIONS: dict[str, str] = {
        "preferences": (
            "You gave me permission to ask something real, so here's one I actually have a gap on: "
            "what are the little things you genuinely enjoy enough that I should remember them about you?"
        ),
        "interests": (
            "Then let me ask something I genuinely don't have filled in yet: what can you get completely "
            "absorbed in even when nobody is asking you to do it?"
        ),
        "goals": (
            "I do want to learn. One gap I actually track is your goals: outside of whatever we're working on "
            "right now, what do you most want your life to move toward?"
        ),
        "values": (
            "Yeah. If you're really giving me the opening, this is something I actually want to understand: "
            "when a choice is hard and there isn't an obvious right answer, what matters most to you?"
        ),
        "communication": (
            "Then here's something useful for *us*: when you think I'm wrong or I'm missing what you mean, "
            "how do you want me to push back or ask you about it?"
        ),
    }

    def __init__(self, relationship_curiosity: Any) -> None:
        self.relationship_curiosity = relationship_curiosity

    def is_invitation(self, text: str) -> bool:
        normalized = normalize_for_matching(str(text or "")).lower().strip()
        return any(
            re.search(pattern, normalized, flags=re.IGNORECASE)
            for pattern in self._INVITATION_PATTERNS
        )

    def respond_if_invited(self, text: str) -> dict[str, Any] | None:
        """Return one grounded relationship question only when explicitly invited."""

        if not self.is_invitation(text):
            return None

        try:
            self.relationship_curiosity.sync()
            unresolved = list(self.relationship_curiosity.unresolved_gaps())
        except Exception:
            unresolved = []

        if not unresolved:
            return {
                "handled": True,
                "category": None,
                "response": (
                    "I do want to keep learning about you. The broad relationship categories I currently track "
                    "already have something in them, though, so I don't want to fake a gap just to ask a question. "
                    "Tell me something you think I still misunderstand or don't know yet, and I'll treat it as yours—not mine."
                ),
            }

        gap = dict(unresolved[0])
        category = str(gap.get("category", "")).strip().lower()
        response = self._QUESTIONS.get(category)
        if not response:
            response = (
                "You gave me permission to ask, so I'll use a real gap instead of making one up: "
                + str(gap.get("question") or gap.get("description") or "what should I understand about you that I don't yet?")
                + "?"
            )

        return {
            "handled": True,
            "category": category or None,
            "response": response,
        }

    def status(self) -> dict[str, Any]:
        try:
            unresolved = self.relationship_curiosity.unresolved_gaps()
        except Exception:
            unresolved = []
        return {
            "connected": True,
            "version": self.VERSION,
            "unresolved_relationship_gaps": len(unresolved),
            "autonomous_questioning": False,
        }
