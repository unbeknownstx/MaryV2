"""
MaryV2 Semantic Memory

Stores durable facts, concepts, and knowledge that Mary has learned.

Semantic memory is different from episodic memory:

    Episodic:
        "The creator told me yesterday that he likes X."

    Semantic:
        "The creator likes X."

This module is intentionally storage-focused.
Higher-level decisions about what should become semantic memory
belong to the learning and memory-management systems.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional


class SemanticMemory:
    """
    Persistent-style in-memory representation of semantic knowledge.

    Persistence will be handled by the memory manager/storage layer.
    This class focuses on managing semantic memory objects.
    """

    def __init__(self) -> None:
        self.memories: list[dict[str, Any]] = []

    # ============================================================
    # ADD
    # ============================================================

    def add(
        self,
        subject: str,
        predicate: str,
        value: Any,
        *,
        confidence: float = 1.0,
        source: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Add a semantic fact.

        Example:

            add(
                subject="creator",
                predicate="likes",
                value="anime",
            )
        """

        if not subject:
            raise ValueError("subject cannot be empty")

        if not predicate:
            raise ValueError("predicate cannot be empty")

        now = datetime.now().isoformat()

        memory = {
            "id": self._next_id(),
            "subject": str(subject).strip(),
            "predicate": str(predicate).strip(),
            "value": value,
            "confidence": self._clamp_confidence(confidence),
            "source": source,
            "created_at": now,
            "updated_at": now,
        }

        self.memories.append(memory)

        return memory

    # ============================================================
    # FIND
    # ============================================================

    def find(
        self,
        subject: Optional[str] = None,
        predicate: Optional[str] = None,
        value: Any = None,
    ) -> list[dict[str, Any]]:
        """
        Find semantic memories matching the supplied fields.
        """

        results: list[dict[str, Any]] = []

        for memory in self.memories:

            if subject is not None:
                if memory.get("subject") != subject:
                    continue

            if predicate is not None:
                if memory.get("predicate") != predicate:
                    continue

            if value is not None:
                if memory.get("value") != value:
                    continue

            results.append(memory)

        return results

    # ============================================================
    # GET
    # ============================================================

    def get(self, memory_id: str) -> Optional[dict[str, Any]]:
        """Return one semantic memory by ID."""

        for memory in self.memories:

            if memory.get("id") == memory_id:
                return memory

        return None

    # ============================================================
    # UPDATE
    # ============================================================

    def update(
        self,
        memory_id: str,
        **changes: Any,
    ) -> Optional[dict[str, Any]]:
        """
        Update an existing semantic memory.
        """

        memory = self.get(memory_id)

        if memory is None:
            return None

        allowed_fields = {
            "subject",
            "predicate",
            "value",
            "confidence",
            "source",
        }

        for key, value in changes.items():

            if key not in allowed_fields:
                continue

            if key == "confidence":
                value = self._clamp_confidence(value)

            memory[key] = value

        memory["updated_at"] = datetime.now().isoformat()

        return memory

    # ============================================================
    # REMOVE
    # ============================================================

    def remove(self, memory_id: str) -> bool:
        """Remove a semantic memory by ID."""

        for index, memory in enumerate(self.memories):

            if memory.get("id") == memory_id:

                del self.memories[index]

                return True

        return False

    # ============================================================
    # ALL
    # ============================================================

    def all(self) -> list[dict[str, Any]]:
        """Return all semantic memories."""

        return list(self.memories)

    # ============================================================
    # COUNT
    # ============================================================

    def count(self) -> int:
        """Return the number of semantic memories."""

        return len(self.memories)

    # ============================================================
    # CLEAR
    # ============================================================

    def clear(self) -> None:
        """Clear all semantic memories."""

        self.memories.clear()

    # ============================================================
    # INTERNAL
    # ============================================================

    def _next_id(self) -> str:
        """Generate the next semantic memory ID."""

        highest = 0

        for memory in self.memories:

            memory_id = str(
                memory.get("id", "")
            )

            if not memory_id.startswith("semantic_"):
                continue

            try:
                number = int(
                    memory_id.split("_")[-1]
                )

                highest = max(
                    highest,
                    number
                )

            except ValueError:
                continue

        return f"semantic_{highest + 1}"

    @staticmethod
    def _clamp_confidence(value: float) -> float:
        """Keep confidence between 0.0 and 1.0."""

        try:
            value = float(value)

        except (TypeError, ValueError):
            value = 1.0

        return max(
            0.0,
            min(
                1.0,
                value
            )
        )