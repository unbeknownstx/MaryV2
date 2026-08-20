"""
MaryV2 - Natural Relationship Learning Gate

Recognizes a deliberately small set of direct, first-person creator statements
that are safe to offer to Mary's existing RelationshipManager.

This module does not write memory, mutate relationship state, call an LLM, or
infer hidden facts.  It only decides whether the creator clearly volunteered a
current relationship fact in ordinary conversation.

Boundary:

    creator statement
        -> conservative deterministic gate
        -> existing RelationshipManager.learn_explicit(...)

Questions, hypotheticals, uncertainty, past-only statements, and third-party
claims stay ordinary conversation.
"""

from __future__ import annotations

import re
from typing import Any

from mary.cognition.natural_input import normalize_for_matching


class NaturalRelationshipLearner:
    """Conservative detector for naturally volunteered creator facts."""

    MAX_CHARACTERS = 500

    def detect(
        self,
        text: str,
    ) -> dict[str, Any] | None:
        """
        Return a relationship-learning candidate only for clear creator facts.

        The returned text is still parsed by RelationshipManager.  This class
        intentionally does not become a second relationship parser/database.
        """

        content = " ".join(str(text or "").split()).strip()
        if not content or len(content) > self.MAX_CHARACTERS:
            return None

        # Matching is tolerant of ordinary chat shorthand/punctuation, while
        # ``content`` remains the exact creator text for evidence/memory.
        lowered = normalize_for_matching(content)

        if self._is_question(lowered):
            return None

        if self._is_uncertain_or_hypothetical(lowered):
            return None

        if self._is_past_only(lowered):
            return None

        signal_type = self._signal_type(lowered)
        if signal_type is None:
            return None

        return {
            "content": content,
            "signal_type": signal_type,
            "source": "creator_natural",
            "explicit_first_person": True,
            "match_content": lowered,
        }

    @staticmethod
    def _is_question(text: str) -> bool:
        if "?" in text:
            return True

        return bool(
            re.match(
                r"^(?:what|why|when|where|who|which|how|do|does|did|can|could|"
                r"would|should|is|are|am|have|has|will)\b",
                text,
            )
        )

    @staticmethod
    def _is_uncertain_or_hypothetical(text: str) -> bool:
        markers = (
            "maybe ",
            "perhaps ",
            "possibly ",
            "i might ",
            "i may ",
            "i could ",
            "i would ",
            "i think i ",
            "i guess i ",
            "i suppose i ",
            "i'm not sure ",
            "i am not sure ",
            "not sure if i ",
            "if i ",
        )
        return any(marker in text for marker in markers)

    @staticmethod
    def _is_past_only(text: str) -> bool:
        markers = (
            "i used to ",
            "i formerly ",
            "i previously ",
            "when i was ",
            "back when i ",
        )
        return any(marker in text for marker in markers)

    @staticmethod
    def _signal_type(text: str) -> str | None:
        # Communication preference must be checked before generic preference.
        if re.match(r"^i prefer (?:that )?you\b", text):
            return "communication_preference"

        if re.match(r"^i like it when you\b", text):
            return "communication_preference"

        preference_patterns = (
            r"^my (?:favorite|favourite)\s+.+\s+is\s+.+",
        )
        if any(re.match(pattern, text) for pattern in preference_patterns):
            return "preference"

        interest_patterns = (
            r"^i (?:really )?(?:like|love|enjoy)\b",
            r"^i(?:'m| am) interested in\b",
        )
        if any(re.match(pattern, text) for pattern in interest_patterns):
            return "interest"

        goal_patterns = (
            r"^my (?:main |primary |current |long[- ]term )?goal(?: right now)? is\b",
            r"^one of my (?:main )?goals is\b",
            r"^my goals (?:include|includes|are)\b",
        )
        if any(re.match(pattern, text) for pattern in goal_patterns):
            return "goal"

        value_patterns = (
            r"^i value\b",
            r"^what matters (?:most )?to me is\b",
            r"^.{2,160} is (?:very |really )?important to me[.!]?$",
        )
        if any(re.match(pattern, text) for pattern in value_patterns):
            return "value"

        return None
