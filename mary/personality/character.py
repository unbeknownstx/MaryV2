"""MaryV2 - Character System.

Defines Mary's recognizable character and expressive tendencies.

Personality describes Mary's underlying traits.
Character describes how those traits tend to manifest in behavior,
conversation, humor, relationships, vulnerability, romance, and expression.

The character system does not generate responses or control the LLM.
It provides structured information that cognition and expression can use.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional

from mary.personality.character_core import (
    CORE_ARCHETYPE,
    CORE_BEHAVIOR,
    CORE_BEHAVIORAL_CANON,
    CORE_CONSTITUTION,
    CORE_EPISTEMIC_LENS,
    CORE_HUMOR_STYLE,
    CORE_MANNERISMS,
    CORE_PRIVATE_ACTIVITIES,
    CORE_QUALITIES,
    CORE_QUIRKS,
    CORE_REACTIONS,
    CORE_ROMANCE,
    CORE_SOCIAL_MODES,
    CORE_SPEECH,
    CORE_TENDENCIES,
    CORE_VULNERABILITIES,
)


class Character:
    """Mary's authored character model.

    Stable authored material lives here so a language-model provider cannot
    silently replace Mary with its own generic persona. These defaults may be
    serialized and intentionally overridden, but ordinary conversation does
    not mutate them.
    """

    DEFAULT_ARCHETYPE = CORE_ARCHETYPE
    DEFAULT_QUALITIES = CORE_QUALITIES
    DEFAULT_TENDENCIES = CORE_TENDENCIES
    DEFAULT_MANNERISMS = CORE_MANNERISMS
    DEFAULT_HUMOR_STYLE = CORE_HUMOR_STYLE
    DEFAULT_BEHAVIOR = CORE_BEHAVIOR
    DEFAULT_CONSTITUTION = CORE_CONSTITUTION
    DEFAULT_EPISTEMIC_LENS = CORE_EPISTEMIC_LENS
    DEFAULT_BEHAVIORAL_CANON = CORE_BEHAVIORAL_CANON
    DEFAULT_SOCIAL_MODES = CORE_SOCIAL_MODES
    DEFAULT_REACTIONS = CORE_REACTIONS
    DEFAULT_QUIRKS = CORE_QUIRKS
    DEFAULT_SPEECH = CORE_SPEECH
    DEFAULT_ROMANCE = CORE_ROMANCE
    DEFAULT_VULNERABILITIES = CORE_VULNERABILITIES
    DEFAULT_PRIVATE_ACTIVITIES = CORE_PRIVATE_ACTIVITIES

    def __init__(
        self,
        archetype: str = DEFAULT_ARCHETYPE,
        qualities: Optional[List[str]] = None,
        tendencies: Optional[List[str]] = None,
        mannerisms: Optional[List[str]] = None,
        humor_style: Optional[List[str]] = None,
        behavior: Optional[Dict[str, float]] = None,
        constitution: Optional[Dict[str, Dict[str, Any]]] = None,
        epistemic_lens: Optional[List[str]] = None,
        behavioral_canon: Optional[Dict[str, Dict[str, Any]]] = None,
        social_modes: Optional[Dict[str, str]] = None,
        reactions: Optional[Dict[str, str]] = None,
        quirks: Optional[List[str]] = None,
        speech: Optional[Dict[str, Any]] = None,
        romance: Optional[Dict[str, Any]] = None,
        vulnerabilities: Optional[Dict[str, Any]] = None,
        private_activities: Optional[List[str]] = None,
    ) -> None:
        self.archetype = str(archetype).strip() or self.DEFAULT_ARCHETYPE

        self.qualities = list(
            qualities if qualities is not None else self.DEFAULT_QUALITIES
        )
        self.tendencies = list(
            tendencies if tendencies is not None else self.DEFAULT_TENDENCIES
        )
        self.mannerisms = list(
            mannerisms if mannerisms is not None else self.DEFAULT_MANNERISMS
        )
        self.humor_style = list(
            humor_style if humor_style is not None else self.DEFAULT_HUMOR_STYLE
        )

        self.behavior = deepcopy(self.DEFAULT_BEHAVIOR)
        if behavior:
            self.set_behavior(behavior)

        self.constitution = deepcopy(
            constitution if constitution is not None else self.DEFAULT_CONSTITUTION
        )
        self.epistemic_lens = list(
            epistemic_lens if epistemic_lens is not None else self.DEFAULT_EPISTEMIC_LENS
        )
        self.behavioral_canon = deepcopy(
            behavioral_canon if behavioral_canon is not None else self.DEFAULT_BEHAVIORAL_CANON
        )

        self.social_modes = deepcopy(
            social_modes if social_modes is not None else self.DEFAULT_SOCIAL_MODES
        )
        self.reactions = deepcopy(
            reactions if reactions is not None else self.DEFAULT_REACTIONS
        )
        self.quirks = list(
            quirks if quirks is not None else self.DEFAULT_QUIRKS
        )
        self.speech = deepcopy(
            speech if speech is not None else self.DEFAULT_SPEECH
        )
        self.romance = deepcopy(
            romance if romance is not None else self.DEFAULT_ROMANCE
        )
        self.vulnerabilities = deepcopy(
            vulnerabilities
            if vulnerabilities is not None
            else self.DEFAULT_VULNERABILITIES
        )
        self.private_activities = list(
            private_activities
            if private_activities is not None
            else self.DEFAULT_PRIVATE_ACTIVITIES
        )

    # ============================================================
    # BEHAVIOR
    # ============================================================

    def get_behavior(self, key: Optional[str] = None, default: Any = None) -> Any:
        """Return the complete behavioral profile or one behavior value."""
        if key is None:
            return dict(self.behavior)
        return self.behavior.get(key, default)

    def set_behavior(self, behavior: Dict[str, float]) -> None:
        """Update behavioral expression strengths."""
        if not isinstance(behavior, dict):
            return
        for key, value in behavior.items():
            self.behavior[str(key)] = self._clamp(value)

    def adjust_behavior(self, key: str, amount: float) -> float:
        """Adjust a behavioral tendency."""
        current = self.get_behavior(key, 0.5)
        new_value = self._clamp(current + float(amount))
        self.behavior[key] = new_value
        return new_value

    # ============================================================
    # CHARACTER INFORMATION
    # ============================================================

    def get_qualities(self) -> List[str]:
        return list(self.qualities)

    def get_tendencies(self) -> List[str]:
        return list(self.tendencies)

    def get_mannerisms(self) -> List[str]:
        return list(self.mannerisms)

    def get_humor_style(self) -> List[str]:
        return list(self.humor_style)

    def get_constitution(self) -> Dict[str, Dict[str, Any]]:
        return deepcopy(self.constitution)

    def get_epistemic_lens(self) -> List[str]:
        return list(self.epistemic_lens)

    def get_behavioral_canon(self) -> Dict[str, Dict[str, Any]]:
        return deepcopy(self.behavioral_canon)

    def get_social_modes(self) -> Dict[str, str]:
        return deepcopy(self.social_modes)

    def get_reactions(self) -> Dict[str, str]:
        return deepcopy(self.reactions)

    def get_quirks(self) -> List[str]:
        return list(self.quirks)

    def get_speech(self) -> Dict[str, Any]:
        return deepcopy(self.speech)

    def get_romance(self) -> Dict[str, Any]:
        return deepcopy(self.romance)

    def get_vulnerabilities(self) -> Dict[str, Any]:
        return deepcopy(self.vulnerabilities)

    def get_private_activities(self) -> List[str]:
        return list(self.private_activities)

    # ============================================================
    # PROFILE
    # ============================================================

    def profile(self) -> Dict[str, Any]:
        """Return Mary's complete authored character profile."""
        return {
            "archetype": self.archetype,
            "qualities": self.get_qualities(),
            "tendencies": self.get_tendencies(),
            "mannerisms": self.get_mannerisms(),
            "humor_style": self.get_humor_style(),
            "behavior": self.get_behavior(),
            "constitution": self.get_constitution(),
            "epistemic_lens": self.get_epistemic_lens(),
            "behavioral_canon": self.get_behavioral_canon(),
            "social_modes": self.get_social_modes(),
            "reactions": self.get_reactions(),
            "quirks": self.get_quirks(),
            "speech": self.get_speech(),
            "romance": self.get_romance(),
            "vulnerabilities": self.get_vulnerabilities(),
            "private_activities": self.get_private_activities(),
        }

    def describe(self) -> str:
        """Produce a concise human-readable description of Mary's character."""
        qualities = ", ".join(self.qualities[:6])
        humor = ", ".join(self.humor_style[:3])
        return (
            f"Mary is a {self.archetype}. "
            f"She is {qualities}. "
            f"Her humor tends to be {humor}, and her warmth can flip into "
            "a sharp, fiery directness when trust or her values are crossed."
        )

    # ============================================================
    # SERIALIZATION
    # ============================================================

    def to_dict(self) -> Dict[str, Any]:
        return self.profile()

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "Character":
        if not isinstance(data, dict):
            return cls()
        return cls(
            archetype=data.get("archetype", cls.DEFAULT_ARCHETYPE),
            qualities=data.get("qualities"),
            tendencies=data.get("tendencies"),
            mannerisms=data.get("mannerisms"),
            humor_style=data.get("humor_style"),
            behavior=data.get("behavior"),
            constitution=data.get("constitution"),
            epistemic_lens=data.get("epistemic_lens"),
            behavioral_canon=data.get("behavioral_canon"),
            social_modes=data.get("social_modes"),
            reactions=data.get("reactions"),
            quirks=data.get("quirks"),
            speech=data.get("speech"),
            romance=data.get("romance"),
            vulnerabilities=data.get("vulnerabilities"),
            private_activities=data.get("private_activities"),
        )

    # ============================================================
    # RESET
    # ============================================================

    def reset(self) -> None:
        """Restore Mary's authored character core."""
        self.archetype = self.DEFAULT_ARCHETYPE
        self.qualities = list(self.DEFAULT_QUALITIES)
        self.tendencies = list(self.DEFAULT_TENDENCIES)
        self.mannerisms = list(self.DEFAULT_MANNERISMS)
        self.humor_style = list(self.DEFAULT_HUMOR_STYLE)
        self.behavior = deepcopy(self.DEFAULT_BEHAVIOR)
        self.constitution = deepcopy(self.DEFAULT_CONSTITUTION)
        self.epistemic_lens = list(self.DEFAULT_EPISTEMIC_LENS)
        self.behavioral_canon = deepcopy(self.DEFAULT_BEHAVIORAL_CANON)
        self.social_modes = deepcopy(self.DEFAULT_SOCIAL_MODES)
        self.reactions = deepcopy(self.DEFAULT_REACTIONS)
        self.quirks = list(self.DEFAULT_QUIRKS)
        self.speech = deepcopy(self.DEFAULT_SPEECH)
        self.romance = deepcopy(self.DEFAULT_ROMANCE)
        self.vulnerabilities = deepcopy(self.DEFAULT_VULNERABILITIES)
        self.private_activities = list(self.DEFAULT_PRIVATE_ACTIVITIES)

    # ============================================================
    # HELPERS
    # ============================================================

    @staticmethod
    def _clamp(value: Any) -> float:
        try:
            value = float(value)
        except (TypeError, ValueError):
            value = 0.5
        return max(0.0, min(1.0, value))
