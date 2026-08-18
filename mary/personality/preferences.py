"""
MaryV2 - Preferences System

Stores Mary's preferences.

Personality describes how Mary tends to behave.
Values describe what Mary considers important.
Preferences describe what Mary tends to like, dislike, or prefer.

Preferences can be changed through experience and learning without
necessarily changing Mary's underlying personality or values.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, List, Optional

from mary.personality.character_core import CORE_PREFERENCES


class Preferences:
    """
    Mary's preference model.

    Preferences are intentionally lightweight and mutable.

    Each preference contains:

        name
        category
        strength
        polarity
        confidence
        source
        created_at
        updated_at

    polarity:
        +1.0 = strong preference
        -1.0 = strong dislike
         0.0 = neutral

    strength:
        How strongly Mary currently prefers the item.

    confidence:
        How confident the system is that the preference is valid.
    """

    def __init__(
        self,
        preferences: Optional[
            Dict[str, Dict[str, Any]]
        ] = None,
    ):
        self.preferences: Dict[
            str,
            Dict[str, Any],
        ] = {}

        # Authored core preferences are different from preferences learned from
        # later experiences.  Seed the established Mary baseline first, then
        # allow serialized/learned state to override it intentionally.
        self._seed_core_preferences()

        if preferences:
            self.load(
                preferences
            )


    def _seed_core_preferences(self) -> None:
        """Restore Mary's established authored likes and dislikes."""

        for name, preference in CORE_PREFERENCES.items():
            self.set_preference(
                name=name,
                category=preference.get("category", "general"),
                strength=preference.get("strength", 0.5),
                polarity=preference.get("polarity", 1.0),
                confidence=1.0,
                source="character_core",
            )

    # ============================================================
    # CREATE / UPDATE
    # ============================================================

    def set_preference(
        self,
        name: str,
        category: str = "general",
        strength: float = 0.5,
        polarity: float = 1.0,
        confidence: float = 0.5,
        source: str = "system",
    ) -> Dict[str, Any]:
        """
        Create or update a preference.
        """

        name = self._normalize_name(
            name
        )

        if not name:
            raise ValueError(
                "Preference name cannot be empty."
            )

        now = datetime.now().isoformat()

        existing = self.preferences.get(
            name
        )

        created_at = (
            existing.get(
                "created_at",
                now,
            )
            if existing
            else now
        )

        preference = {
            "name": name,
            "category": str(
                category
            ).strip().lower() or "general",
            "strength": self._clamp(
                strength
            ),
            "polarity": self._clamp_signed(
                polarity
            ),
            "confidence": self._clamp(
                confidence
            ),
            "source": str(
                source
            ).strip() or "system",
            "created_at": created_at,
            "updated_at": now,
        }

        self.preferences[name] = (
            preference
        )

        return deepcopy(
            preference
        )

    # ============================================================
    # GET
    # ============================================================

    def get_preference(
        self,
        name: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Return a single preference.
        """

        name = self._normalize_name(
            name
        )

        preference = self.preferences.get(
            name
        )

        if preference is None:
            return None

        return deepcopy(
            preference
        )

    def has_preference(
        self,
        name: str,
    ) -> bool:
        """
        Determine whether a preference exists.
        """

        return (
            self._normalize_name(name)
            in self.preferences
        )

    def get_preferences(
        self,
    ) -> List[Dict[str, Any]]:
        """
        Return all preferences.
        """

        return [
            deepcopy(preference)
            for preference in self.preferences.values()
        ]

    # ============================================================
    # CATEGORY
    # ============================================================

    def get_by_category(
        self,
        category: str,
    ) -> List[Dict[str, Any]]:
        """
        Return preferences belonging to a category.
        """

        category = str(
            category
        ).strip().lower()

        return [
            deepcopy(preference)
            for preference in self.preferences.values()
            if preference.get(
                "category"
            ) == category
        ]

    # ============================================================
    # LIKES
    # ============================================================

    def get_likes(
        self,
        minimum_strength: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """
        Return positive preferences.
        """

        minimum_strength = self._clamp(
            minimum_strength
        )

        return [
            deepcopy(preference)
            for preference in self.preferences.values()
            if (
                preference.get(
                    "polarity",
                    0.0,
                ) > 0
                and preference.get(
                    "strength",
                    0.0,
                ) >= minimum_strength
            )
        ]

    # ============================================================
    # DISLIKES
    # ============================================================

    def get_dislikes(
        self,
        minimum_strength: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """
        Return negative preferences.
        """

        minimum_strength = self._clamp(
            minimum_strength
        )

        return [
            deepcopy(preference)
            for preference in self.preferences.values()
            if (
                preference.get(
                    "polarity",
                    0.0,
                ) < 0
                and preference.get(
                    "strength",
                    0.0,
                ) >= minimum_strength
            )
        ]

    # ============================================================
    # PREFERENCE SCORE
    # ============================================================

    def score(
        self,
        name: str,
    ) -> float:
        """
        Return a combined preference score.

        Range:
            -1.0 to +1.0

        Positive values represent preference.
        Negative values represent dislike.
        """

        preference = self.get_preference(
            name
        )

        if preference is None:
            return 0.0

        return (
            preference["polarity"]
            * preference["strength"]
        )

    # ============================================================
    # ADJUST
    # ============================================================

    def adjust(
        self,
        name: str,
        amount: float,
        confidence: Optional[float] = None,
        source: str = "experience",
    ) -> Optional[Dict[str, Any]]:
        """
        Adjust an existing preference.

        If the preference does not exist, a neutral preference
        is created first.
        """

        name = self._normalize_name(
            name
        )

        existing = self.preferences.get(
            name
        )

        if existing is None:

            self.set_preference(
                name=name,
                strength=0.0,
                polarity=1.0,
                confidence=0.0,
                source=source,
            )

            existing = self.preferences[name]

        current_score = (
            existing["polarity"]
            * existing["strength"]
        )

        new_score = max(
            -1.0,
            min(
                1.0,
                current_score
                + float(amount),
            ),
        )

        if new_score >= 0:
            polarity = 1.0
            strength = new_score
        else:
            polarity = -1.0
            strength = abs(new_score)

        existing["polarity"] = polarity
        existing["strength"] = strength
        existing["source"] = (
            str(source).strip()
            or existing.get(
                "source",
                "experience",
            )
        )
        existing["updated_at"] = (
            datetime.now().isoformat()
        )

        if confidence is not None:
            existing["confidence"] = (
                self._clamp(
                    confidence
                )
            )

        return deepcopy(
            existing
        )

    # ============================================================
    # CONFIDENCE
    # ============================================================

    def update_confidence(
        self,
        name: str,
        confidence: float,
    ) -> Optional[Dict[str, Any]]:
        """
        Update confidence in a preference.
        """

        name = self._normalize_name(
            name
        )

        preference = self.preferences.get(
            name
        )

        if preference is None:
            return None

        preference["confidence"] = (
            self._clamp(
                confidence
            )
        )

        preference["updated_at"] = (
            datetime.now().isoformat()
        )

        return deepcopy(
            preference
        )

    # ============================================================
    # FORGET
    # ============================================================

    def remove(
        self,
        name: str,
    ) -> bool:
        """
        Remove a preference.
        """

        name = self._normalize_name(
            name
        )

        if name not in self.preferences:
            return False

        del self.preferences[name]

        return True

    # ============================================================
    # SORTING
    # ============================================================

    def get_strongest(
        self,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Return strongest preferences first.
        """

        preferences = self.get_preferences()

        preferences.sort(
            key=lambda item: (
                abs(
                    item.get(
                        "polarity",
                        0.0,
                    )
                    * item.get(
                        "strength",
                        0.0,
                    )
                )
            ),
            reverse=True,
        )

        if limit is not None:
            preferences = preferences[
                :max(0, int(limit))
            ]

        return preferences

    # ============================================================
    # SERIALIZATION
    # ============================================================

    def to_dict(
        self,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Serialize preferences.
        """

        return deepcopy(
            self.preferences
        )

    @classmethod
    def from_dict(
        cls,
        data: Optional[
            Dict[str, Dict[str, Any]]
        ],
    ) -> "Preferences":
        """
        Construct Preferences from serialized data.
        """

        if not isinstance(
            data,
            dict,
        ):
            return cls()

        return cls(
            preferences=data
        )

    def load(
        self,
        data: Dict[str, Dict[str, Any]],
    ) -> None:
        """
        Load serialized preferences.
        """

        if not isinstance(
            data,
            dict,
        ):
            return

        for name, preference in data.items():

            if not isinstance(
                preference,
                dict,
            ):
                continue

            self.set_preference(
                name=preference.get(
                    "name",
                    name,
                ),
                category=preference.get(
                    "category",
                    "general",
                ),
                strength=preference.get(
                    "strength",
                    0.5,
                ),
                polarity=preference.get(
                    "polarity",
                    1.0,
                ),
                confidence=preference.get(
                    "confidence",
                    0.5,
                ),
                source=preference.get(
                    "source",
                    "system",
                ),
            )

    # ============================================================
    # RESET
    # ============================================================

    def reset(self) -> None:
        """
        Restore Mary's authored core preferences and remove later learned overrides.
        """

        self.preferences = {}
        self._seed_core_preferences()

    # ============================================================
    # HELPERS
    # ============================================================

    @staticmethod
    def _normalize_name(
        name: Any,
    ) -> str:
        """
        Normalize a preference identifier.
        """

        return str(
            name
        ).strip().lower()

    @staticmethod
    def _clamp(
        value: Any,
    ) -> float:
        """
        Clamp a numeric value to 0.0 - 1.0.
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

    @staticmethod
    def _clamp_signed(
        value: Any,
    ) -> float:
        """
        Clamp a numeric value to -1.0 - 1.0.
        """

        try:
            value = float(value)
        except (
            TypeError,
            ValueError,
        ):
            value = 0.0

        return max(
            -1.0,
            min(
                1.0,
                value,
            ),
        )