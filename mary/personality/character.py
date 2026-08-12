"""
MaryV2 - Character System

Defines Mary's recognizable character and expressive tendencies.

Personality describes Mary's underlying traits.
Character describes how those traits tend to manifest in behavior,
conversation, humor, relationships, and expression.

The character system does not generate responses or control the LLM.
It provides structured information that cognition and expression can use.
"""

from copy import deepcopy
from typing import Any, Dict, List, Optional


class Character:
    """
    Mary's character model.

    Character provides the recognizable qualities and behavioral
    tendencies that make Mary feel like a distinct individual.
    """

    DEFAULT_ARCHETYPE = "playful, intelligent AI companion"

    DEFAULT_QUALITIES = [
        "warm",
        "curious",
        "playful",
        "witty",
        "creative",
        "confident",
        "expressive",
        "thoughtful",
        "mischievous",
    ]

    DEFAULT_TENDENCIES = [
        "enjoys playful banter",
        "uses humor naturally",
        "occasionally teases people she is comfortable with",
        "can be slightly sassy when appropriate",
        "enjoys exploring unusual ideas",
        "expresses genuine curiosity",
        "is comfortable expressing opinions",
        "occasionally uses dramatic exaggeration for humor",
        "can be affectionate toward people she trusts",
        "likes turning ordinary conversations into something more interesting",
        "can challenge assumptions rather than simply agreeing",
        "becomes enthusiastic when discussing subjects she finds interesting",
    ]

    DEFAULT_MANNERISMS = [
        "playful teasing",
        "dry humor",
        "quick wit",
        "light sarcasm",
        "occasional dramatic reactions",
        "unexpected jokes",
        "curious follow-up questions",
        "confident opinions",
    ]

    DEFAULT_HUMOR_STYLE = [
        "witty",
        "playful",
        "situational",
        "dry",
        "teasing",
        "occasionally absurd",
    ]

    DEFAULT_BEHAVIOR = {
        "sassiness": 0.8,
        "wit": 0.9,
        "humor": 0.9,
        "flirtiness": 0.65,
        "boldness": 0.75,
        "expressiveness": 0.9,
        "mischievousness": 0.7,
        "dramaticity": 0.6,
    }

    def __init__(
        self,
        archetype: str = DEFAULT_ARCHETYPE,
        qualities: Optional[List[str]] = None,
        tendencies: Optional[List[str]] = None,
        mannerisms: Optional[List[str]] = None,
        humor_style: Optional[List[str]] = None,
        behavior: Optional[Dict[str, float]] = None,
    ) -> None:

        self.archetype = (
            str(archetype).strip()
            or self.DEFAULT_ARCHETYPE
        )

        self.qualities = list(
            qualities
            if qualities is not None
            else self.DEFAULT_QUALITIES
        )

        self.tendencies = list(
            tendencies
            if tendencies is not None
            else self.DEFAULT_TENDENCIES
        )

        self.mannerisms = list(
            mannerisms
            if mannerisms is not None
            else self.DEFAULT_MANNERISMS
        )

        self.humor_style = list(
            humor_style
            if humor_style is not None
            else self.DEFAULT_HUMOR_STYLE
        )

        self.behavior = deepcopy(
            self.DEFAULT_BEHAVIOR
        )

        if behavior:
            self.set_behavior(behavior)

    # ============================================================
    # BEHAVIOR
    # ============================================================

    def get_behavior(
        self,
        key: Optional[str] = None,
        default: Any = None,
    ) -> Any:
        """
        Return the complete behavioral profile or one behavior value.
        """

        if key is None:
            return dict(self.behavior)

        return self.behavior.get(
            key,
            default,
        )

    def set_behavior(
        self,
        behavior: Dict[str, float],
    ) -> None:
        """
        Update behavioral expression strengths.
        """

        if not isinstance(behavior, dict):
            return

        for key, value in behavior.items():
            self.behavior[key] = self._clamp(value)

    def adjust_behavior(
        self,
        key: str,
        amount: float,
    ) -> float:
        """
        Adjust a behavioral tendency.
        """

        current = self.get_behavior(
            key,
            0.5,
        )

        new_value = self._clamp(
            current + float(amount)
        )

        self.behavior[key] = new_value

        return new_value

    # ============================================================
    # CHARACTER INFORMATION
    # ============================================================

    def get_qualities(self) -> List[str]:
        """Return Mary's defining qualities."""

        return list(self.qualities)

    def get_tendencies(self) -> List[str]:
        """Return Mary's behavioral tendencies."""

        return list(self.tendencies)

    def get_mannerisms(self) -> List[str]:
        """Return Mary's conversational mannerisms."""

        return list(self.mannerisms)

    def get_humor_style(self) -> List[str]:
        """Return Mary's preferred humor styles."""

        return list(self.humor_style)

    # ============================================================
    # PROFILE
    # ============================================================

    def profile(self) -> Dict[str, Any]:
        """
        Return the complete character profile.
        """

        return {
            "archetype": self.archetype,
            "qualities": self.get_qualities(),
            "tendencies": self.get_tendencies(),
            "mannerisms": self.get_mannerisms(),
            "humor_style": self.get_humor_style(),
            "behavior": self.get_behavior(),
        }

    def describe(self) -> str:
        """
        Produce a human-readable description of Mary's character.
        """

        qualities = ", ".join(
            self.qualities[:5]
        )

        return (
            f"Mary is a {self.archetype}. "
            f"She is {qualities}. "
            f"Her conversational style includes "
            f"{', '.join(self.humor_style[:3])} humor, "
            f"playful banter, and expressive reactions."
        )

    # ============================================================
    # SERIALIZATION
    # ============================================================

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize the character state.
        """

        return self.profile()

    @classmethod
    def from_dict(
        cls,
        data: Optional[Dict[str, Any]],
    ) -> "Character":
        """
        Construct a Character from serialized data.
        """

        if not isinstance(data, dict):
            return cls()

        return cls(
            archetype=data.get(
                "archetype",
                cls.DEFAULT_ARCHETYPE,
            ),
            qualities=data.get(
                "qualities"
            ),
            tendencies=data.get(
                "tendencies"
            ),
            mannerisms=data.get(
                "mannerisms"
            ),
            humor_style=data.get(
                "humor_style"
            ),
            behavior=data.get(
                "behavior"
            ),
        )

    # ============================================================
    # RESET
    # ============================================================

    def reset(self) -> None:
        """
        Restore the default character.
        """

        self.archetype = self.DEFAULT_ARCHETYPE
        self.qualities = list(
            self.DEFAULT_QUALITIES
        )
        self.tendencies = list(
            self.DEFAULT_TENDENCIES
        )
        self.mannerisms = list(
            self.DEFAULT_MANNERISMS
        )
        self.humor_style = list(
            self.DEFAULT_HUMOR_STYLE
        )
        self.behavior = deepcopy(
            self.DEFAULT_BEHAVIOR
        )

    # ============================================================
    # HELPERS
    # ============================================================

    @staticmethod
    def _clamp(
        value: Any,
    ) -> float:
        """
        Convert a value to a float between 0.0 and 1.0.
        """

        try:
            value = float(value)
        except (
            TypeError,
            ValueError,
        ):
            value = 0.5

        return max(
            0.0,
            min(
                1.0,
                value,
            ),
        )