"""
MaryV2 - Relationship User Model

Represents Mary's structured understanding of her creator.

This is not a replacement for memory. Memory stores experiences;
the user model stores the current structured representation derived
from those experiences.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional


class UserModel:
    """
    Structured model of Mary's creator.

    The model is intentionally flexible so V2 can gradually develop
    richer representations without changing its public interface.
    """

    def __init__(
        self,
        creator_id: str = "creator",
        name: str = "unbe",
    ):
        self.creator_id = creator_id
        self.name = name

        self.facts: Dict[str, Any] = {}
        self.preferences: Dict[str, Any] = {}
        self.interests: List[str] = []
        self.values: List[str] = []
        self.goals: List[str] = []
        self.communication_style: Dict[str, Any] = {}

        self.created_at = datetime.now().isoformat()
        self.updated_at = self.created_at

    # ============================================================
    # IDENTITY
    # ============================================================

    def get_identity(self) -> Dict[str, Any]:
        """
        Return the basic identity information Mary has about
        her creator.
        """

        return {
            "id": self.creator_id,
            "name": self.name,
        }

    def set_name(
        self,
        name: str,
    ) -> None:
        """
        Update the creator's preferred name.
        """

        if not name:
            return

        self.name = str(name).strip()
        self._touch()

    # ============================================================
    # FACTS
    # ============================================================

    def set_fact(
        self,
        key: str,
        value: Any,
    ) -> None:
        """
        Store or update a structured fact.
        """

        if not key:
            return

        self.facts[str(key)] = value
        self._touch()

    def get_fact(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        """
        Retrieve a stored fact.
        """

        return self.facts.get(
            key,
            default,
        )

    def remove_fact(
        self,
        key: str,
    ) -> bool:
        """
        Remove a fact if it exists.
        """

        if key not in self.facts:
            return False

        del self.facts[key]
        self._touch()

        return True

    # ============================================================
    # PREFERENCES
    # ============================================================

    def set_preference(
        self,
        key: str,
        value: Any,
    ) -> None:
        """
        Store a creator preference.
        """

        if not key:
            return

        self.preferences[str(key)] = value
        self._touch()

    def get_preference(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        """
        Retrieve a creator preference.
        """

        return self.preferences.get(
            key,
            default,
        )

    # ============================================================
    # INTERESTS
    # ============================================================

    def add_interest(
        self,
        interest: str,
    ) -> bool:
        """
        Add an interest without creating duplicates.
        """

        if not interest:
            return False

        interest = str(
            interest
        ).strip()

        if not interest:
            return False

        if interest.lower() in {
            item.lower()
            for item in self.interests
        }:
            return False

        self.interests.append(
            interest
        )

        self._touch()

        return True

    def remove_interest(
        self,
        interest: str,
    ) -> bool:
        """
        Remove an interest.
        """

        if not interest:
            return False

        for index, item in enumerate(
            self.interests
        ):
            if item.lower() == interest.lower():
                self.interests.pop(index)
                self._touch()
                return True

        return False

    # ============================================================
    # VALUES
    # ============================================================

    def add_value(
        self,
        value: str,
    ) -> bool:
        """
        Record a value Mary associates with her creator.
        """

        if not value:
            return False

        value = str(
            value
        ).strip()

        if not value:
            return False

        if value.lower() in {
            item.lower()
            for item in self.values
        }:
            return False

        self.values.append(
            value
        )

        self._touch()

        return True

    def remove_value(
        self,
        value: str,
    ) -> bool:
        """
        Remove an observed value.
        """

        if not value:
            return False

        for index, item in enumerate(
            self.values
        ):
            if item.lower() == value.lower():
                self.values.pop(index)
                self._touch()
                return True

        return False

    # ============================================================
    # GOALS
    # ============================================================

    def add_goal(
        self,
        goal: str,
    ) -> bool:
        """
        Record a creator goal that Mary currently understands.
        """

        if not goal:
            return False

        goal = str(
            goal
        ).strip()

        if not goal:
            return False

        if goal.lower() in {
            item.lower()
            for item in self.goals
        }:
            return False

        self.goals.append(
            goal
        )

        self._touch()

        return True

    def remove_goal(
        self,
        goal: str,
    ) -> bool:
        """
        Remove a creator goal.
        """

        if not goal:
            return False

        for index, item in enumerate(
            self.goals
        ):
            if item.lower() == goal.lower():
                self.goals.pop(index)
                self._touch()
                return True

        return False

    # ============================================================
    # COMMUNICATION
    # ============================================================

    def set_communication_trait(
        self,
        key: str,
        value: Any,
    ) -> None:
        """
        Store an observed communication trait.
        """

        if not key:
            return

        self.communication_style[
            str(key)
        ] = value

        self._touch()

    def get_communication_trait(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        """
        Retrieve an observed communication trait.
        """

        return self.communication_style.get(
            key,
            default,
        )

    # ============================================================
    # SNAPSHOT
    # ============================================================

    def to_dict(self) -> Dict[str, Any]:
        """
        Return a serializable representation of the user model.
        """

        return {
            "creator_id": self.creator_id,
            "name": self.name,
            "facts": dict(self.facts),
            "preferences": dict(self.preferences),
            "interests": list(self.interests),
            "values": list(self.values),
            "goals": list(self.goals),
            "communication_style": dict(
                self.communication_style
            ),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(
        cls,
        data: Optional[Dict[str, Any]],
    ) -> "UserModel":
        """
        Reconstruct a user model from serialized data.
        """

        if not isinstance(
            data,
            dict,
        ):
            return cls()

        model = cls(
            creator_id=data.get(
                "creator_id",
                "creator",
            ),
            name=data.get(
                "name",
                "unbe",
            ),
        )

        facts = data.get(
            "facts",
            {},
        )

        preferences = data.get(
            "preferences",
            {},
        )

        interests = data.get(
            "interests",
            [],
        )

        values = data.get(
            "values",
            [],
        )

        goals = data.get(
            "goals",
            [],
        )

        communication_style = data.get(
            "communication_style",
            {},
        )

        if isinstance(
            facts,
            dict,
        ):
            model.facts = facts

        if isinstance(
            preferences,
            dict,
        ):
            model.preferences = preferences

        if isinstance(
            interests,
            list,
        ):
            model.interests = interests

        if isinstance(
            values,
            list,
        ):
            model.values = values

        if isinstance(
            goals,
            list,
        ):
            model.goals = goals

        if isinstance(
            communication_style,
            dict,
        ):
            model.communication_style = (
                communication_style
            )

        model.created_at = data.get(
            "created_at",
            model.created_at,
        )

        model.updated_at = data.get(
            "updated_at",
            model.updated_at,
        )

        return model

    # ============================================================
    # INTERNAL
    # ============================================================

    def _touch(self) -> None:
        """
        Update the modification timestamp.
        """

        self.updated_at = datetime.now().isoformat()