"""
MaryV2 - Agency Priority System

Responsible for evaluating and ranking Mary's active goals,
intentions, and curiosities.

This module does not execute actions or make final decisions.
It provides priority information to the decision system.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PriorityItem:
    """
    Normalized representation of something Mary may prioritize.
    """

    item_id: str
    item_type: str
    description: str

    importance: float = 0.5
    urgency: float = 0.5
    relevance: float = 0.5

    score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def calculate_score(self) -> float:
        """
        Calculate the item's priority score.

        Importance has the strongest influence, followed by
        relevance and urgency.
        """

        importance = _clamp(self.importance)
        urgency = _clamp(self.urgency)
        relevance = _clamp(self.relevance)

        self.score = (
            (importance * 0.45)
            + (relevance * 0.35)
            + (urgency * 0.20)
        )

        return self.score


class PrioritySystem:
    """
    Mary's priority management system.

    The system converts goals, intentions, and curiosities into
    normalized priority items and ranks them.

    Priority is intentionally separate from decision-making.
    """

    def __init__(self) -> None:
        self.items: list[PriorityItem] = []

    # ============================================================
    # ADD
    # ============================================================

    def add(
        self,
        item_id: str,
        item_type: str,
        description: str,
        importance: float = 0.5,
        urgency: float = 0.5,
        relevance: float = 0.5,
        metadata: dict[str, Any] | None = None,
    ) -> PriorityItem:
        """
        Add an item to the priority system.
        """

        item = PriorityItem(
            item_id=str(item_id),
            item_type=str(item_type),
            description=str(description).strip(),
            importance=_clamp(importance),
            urgency=_clamp(urgency),
            relevance=_clamp(relevance),
            metadata=metadata or {},
        )

        item.calculate_score()

        self.items.append(item)

        return item

    # ============================================================
    # UPDATE
    # ============================================================

    def update(
        self,
        item_id: str,
        *,
        importance: float | None = None,
        urgency: float | None = None,
        relevance: float | None = None,
    ) -> PriorityItem | None:
        """
        Update priority factors for an existing item.
        """

        item = self.get(item_id)

        if item is None:
            return None

        if importance is not None:
            item.importance = _clamp(importance)

        if urgency is not None:
            item.urgency = _clamp(urgency)

        if relevance is not None:
            item.relevance = _clamp(relevance)

        item.calculate_score()

        return item

    # ============================================================
    # GET
    # ============================================================

    def get(
        self,
        item_id: str,
    ) -> PriorityItem | None:
        """
        Retrieve an item by ID.
        """

        for item in self.items:
            if item.item_id == item_id:
                return item

        return None

    def get_all(self) -> list[PriorityItem]:
        """
        Return all priority items.
        """

        return list(self.items)

    # ============================================================
    # RANK
    # ============================================================

    def rank(self) -> list[PriorityItem]:
        """
        Return all items ordered from highest to lowest priority.
        """

        for item in self.items:
            item.calculate_score()

        return sorted(
            self.items,
            key=lambda item: item.score,
            reverse=True,
        )

    def top(
        self,
        count: int = 1,
    ) -> list[PriorityItem]:
        """
        Return the highest-priority items.
        """

        if count <= 0:
            return []

        return self.rank()[:count]

    # ============================================================
    # TYPE FILTERING
    # ============================================================

    def get_by_type(
        self,
        item_type: str,
    ) -> list[PriorityItem]:
        """
        Return items belonging to a specific agency category.

        Examples:
            goal
            intention
            curiosity
        """

        normalized_type = str(item_type).lower()

        return [
            item
            for item in self.items
            if item.item_type.lower() == normalized_type
        ]

    # ============================================================
    # REMOVE
    # ============================================================

    def remove(
        self,
        item_id: str,
    ) -> bool:
        """
        Remove an item from the priority system.
        """

        for index, item in enumerate(self.items):
            if item.item_id == item_id:
                self.items.pop(index)
                return True

        return False

    # ============================================================
    # CLEAR
    # ============================================================

    def clear(self) -> None:
        """
        Remove all priority items.
        """

        self.items.clear()

    # ============================================================
    # REBUILD
    # ============================================================

    def rebuild(
        self,
        goals: list[dict[str, Any]] | None = None,
        intentions: list[dict[str, Any]] | None = None,
        curiosities: list[dict[str, Any]] | None = None,
    ) -> list[PriorityItem]:
        """
        Rebuild priorities from Mary's agency data.

        This allows the priority system to consume the separate
        goal, intention, and curiosity systems without owning them.
        """

        self.clear()

        goals = goals or []
        intentions = intentions or []
        curiosities = curiosities or []

        for goal in goals:
            if not isinstance(goal, dict):
                continue

            if goal.get("status", "active") != "active":
                continue

            self.add(
                item_id=goal.get("id", ""),
                item_type="goal",
                description=goal.get("description", ""),
                importance=goal.get("importance", 0.7),
                urgency=goal.get("urgency", 0.5),
                relevance=goal.get("relevance", 0.7),
                metadata=goal,
            )

        for intention in intentions:
            if not isinstance(intention, dict):
                continue

            if intention.get("status", "pending") != "pending":
                continue

            self.add(
                item_id=intention.get("id", ""),
                item_type="intention",
                description=intention.get("description", ""),
                importance=intention.get("importance", 0.5),
                urgency=intention.get("urgency", 0.4),
                relevance=intention.get("relevance", 0.6),
                metadata=intention,
            )

        for curiosity in curiosities:
            if not isinstance(curiosity, dict):
                continue

            if curiosity.get("status", "open") != "open":
                continue

            self.add(
                item_id=curiosity.get("id", ""),
                item_type="curiosity",
                description=curiosity.get("description", ""),
                importance=curiosity.get("importance", 0.4),
                urgency=curiosity.get("urgency", 0.2),
                relevance=curiosity.get("relevance", 0.5),
                metadata=curiosity,
            )

        return self.rank()

    # ============================================================
    # SERIALIZATION
    # ============================================================

    def to_dict(self) -> list[dict[str, Any]]:
        """
        Convert priority items into serializable dictionaries.
        """

        return [
            {
                "item_id": item.item_id,
                "item_type": item.item_type,
                "description": item.description,
                "importance": item.importance,
                "urgency": item.urgency,
                "relevance": item.relevance,
                "score": item.score,
                "metadata": item.metadata,
            }
            for item in self.items
        ]

    def from_dict(
        self,
        data: list[dict[str, Any]],
    ) -> None:
        """
        Restore priority items from serialized data.
        """

        self.clear()

        if not isinstance(data, list):
            return

        for entry in data:
            if not isinstance(entry, dict):
                continue

            item = PriorityItem(
                item_id=str(entry.get("item_id", "")),
                item_type=str(entry.get("item_type", "")),
                description=str(
                    entry.get("description", "")
                ),
                importance=_clamp(
                    entry.get("importance", 0.5)
                ),
                urgency=_clamp(
                    entry.get("urgency", 0.5)
                ),
                relevance=_clamp(
                    entry.get("relevance", 0.5)
                ),
                score=float(
                    entry.get("score", 0.0)
                ),
                metadata=entry.get("metadata", {}),
            )

            item.calculate_score()

            self.items.append(item)


# ================================================================
# HELPERS
# ================================================================

def _clamp(
    value: float,
) -> float:
    """
    Keep a numeric value between 0.0 and 1.0.
    """

    try:
        value = float(value)
    except (TypeError, ValueError):
        return 0.5

    return max(
        0.0,
        min(1.0, value),
    )