"""Conversation-facing bridge into Mary's real relationship curiosity state.

The bridge serves three purposes:

1. explicit invitations such as ``ask me anything`` choose a *real* unresolved
   relationship gap instead of asking a language model to invent curiosity;
2. the reason for that question remains available across the next turns so a
   natural ``why that question?`` can be answered from Mary's actual state;
3. accepted creator learning can resolve the pending question without creating a
   second relationship store.

The pending question is process-local conversation state. It is deliberately not
another durable memory source. Durable learning still belongs to Mary's existing
RelationshipManager / natural relationship-learning boundary.
"""

from __future__ import annotations

from copy import deepcopy
import re
from typing import Any

from mary.cognition.natural_input import normalize_for_matching


class ConversationLearningBridge:
    VERSION = "v2-breakthrough-11"

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

    _FOLLOWUP_PATTERNS: tuple[str, ...] = (
        r"^(?:hmm |hm |wait |okay |ok )?why (?:that|that question)(?: though)?$",
        r"^why (?:did you ask that|did you ask me that)$",
        r"^why(?:'d| did) you ask(?: me)?(?: that| that question)?$",
        r"^what made you ask(?: me)?(?: that| that question)?$",
        r"^why are you asking(?: me)?(?: that| that question)?$",
        r"^what were you asking me(?: again)?$",
        r"^what did you just ask me(?: again)?$",
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

    _REASONS: dict[str, str] = {
        "preferences": (
            "I have some structured information about you, but I still have a real gap around the small "
            "preferences that make everyday conversation more specifically *you*."
        ),
        "interests": (
            "I know pieces of what you're building and what you care about, but I still track a gap around "
            "what naturally holds your attention when nobody is assigning it to you."
        ),
        "goals": (
            "I know some current project goals, but I don't want to confuse one project with the direction "
            "you want your life to move in overall."
        ),
        "values": (
            "I know some of your interests, preferences, and goals, but I still don't have a clear grounded "
            "answer for what you use as a compass when two choices both have real tradeoffs."
        ),
        "communication": (
            "Because how we repair misunderstandings affects every other conversation we have, and I want "
            "that to come from what you actually prefer rather than a model guessing for you."
        ),
    }

    def __init__(self, relationship_curiosity: Any) -> None:
        self.relationship_curiosity = relationship_curiosity
        self._pending_question: dict[str, Any] | None = None
        self._sequence = 0

    def is_invitation(self, text: str) -> bool:
        normalized = normalize_for_matching(str(text or "")).lower().strip()
        return any(
            re.search(pattern, normalized, flags=re.IGNORECASE)
            for pattern in self._INVITATION_PATTERNS
        )

    def is_pending_followup(self, text: str) -> bool:
        if self._pending_question is None:
            return False
        normalized = normalize_for_matching(str(text or "")).lower().strip()
        return any(
            re.search(pattern, normalized, flags=re.IGNORECASE)
            for pattern in self._FOLLOWUP_PATTERNS
        )

    def respond_to_pending_followup(self, text: str) -> dict[str, Any] | None:
        """Explain or restate Mary's actual pending curiosity question locally."""

        if not self.is_pending_followup(text):
            return None

        pending = dict(self._pending_question or {})
        normalized = normalize_for_matching(str(text or "")).lower().strip()
        if normalized.startswith(("what were you asking", "what did you just ask")):
            response = str(pending.get("question", "")).strip()
        else:
            reason = str(pending.get("reason", "")).strip()
            category = str(pending.get("category", "")).strip()
            response = (
                reason
                + (
                    " That's a real gap in my relationship model, so I chose it instead of making up a random question."
                    if reason
                    else "I chose it because it maps to a real unresolved relationship gap rather than model-improvised curiosity."
                )
            )
            if category:
                response += f" The gap I'm trying to understand is {category}."

        return {
            "handled": True,
            "operation": "pending_question_followup",
            "category": pending.get("category"),
            "pending_id": pending.get("id"),
            "response": response,
        }

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
            self._pending_question = None
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
            raw_question = str(
                gap.get("question")
                or gap.get("description")
                or "what should I understand about you that I don't yet?"
            ).strip().rstrip("?")
            response = (
                "You gave me permission to ask, so I'll use a real gap instead of making one up: "
                + raw_question
                + "?"
            )

        self._sequence += 1
        reason = self._REASONS.get(
            category,
            "I chose it because that category is still an unresolved gap in the relationship state I actually track.",
        )
        self._pending_question = {
            "id": f"relationship_question_{self._sequence}",
            "category": category or None,
            "question": response,
            "reason": reason,
            "gap": {
                key: gap.get(key)
                for key in ("category", "description", "question", "status", "source")
                if gap.get(key) not in (None, "", [], {})
            },
            "status": "asked",
        }

        return {
            "handled": True,
            "category": category or None,
            "pending_id": self._pending_question["id"],
            "response": response,
        }

    def observe_learning(self, learning_result: dict[str, Any] | None) -> None:
        """Resolve the pending question when existing relationship learning fills it."""

        if not self._pending_question or not isinstance(learning_result, dict):
            return
        if not (learning_result.get("learned") or learning_result.get("already_known")):
            return

        learned_category = str(learning_result.get("category", "")).strip().lower()
        pending_category = str(self._pending_question.get("category", "")).strip().lower()
        aliases = {
            "preferences": {"preference"},
            "interests": {"interest"},
            "goals": {"goal"},
            "values": {"value"},
            "communication": {"communication", "communication_style"},
        }
        expected = {pending_category} | aliases.get(pending_category, set())
        if learned_category and learned_category in expected:
            self._pending_question = None

    def pending(self) -> dict[str, Any] | None:
        return deepcopy(self._pending_question)

    def prompt_view(self) -> dict[str, Any] | None:
        """Return a tiny model-facing pending-question view for turn continuity."""

        pending = self._pending_question
        if not isinstance(pending, dict):
            return None
        return {
            "id": pending.get("id"),
            "category": pending.get("category"),
            "question": pending.get("question"),
            "reason": pending.get("reason"),
            "status": pending.get("status", "asked"),
        }

    def status(self) -> dict[str, Any]:
        try:
            unresolved = self.relationship_curiosity.unresolved_gaps()
        except Exception:
            unresolved = []
        pending = self.prompt_view()
        return {
            "connected": True,
            "version": self.VERSION,
            "unresolved_relationship_gaps": len(unresolved),
            "autonomous_questioning": False,
            "pending_question": pending,
        }
