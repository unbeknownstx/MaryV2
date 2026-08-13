"""
MaryV2 Episodic Memory

Episodic memory stores experiences and events that happened to Mary.

Examples:
    - A conversation with Unbe
    - A task Mary completed
    - Something Mary learned through an interaction
    - An important event
    - A meaningful milestone

This module is responsible for representing and storing episodic memories.

It does NOT handle:
    - semantic knowledge
    - working memory
    - memory consolidation
    - relationships
    - personality
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid


@dataclass
class EpisodicMemory:
    """
    Represents a single experience or event in Mary's life.
    """

    id: str

    content: str

    timestamp: datetime

    importance: float = 0.5

    source: str = "interaction"

    event_type: str = "general"

    participants: list[str] = field(
        default_factory=list
    )

    emotional_context: dict[str, Any] = field(
        default_factory=dict
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the memory into a JSON-compatible dictionary.
        """

        data = asdict(self)

        data["timestamp"] = self.timestamp.isoformat()

        return data

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> "EpisodicMemory":
        """
        Reconstruct an episodic memory from stored data.
        """

        timestamp = data.get(
            "timestamp"
        )

        if isinstance(timestamp, str):

            try:

                timestamp = datetime.fromisoformat(
                    timestamp
                )

            except ValueError:

                timestamp = datetime.now(
                    timezone.utc
                )

        elif not isinstance(
            timestamp,
            datetime,
        ):

            timestamp = datetime.now(
                timezone.utc
            )

        return cls(
            id=str(
                data.get(
                    "id",
                    uuid.uuid4().hex,
                )
            ),
            content=str(
                data.get(
                    "content",
                    "",
                )
            ),
            timestamp=timestamp,
            importance=float(
                data.get(
                    "importance",
                    0.5,
                )
            ),
            source=str(
                data.get(
                    "source",
                    "interaction",
                )
            ),
            event_type=str(
                data.get(
                    "event_type",
                    "general",
                )
            ),
            participants=list(
                data.get(
                    "participants",
                    [],
                )
            ),
            emotional_context=dict(
                data.get(
                    "emotional_context",
                    {},
                )
            ),
            metadata=dict(
                data.get(
                    "metadata",
                    {},
                )
            ),
        )


class EpisodicMemoryStore:
    """
    In-memory collection of episodic memories.

    Persistent storage will be handled by the memory manager rather than
    embedding filesystem/database behavior into this class.
    """

    def __init__(self) -> None:

        self._memories: list[EpisodicMemory] = []

    def add(
        self,
        memory: EpisodicMemory,
    ) -> EpisodicMemory:
        """
        Add an episodic memory.
        """

        self._memories.append(
            memory
        )

        return memory

    def create(
        self,
        content: str,
        *,
        importance: float = 0.5,
        source: str = "interaction",
        event_type: str = "general",
        participants: list[str] | None = None,
        emotional_context: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> EpisodicMemory:
        """
        Create and store a new episodic memory.
        """

        memory = EpisodicMemory(
            id=f"episode_{uuid.uuid4().hex}",
            content=str(
                content
            ).strip(),
            timestamp=datetime.now(
                timezone.utc
            ),
            importance=max(
                0.0,
                min(
                    1.0,
                    float(importance),
                ),
            ),
            source=source,
            event_type=event_type,
            participants=(
                list(participants)
                if participants
                else []
            ),
            emotional_context=(
                dict(emotional_context)
                if emotional_context
                else {}
            ),
            metadata=(
                dict(metadata)
                if metadata
                else {}
            ),
        )

        return self.add(
            memory
        )

    def get(
        self,
        memory_id: str,
    ) -> EpisodicMemory | None:
        """
        Retrieve an episodic memory by ID.
        """

        for memory in self._memories:

            if memory.id == memory_id:

                return memory

        return None

    def all(self) -> list[EpisodicMemory]:
        """
        Return all episodic memories.
        """

        return list(
            self._memories
        )

    def search(
        self,
        query: str,
        limit: int = 5,
    ) -> list[EpisodicMemory]:
        """
        Search episodic memories using simple lexical matching.
        """

        if not query or not str(query).strip():
            return []

        if limit <= 0:
            return []

        query_terms = {
            term.lower()
            for term in str(query).split()
            if term.strip()
        }

        if not query_terms:
            return []

        matches: list[tuple[int, EpisodicMemory]] = []

        for memory in self._memories:

            content = memory.content.lower()

            matched_terms = sum(
                1
                for term in query_terms
                if term in content
            )

            if matched_terms > 0:

                matches.append(
                    (
                        matched_terms,
                        memory,
                    )
                )

        matches.sort(
            key=lambda item: (
                item[0],
                item[1].importance,
                item[1].timestamp,
            ),
            reverse=True,
        )

        return [
            memory
            for _, memory in matches[:limit]
        ]

    def count(self) -> int:
        """
        Return the number of stored episodic memories.
        """

        return len(
            self._memories
        )

    def remove(
        self,
        memory_id: str,
    ) -> bool:
        """
        Remove an episodic memory by ID.
        """

        for index, memory in enumerate(
            self._memories
        ):

            if memory.id == memory_id:

                del self._memories[index]

                return True

        return False

    def clear(self) -> None:
        """
        Remove all episodic memories.
        """

        self._memories.clear()

    def export(self) -> list[dict[str, Any]]:
        """
        Export all memories as dictionaries.
        """

        return [
            memory.to_dict()
            for memory in self._memories
        ]

    def import_data(
        self,
        data: list[dict[str, Any]],
    ) -> None:
        """
        Import episodic memories from dictionaries.
        """

        self._memories.clear()

        for item in data:

            if not isinstance(
                item,
                dict,
            ):
                continue

            memory = EpisodicMemory.from_dict(
                item
            )

            self._memories.append(
                memory
            )