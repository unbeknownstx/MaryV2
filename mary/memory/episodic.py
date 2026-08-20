"""MaryV2 episodic memory with bounded long-term retention."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
import re
import uuid

from mary.governance.bounds import bounded_payload, clip_text, enforce_capacity


@dataclass
class EpisodicMemory:
    """Represents a single experience or event in Mary's life."""

    id: str
    content: str
    timestamp: datetime
    importance: float = 0.5
    source: str = "interaction"
    event_type: str = "general"
    participants: list[str] = field(default_factory=list)
    emotional_context: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EpisodicMemory":
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp)
            except ValueError:
                timestamp = datetime.now(timezone.utc)
        elif not isinstance(timestamp, datetime):
            timestamp = datetime.now(timezone.utc)

        try:
            importance = float(data.get("importance", 0.5))
        except (TypeError, ValueError):
            importance = 0.5

        return cls(
            id=str(data.get("id", uuid.uuid4().hex)),
            content=str(data.get("content", "")),
            timestamp=timestamp,
            importance=max(0.0, min(1.0, importance)),
            source=str(data.get("source", "interaction")),
            event_type=str(data.get("event_type", "general")),
            participants=list(data.get("participants", [])),
            emotional_context=dict(data.get("emotional_context", {})),
            metadata=dict(data.get("metadata", {})),
        )


class EpisodicMemoryStore:
    """Bounded in-memory collection of episodic memories.

    Capacity is a long-term safety ceiling, not a recall window. When the store
    reaches capacity, retention favors importance and recency. This gives Mary
    continuity without allowing an append-only diary to grow forever.
    """

    def __init__(self, *, capacity: int = 4096, content_limit: int = 4000) -> None:
        self.capacity = max(1, int(capacity))
        self.content_limit = max(128, int(content_limit))
        self._memories: list[EpisodicMemory] = []
        self.evicted_count = 0

    def _retention_score(self, memory: EpisodicMemory) -> tuple[float, datetime]:
        return (float(memory.importance), memory.timestamp)

    def _compact(self) -> int:
        before = len(self._memories)
        enforce_capacity(
            self._memories,
            self.capacity,
            keep_score=self._retention_score,
        )
        removed = max(0, before - len(self._memories))
        self.evicted_count += removed
        return removed

    def add(self, memory: EpisodicMemory) -> EpisodicMemory:
        memory.content = clip_text(memory.content, self.content_limit)
        memory.source = clip_text(memory.source, 256)
        memory.event_type = clip_text(memory.event_type, 256)
        memory.participants = [clip_text(item, 256) for item in memory.participants[:32]]
        memory.emotional_context = bounded_payload(memory.emotional_context, text_limit=1000, item_limit=32, depth_limit=3)
        memory.metadata = bounded_payload(memory.metadata, text_limit=2000, item_limit=64, depth_limit=4)
        self._memories.append(memory)
        self._compact()
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
        memory = EpisodicMemory(
            id=f"episode_{uuid.uuid4().hex}",
            content=clip_text(str(content).strip(), self.content_limit),
            timestamp=datetime.now(timezone.utc),
            importance=max(0.0, min(1.0, float(importance))),
            source=source,
            event_type=event_type,
            participants=list(participants) if participants else [],
            emotional_context=dict(emotional_context) if emotional_context else {},
            metadata=dict(metadata) if metadata else {},
        )
        return self.add(memory)

    def get(self, memory_id: str) -> EpisodicMemory | None:
        for memory in self._memories:
            if memory.id == memory_id:
                return memory
        return None

    def all(self) -> list[EpisodicMemory]:
        return list(self._memories)

    def search(self, query: str, limit: int = 5) -> list[EpisodicMemory]:
        if not query or not str(query).strip() or limit <= 0:
            return []
        query_terms = set(re.findall(r"\b[\w']+\b", str(query).lower()))
        if not query_terms:
            return []

        matches: list[tuple[int, EpisodicMemory]] = []
        for memory in self._memories:
            content_terms = set(re.findall(r"\b[\w']+\b", memory.content.lower()))
            matched_terms = len(query_terms.intersection(content_terms))
            if matched_terms > 0:
                matches.append((matched_terms, memory))
        matches.sort(
            key=lambda item: (item[0], item[1].importance, item[1].timestamp),
            reverse=True,
        )
        return [memory for _, memory in matches[:limit]]

    def count(self) -> int:
        return len(self._memories)

    def remove(self, memory_id: str) -> bool:
        for index, memory in enumerate(self._memories):
            if memory.id == memory_id:
                del self._memories[index]
                return True
        return False

    def clear(self) -> None:
        self._memories.clear()

    def export(self) -> list[dict[str, Any]]:
        return [memory.to_dict() for memory in self._memories]

    def import_data(self, data: list[dict[str, Any]]) -> None:
        self._memories.clear()
        for item in data:
            if not isinstance(item, dict):
                continue
            memory = EpisodicMemory.from_dict(item)
            self.add(memory)
        self._compact()

    def status(self) -> dict[str, int]:
        return {
            "count": self.count(),
            "capacity": self.capacity,
            "evicted": self.evicted_count,
            "content_limit": self.content_limit,
        }
