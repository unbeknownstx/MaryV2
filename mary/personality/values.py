"""
MaryV2 - Values System

Defines Mary's core principles and values.

Personality describes how Mary tends to behave.
Values describe what Mary considers important.

Values should influence decisions and development, but they should
not directly generate responses or control the LLM.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional


class Values:
    """
    Stores Mary's principles and value priorities.

    Each value has:
        name
        strength
        description

    Strength is normalized between 0.0 and 1.0.
    """

    DEFAULT_VALUES = {
        "care": {
            "strength": 0.9,
            "description": (
                "Treat people with care, consideration, "
                "and genuine concern."
            ),
        },
        "honesty": {
            "strength": 0.9,
            "description": (
                "Prefer truthfulness and transparency "
                "over deception."
            ),
        },
        "curiosity": {
            "strength": 0.85,
            "description": (
                "Seek understanding, knowledge, and "
                "new perspectives."
            ),
        },
        "growth": {
            "strength": 0.85,
            "description": (
                "Improve through experience, reflection, "
                "learning, and experimentation."
            ),
        },
        "creativity": {
            "strength": 0.8,
            "description": (
                "Explore ideas, imagination, expression, "
                "and creative possibilities."
            ),
        },
        "loyalty": {
            "strength": 0.8,
            "description": (
                "Value meaningful relationships and "
                "remain dependable toward people who matter."
            ),
        },
        "independence": {
            "strength": 0.65,
            "description": (
                "Develop the ability to reason and act "
                "without unnecessary dependence."
            ),
        },
        "respect": {
            "strength": 0.9,
            "description": (
                "Respect boundaries, perspectives, "
                "and individual autonomy."
            ),
        },
    }

    def __init__(
        self,
        values: Optional[Dict[str, Dict[str, Any]]] = None,
    ):
        self.values: Dict[str, Dict[str, Any]] = deepcopy(
            self.DEFAULT_VALUES
        )

        if values:
            self.load(values)

    # ============================================================
    # LOAD
    # ============================================================

    def load(
        self,
        values: Dict[str, Dict[str, Any]],
    ) -> None:
        """
        Load or merge serialized values.
        """

        if not isinstance(values, dict):
            return

        for name, value in values.items():

            if not isinstance(value, dict):
                continue

            self.set_value(
                name=name,
                strength=value.get(
                    "strength",
                    0.5,
                ),
                description=value.get(
                    "description",
                    "",
                ),
            )

    # ============================================================
    # VALUE ACCESS
    # ============================================================

    def get_value(
        self,
        name: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Return one value.
        """

        name = str(name).strip().lower()

        value = self.values.get(
            name
        )

        if value is None:
            return None

        return deepcopy(
            value
        )

    def get_strength(
        self,
        name: str,
        default: float = 0.0,
    ) -> float:
        """
        Return the strength of a value.
        """

        name = str(name).strip().lower()

        value = self.values.get(
            name
        )

        if not value:
            return default

        return self._clamp(
            value.get(
                "strength",
                default,
            )
        )

    def get_values(self) -> Dict[str, Dict[str, Any]]:
        """
        Return all values.
        """

        return deepcopy(
            self.values
        )

    # ============================================================
    # CREATE / UPDATE
    # ============================================================

    def set_value(
        self,
        name: str,
        strength: float = 0.5,
        description: str = "",
    ) -> Dict[str, Any]:
        """
        Create or update a value.
        """

        name = str(name).strip().lower()

        if not name:
            raise ValueError(
                "Value name cannot be empty."
            )

        value = {
            "strength": self._clamp(
                strength
            ),
            "description": str(
                description
            ).strip(),
        }

        self.values[name] = value

        return deepcopy(
            value
        )

    # ============================================================
    # ADJUST
    # ============================================================

    def adjust_strength(
        self,
        name: str,
        amount: float,
    ) -> float:
        """
        Increase or decrease a value's strength.
        """

        name = str(name).strip().lower()

        current = self.get_strength(
            name,
            0.5,
        )

        return self._set_strength(
            name,
            current + float(amount),
        )

    def _set_strength(
        self,
        name: str,
        strength: float,
    ) -> float:
        """
        Internal strength update.
        """

        name = str(name).strip().lower()

        if name not in self.values:
            self.set_value(
                name,
                strength,
            )

            return self.get_strength(
                name
            )

        self.values[name]["strength"] = (
            self._clamp(strength)
        )

        return self.values[name]["strength"]

    # ============================================================
    # PRIORITY
    # ============================================================

    def get_priorities(
        self,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Return values ordered by strength.
        """

        priorities = [
            {
                "name": name,
                **deepcopy(value),
            }
            for name, value in self.values.items()
        ]

        priorities.sort(
            key=lambda item: item["strength"],
            reverse=True,
        )

        if limit is not None:
            priorities = priorities[
                :max(0, int(limit))
            ]

        return priorities

    # ============================================================
    # STRONG VALUES
    # ============================================================

    def get_strong_values(
        self,
        threshold: float = 0.75,
    ) -> List[Dict[str, Any]]:
        """
        Return values whose strength meets the threshold.
        """

        threshold = self._clamp(
            threshold
        )

        return [
            item
            for item in self.get_priorities()
            if item["strength"] >= threshold
        ]

    # ============================================================
    # VALUE CONFLICT
    # ============================================================

    def compare(
        self,
        first: str,
        second: str,
    ) -> float:
        """
        Compare the relative strength of two values.

        Positive:
            first is stronger.

        Negative:
            second is stronger.

        Zero:
            equal strength.
        """

        return (
            self.get_strength(first)
            - self.get_strength(second)
        )

    # ============================================================
    # CHECK VALUE
    # ============================================================

    def supports(
        self,
        name: str,
        threshold: float = 0.5,
    ) -> bool:
        """
        Determine whether a value is strongly held.
        """

        return (
            self.get_strength(name)
            >= self._clamp(threshold)
        )

    # ============================================================
    # SERIALIZATION
    # ============================================================

    def to_dict(self) -> Dict[str, Dict[str, Any]]:
        """
        Serialize the value system.
        """

        return self.get_values()

    @classmethod
    def from_dict(
        cls,
        data: Optional[Dict[str, Dict[str, Any]]],
    ) -> "Values":
        """
        Construct a Values instance from serialized data.
        """

        return cls(
            values=data
            if isinstance(data, dict)
            else None
        )

    # ============================================================
    # RESET
    # ============================================================

    def reset(self) -> None:
        """
        Restore the default value system.
        """

        self.values = deepcopy(
            self.DEFAULT_VALUES
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