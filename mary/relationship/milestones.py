# mary/relationship/milestones.py

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional


class MilestoneManager:
    """
    Tracks meaningful milestones in Mary's relationship with her creator.

    Milestones are durable relationship events such as:
    - important shared experiences
    - major discoveries
    - meaningful conversations
    - achievements
    - important firsts
    - changes in the relationship

    This system does not replace relationship history.
    History stores events.
    Milestones stores events that have lasting relationship significance.
    """

    def __init__(self, milestones: Optional[List[Dict[str, Any]]] = None):
        self.milestones: List[Dict[str, Any]] = []

        if milestones:
            self.load(milestones)

    # ============================================================
    # LOAD
    # ============================================================

    def load(self, milestones: List[Dict[str, Any]]) -> None:
        """
        Load milestone records into memory.
        """

        if not isinstance(milestones, list):
            self.milestones = []
            return

        self.milestones = [
            milestone
            for milestone in milestones
            if isinstance(milestone, dict)
        ]

    # ============================================================
    # EXPORT
    # ============================================================

    def export(self) -> List[Dict[str, Any]]:
        """
        Return milestones in a JSON-compatible format.
        """

        return list(self.milestones)

    # ============================================================
    # ADD
    # ============================================================

    def add_milestone(
        self,
        title: str,
        description: str,
        category: str = "general",
        importance: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create and store a new relationship milestone.
        """

        title = str(title).strip()
        description = str(description).strip()

        if not title:
            raise ValueError("Milestone title cannot be empty.")

        if not description:
            raise ValueError(
                "Milestone description cannot be empty."
            )

        importance = self._clamp_importance(importance)

        milestone = {
            "id": self._next_id(),
            "title": title,
            "description": description,
            "category": str(category).strip() or "general",
            "importance": importance,
            "created_at": datetime.now().isoformat(),
            "metadata": (
                dict(metadata)
                if isinstance(metadata, dict)
                else {}
            ),
        }

        self.milestones.append(milestone)

        return milestone

    # ============================================================
    # FIND
    # ============================================================

    def get_milestone(
        self,
        milestone_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve a milestone by ID.
        """

        for milestone in self.milestones:
            if milestone.get("id") == milestone_id:
                return milestone

        return None

    # ============================================================
    # ALL
    # ============================================================

    def get_milestones(self) -> List[Dict[str, Any]]:
        """
        Return all milestones.
        """

        return list(self.milestones)

    # ============================================================
    # RECENT
    # ============================================================

    def get_recent(
        self,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Return the most recently created milestones.
        """

        if limit <= 0:
            return []

        return list(
            reversed(self.milestones[-limit:])
        )

    # ============================================================
    # IMPORTANT
    # ============================================================

    def get_important(
        self,
        minimum_importance: float = 0.7,
    ) -> List[Dict[str, Any]]:
        """
        Return milestones meeting the importance threshold.
        """

        threshold = self._clamp_importance(
            minimum_importance
        )

        return [
            milestone
            for milestone in self.milestones
            if self._safe_float(
                milestone.get("importance", 0.0)
            ) >= threshold
        ]

    # ============================================================
    # CATEGORY
    # ============================================================

    def get_by_category(
        self,
        category: str,
    ) -> List[Dict[str, Any]]:
        """
        Return milestones belonging to a category.
        """

        category = str(category).strip().lower()

        return [
            milestone
            for milestone in self.milestones
            if str(
                milestone.get("category", "")
            ).strip().lower() == category
        ]

    # ============================================================
    # SEARCH
    # ============================================================

    def search(
        self,
        query: str,
    ) -> List[Dict[str, Any]]:
        """
        Search milestone titles and descriptions.
        """

        query = str(query).strip().lower()

        if not query:
            return []

        results = []

        for milestone in self.milestones:

            title = str(
                milestone.get("title", "")
            ).lower()

            description = str(
                milestone.get("description", "")
            ).lower()

            if (
                query in title
                or query in description
            ):
                results.append(milestone)

        return results

    # ============================================================
    # REMOVE
    # ============================================================

    def remove_milestone(
        self,
        milestone_id: str,
    ) -> bool:
        """
        Remove a milestone by ID.
        """

        for index, milestone in enumerate(
            self.milestones
        ):
            if milestone.get("id") == milestone_id:

                self.milestones.pop(index)

                return True

        return False

    # ============================================================
    # COUNT
    # ============================================================

    def count(self) -> int:
        """
        Return the number of stored milestones.
        """

        return len(self.milestones)

    # ============================================================
    # NEXT ID
    # ============================================================

    def _next_id(self) -> str:
        """
        Generate the next milestone ID.
        """

        highest = 0

        for milestone in self.milestones:

            milestone_id = str(
                milestone.get("id", "")
            )

            if not milestone_id.startswith(
                "milestone_"
            ):
                continue

            try:
                number = int(
                    milestone_id.split("_")[-1]
                )

                highest = max(
                    highest,
                    number,
                )

            except ValueError:
                continue

        return f"milestone_{highest + 1}"

    # ============================================================
    # HELPERS
    # ============================================================

    @staticmethod
    def _safe_float(value: Any) -> float:
        """
        Safely convert a value to float.
        """

        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _clamp_importance(value: Any) -> float:
        """
        Keep importance between 0.0 and 1.0.
        """

        value = MilestoneManager._safe_float(value)

        return max(
            0.0,
            min(
                1.0,
                value,
            ),
        )