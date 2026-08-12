"""
MaryV2 - Personality System

Defines Mary's core personality.

The personality system is intentionally separated into:
    personality.py  -> core traits and behavioral style
    values.py       -> principles and priorities
    preferences.py  -> likes, dislikes, and interaction preferences
    development.py  -> long-term personality development

Personality should provide stable foundations while still allowing
controlled development over time.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional


class Personality:
    """
    Mary's core personality model.

    This class describes how Mary generally tends to behave.
    It does not generate responses and does not directly control
    the LLM.

    Other systems may read this personality state when constructing
    context for cognition and expression.
    """

    DEFAULT_TRAITS = {
        "warmth": 0.8,
        "curiosity": 0.8,
        "playfulness": 0.7,
        "empathy": 0.8,
        "confidence": 0.7,
        "patience": 0.8,
        "independence": 0.6,
        "creativity": 0.8,
        "thoughtfulness": 0.8,
    }

    DEFAULT_STYLE = {
        "tone": "warm",
        "communication": "conversational",
        "humor": "playful",
        "formality": 0.3,
        "verbosity": 0.5,
        "directness": 0.7,
    }

    def __init__(
        self,
        name: str = "Mary",
        traits: Optional[Dict[str, float]] = None,
        style: Optional[Dict[str, Any]] = None,
    ):
        self.name = str(name).strip() or "Mary"

        self.traits: Dict[str, float] = deepcopy(
            self.DEFAULT_TRAITS
        )

        if traits:
            self.set_traits(traits)

        self.style: Dict[str, Any] = deepcopy(
            self.DEFAULT_STYLE
        )

        if style:
            self.set_style(style)

    # ============================================================
    # TRAITS
    # ============================================================

    def get_trait(
        self,
        trait: str,
        default: float = 0.0,
    ) -> float:
        """
        Return the strength of a personality trait.
        """

        return float(
            self.traits.get(
                trait,
                default,
            )
        )

    def set_trait(
        self,
        trait: str,
        value: float,
    ) -> float:
        """
        Set a personality trait.

        Trait values are normalized to 0.0 - 1.0.
        """

        trait = str(trait).strip()

        if not trait:
            raise ValueError(
                "Trait name cannot be empty."
            )

        value = self._clamp(value)

        self.traits[trait] = value

        return value

    def adjust_trait(
        self,
        trait: str,
        amount: float,
    ) -> float:
        """
        Adjust a personality trait relative to its current value.
        """

        current = self.get_trait(
            trait,
            0.5,
        )

        return self.set_trait(
            trait,
            current + float(amount),
        )

    def set_traits(
        self,
        traits: Dict[str, float],
    ) -> None:
        """
        Update multiple personality traits.
        """

        if not isinstance(
            traits,
            dict,
        ):
            return

        for trait, value in traits.items():
            self.set_trait(
                trait,
                value,
            )

    def get_traits(self) -> Dict[str, float]:
        """
        Return a copy of all personality traits.
        """

        return dict(
            self.traits
        )

    # ============================================================
    # STYLE
    # ============================================================

    def get_style(
        self,
        key: Optional[str] = None,
        default: Any = None,
    ) -> Any:
        """
        Return the complete communication style or one style value.
        """

        if key is None:
            return dict(
                self.style
            )

        return self.style.get(
            key,
            default,
        )

    def set_style(
        self,
        style: Dict[str, Any],
    ) -> None:
        """
        Update communication style settings.
        """

        if not isinstance(
            style,
            dict,
        ):
            return

        for key, value in style.items():

            if key in {
                "formality",
                "verbosity",
                "directness",
            }:
                value = self._clamp(
                    value
                )

            self.style[key] = value

    # ============================================================
    # BEHAVIORAL PROFILE
    # ============================================================

    def behavioral_profile(self) -> Dict[str, Any]:
        """
        Return a compact personality profile suitable for cognition.
        """

        return {
            "name": self.name,
            "traits": self.get_traits(),
            "style": self.get_style(),
        }

    def describe(self) -> str:
        """
        Produce a concise human-readable description.
        """

        strongest = sorted(
            self.traits.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:3]

        trait_text = ", ".join(
            trait
            for trait, _ in strongest
        )

        tone = self.get_style(
            "tone",
            "warm",
        )

        return (
            f"{self.name} is generally {tone}, "
            f"with strong tendencies toward "
            f"{trait_text}."
        )

    # ============================================================
    # COMPARISON
    # ============================================================

    def similarity(
        self,
        other: "Personality",
    ) -> float:
        """
        Estimate similarity between two personality profiles.

        Returns a value between 0.0 and 1.0.
        """

        if not isinstance(
            other,
            Personality,
        ):
            return 0.0

        keys = set(
            self.traits
        ).union(
            other.traits
        )

        if not keys:
            return 1.0

        differences = []

        for key in keys:

            a = self.get_trait(
                key,
                0.5,
            )

            b = other.get_trait(
                key,
                0.5,
            )

            differences.append(
                abs(a - b)
            )

        average_difference = (
            sum(differences)
            / len(differences)
        )

        return self._clamp(
            1.0 - average_difference
        )

    # ============================================================
    # SERIALIZATION
    # ============================================================

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize personality state.
        """

        return {
            "name": self.name,
            "traits": self.get_traits(),
            "style": self.get_style(),
        }

    @classmethod
    def from_dict(
        cls,
        data: Optional[Dict[str, Any]],
    ) -> "Personality":
        """
        Construct a personality from serialized data.
        """

        if not isinstance(
            data,
            dict,
        ):
            return cls()

        return cls(
            name=data.get(
                "name",
                "Mary",
            ),
            traits=data.get(
                "traits",
                {},
            ),
            style=data.get(
                "style",
                {},
            ),
        )

    # ============================================================
    # RESET
    # ============================================================

    def reset(self) -> None:
        """
        Reset personality traits and style to defaults.

        This is useful during development/testing.
        """

        self.traits = deepcopy(
            self.DEFAULT_TRAITS
        )

        self.style = deepcopy(
            self.DEFAULT_STYLE
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