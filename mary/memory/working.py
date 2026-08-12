"""
MaryV2 Working Memory

Working memory contains information Mary is actively using right now.

Unlike episodic and semantic memory, working memory is temporary.
It represents the active mental workspace used during a conversation,
reasoning cycle, task, or autonomous process.

Examples:
    - Current user message
    - Current conversation topic
    - Active task
    - Relevant retrieved memories
    - Current reasoning state
    - Temporary variables/context

Working memory should not automatically become permanent memory.
The consolidation system decides what is worth retaining.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional


class WorkingMemory:
    """
    Temporary active memory for the current cognitive process.
    """

    def __init__(
        self,
        capacity: int = 50,
    ) -> None:

        if capacity <= 0:
            raise ValueError(
                "Working memory capacity must be greater than zero."
            )

        self.capacity = capacity
        self.items: list[dict[str, Any]] = []

    # ============================================================
    # ADD
    # ============================================================

    def add(
        self,
        content: Any,
        *,
        category: str = "general",
        importance: float = 0.5,
        source: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Add an item to working memory.

        Working memory has a finite capacity. When capacity is
        exceeded, the least important item is removed.
        """

        now = datetime.now().isoformat()

        item = {
            "id": self._next_id(),
            "content": content,
            "category": str(category),
            "importance": self._clamp_importance(
                importance
            ),
            "source": source,
            "created_at": now,
            "updated_at": now,
        }

        self.items.append(item)

        self._enforce_capacity()

        return item

    # ============================================================
    # GET
    # ============================================================

    def get(
        self,
        item_id: str,
    ) -> Optional[dict[str, Any]]:
        """Return one working-memory item by ID."""

        for item in self.items:

            if item.get("id") == item_id:
                return item

        return None

    # ============================================================
    # FIND
    # ============================================================

    def find(
        self,
        *,
        category: Optional[str] = None,
        source: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """
        Find working-memory items by category or source.
        """

        results: list[dict[str, Any]] = []

        for item in self.items:

            if category is not None:
                if item.get("category") != category:
                    continue

            if source is not None:
                if item.get("source") != source:
                    continue

            results.append(item)

        return results

    # ============================================================
    # UPDATE
    # ============================================================

    def update(
        self,
        item_id: str,
        **changes: Any,
    ) -> Optional[dict[str, Any]]:
        """Update an existing working-memory item."""

        item = self.get(item_id)

        if item is None:
            return None

        allowed_fields = {
            "content",
            "category",
            "importance",
            "source",
        }

        for key, value in changes.items():

            if key not in allowed_fields:
                continue

            if key == "importance":
                value = self._clamp_importance(
                    value
                )

            item[key] = value

        item["updated_at"] = datetime.now().isoformat()

        return item

    # ============================================================
    # REMOVE
    # ============================================================

    def remove(
        self,
        item_id: str,
    ) -> bool:
        """Remove one item from working memory."""

        for index, item in enumerate(self.items):

            if item.get("id") == item_id:

                del self.items[index]

                return True

        return False

    # ============================================================
    # RECENT
    # ============================================================

    def recent(
        self,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Return the most recently added working-memory items.
        """

        if limit <= 0:
            return []

        return self.items[-limit:]

    # ============================================================
    # IMPORTANT
    # ============================================================

    def important(
        self,
        threshold: float = 0.7,
    ) -> list[dict[str, Any]]:
        """
        Return items whose importance meets the threshold.
        """

        threshold = self._clamp_importance(
            threshold
        )

        return [
            item
            for item in self.items
            if item.get(
                "importance",
                0.0
            ) >= threshold
        ]

    # ============================================================
    # ALL
    # ============================================================

    def all(self) -> list[dict[str, Any]]:
        """Return all current working-memory items."""

        return list(self.items)

    # ============================================================
    # COUNT
    # ============================================================

    def count(self) -> int:
        """Return the number of active working-memory items."""

        return len(self.items)

    # ============================================================
    # CLEAR
    # ============================================================

    def clear(self) -> None:
        """
        Clear working memory.

        This is useful when starting a new cognitive session,
        resetting Mary, or intentionally ending a task.
        """

        self.items.clear()

    # ============================================================
    # CAPACITY
    # ============================================================

    def _enforce_capacity(self) -> None:
        """
        Keep working memory within its configured capacity.

        The least important item is discarded first.
        """

        while len(self.items) > self.capacity:

            least_important = min(
                self.items,
                key=lambda item: (
                    item.get(
                        "importance",
                        0.0
                    ),
                    item.get(
                        "created_at",
                        ""
                    ),
                ),
            )

            self.items.remove(
                least_important
            )

    # ============================================================
    # ID
    # ============================================================

    def _next_id(self) -> str:
        """Generate the next working-memory ID."""

        highest = 0

        for item in self.items:

            item_id = str(
                item.get("id", "")
            )

            if not item_id.startswith(
                "working_"
            ):
                continue

            try:
                number = int(
                    item_id.split("_")[-1]
                )

                highest = max(
                    highest,
                    number
                )

            except ValueError:
                continue

        return f"working_{highest + 1}"

    # ============================================================
    # VALIDATION
    # ============================================================

    @staticmethod
    def _clamp_importance(
        value: float,
    ) -> float:
        """Keep importance between 0.0 and 1.0."""

        try:
            value = float(value)

        except (TypeError, ValueError):
            value = 0.5

        return max(
            0.0,
            min(
                1.0,
                value
            )
        )