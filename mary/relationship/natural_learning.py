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
    """Conservative detector for naturally volunteered creator facts.

    The gate deliberately mirrors RelationshipManager's deterministic parser.
    A previous version recognized several phrases the manager could not parse,
    which made Mary appear to "notice" a fact without actually preserving it.
    Keeping the two vocabularies aligned makes ordinary relationship learning
    predictable and allows the Memory surface to fill from real creator-owned
    evidence instead of only explicit ``remember this`` commands.
    """

    MAX_CHARACTERS = 500

    def detect(
        self,
        text: str,
    ) -> dict[str, Any] | None:
        """Return a relationship-learning candidate only for clear creator facts."""

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
        # These forms intentionally match RelationshipManager's parser exactly.
        if re.match(r"^i prefer you to\b", text):
            return "communication_preference"

        if re.match(r"^i prefer when you\b", text):
            return "communication_preference"

        preference_patterns = (
            r"^my (?:favorite|favourite)\s+.+\s+is\s+.+",
        )
        if any(re.match(pattern, text) for pattern in preference_patterns):
            return "preference"

        # Interaction-style wording is not a durable hobby/interest. Unless it
        # matched the explicit communication-preference grammar above, fail closed.
        if re.match(r"^i (?:really )?(?:like|love|enjoy) it when you\\b", text):
            return None

        interest_patterns = (
            r"^i (?:really )?(?:like|love|enjoy)\b",
            r"^i(?:'m| am) interested in\b",
        )
        if any(re.match(pattern, text) for pattern in interest_patterns):
            return "interest"

        goal_patterns = (
            r"^my goal is\b",
            r"^my main goal is\b",
            r"^one of my goals is\b",
        )
        if any(re.match(pattern, text) for pattern in goal_patterns):
            return "goal"

        value_patterns = (
            r"^i value\b",
        )
        if any(re.match(pattern, text) for pattern in value_patterns):
            return "value"

        # RelationshipManager already has a deterministic generic-fact parser
        # for ``my <subject> is <value>``. Let ordinary conversation use it.
        # This captures concrete creator-owned facts such as job, city, device,
        # pet/name, schedule, etc. without inferring anything the creator did not
        # state. Favorites/goals above retain their more specific categories.
        if re.match(r"^my [a-z0-9 _-]{1,80} is .+", text):
            return "fact"

        return None
