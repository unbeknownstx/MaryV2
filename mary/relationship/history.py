"""
MaryV2 - Relationship History

Tracks the history of Mary's relationship with her creator.

This is different from conversation history and episodic memory.

Conversation history:
    What was said.

Episodic memory:
    What happened and what was important about it.

Relationship history:
    How the relationship itself develops over time.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid


class RelationshipHistory:
    """Persistent-style in-memory representation of relationship events."""

    def __init__(
        self,
        creator_id: str = "creator",
    ):
        self.creator_id = creator_id
        self.events: List[Dict[str, Any]] = []
        self.created_at = datetime.now().isoformat()
        self.updated_at = self.created_at

    def record(
        self,
        event_type: str,
        description: str,
        *,
        importance: float = 0.5,
        source: str = "conversation",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not event_type:
            raise ValueError("event_type cannot be empty.")
        if not description:
            raise ValueError("description cannot be empty.")

        event = {
            "id": self._new_id(),
            "creator_id": self.creator_id,
            "type": str(event_type),
            "description": str(description).strip(),
            "importance": self._clamp(importance),
            "source": str(source),
            "metadata": dict(metadata or {}),
            "created_at": datetime.now().isoformat(),
        }
        self.events.append(event)
        self._touch()
        return event

    def record_interaction(
        self,
        description: str,
        *,
        importance: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return self.record(
            "interaction",
            description,
            importance=importance,
            source="conversation",
            metadata=metadata,
        )

    def record_first(
        self,
        description: str,
        *,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return self.record(
            "first",
            description,
            importance=0.9,
            source="relationship",
            metadata=metadata,
        )

    def record_milestone(
        self,
        description: str,
        *,
        importance: float = 0.9,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return self.record(
            "milestone",
            description,
            importance=importance,
            source="relationship",
            metadata=metadata,
        )

    def record_creator_preference(
        self,
        description: str,
        *,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return self.record(
            "preference_discovered",
            description,
            importance=0.7,
            source="understanding",
            metadata=metadata,
        )

    def record_creator_fact(
        self,
        description: str,
        *,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return self.record(
            "fact_discovered",
            description,
            importance=0.7,
            source="understanding",
            metadata=metadata,
        )

    def record_shared_experience(
        self,
        description: str,
        *,
        importance: float = 0.8,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return self.record(
            "shared_experience",
            description,
            importance=importance,
            source="relationship",
            metadata=metadata,
        )

    def get_all(self) -> List[Dict[str, Any]]:
        return list(self.events)

    def get_recent(self, limit: int = 10) -> List[Dict[str, Any]]:
        if limit <= 0:
            return []
        return list(reversed(self.events[-limit:]))

    def get_by_type(self, event_type: str) -> List[Dict[str, Any]]:
        return [event for event in self.events if event.get("type") == event_type]

    def get_milestones(self) -> List[Dict[str, Any]]:
        return self.get_by_type("milestone")

    def get_shared_experiences(self) -> List[Dict[str, Any]]:
        return self.get_by_type("shared_experience")

    def get_important(self, minimum_importance: float = 0.7) -> List[Dict[str, Any]]:
        minimum_importance = self._clamp(minimum_importance)
        return [
            event
            for event in self.events
            if event.get("importance", 0.0) >= minimum_importance
        ]

    def search(self, query: str) -> List[Dict[str, Any]]:
        """Perform simple keyword retrieval across relationship history."""
        if not query:
            return []
        terms = {term.lower() for term in str(query).split() if term.strip()}
        results = []
        for event in self.events:
            searchable = " ".join(
                [
                    str(event.get("type", "")),
                    str(event.get("description", "")),
                    str(event.get("source", "")),
                ]
            ).lower()
            score = sum(1 for term in terms if term in searchable)
            if score > 0:
                results.append({"score": score, "event": event})
        results.sort(key=lambda item: item["score"], reverse=True)
        return results

    def count(self, event_type: Optional[str] = None) -> int:
        if event_type is None:
            return len(self.events)
        return len(self.get_by_type(event_type))

    def current_relationship_mode(self) -> str:
        """Derive the current explicit social mode from canonical history.

        This intentionally has no independent persistence. Older stores without
        mode events remain ordinary friend relationships until an explicit mode
        is recorded through the existing relationship owner.
        """
        for event in reversed(self.events):
            if event.get("type") != "relationship_mode_changed":
                continue
            mode = str((event.get("metadata") or {}).get("mode", "")).strip().lower()
            if mode in {"friend", "close", "romantic", "partner"}:
                return mode
        return "friend"

    def summary(self) -> Dict[str, Any]:
        """Return a compact model/dashboard-safe relationship-history summary."""
        return {
            "creator_id": self.creator_id,
            "total_events": len(self.events),
            "milestones": self.count("milestone"),
            "shared_experiences": self.count("shared_experience"),
            "preferences_discovered": self.count("preference_discovered"),
            "facts_discovered": self.count("fact_discovered"),
            "relationship_mode": self.current_relationship_mode(),
            "updated_at": self.updated_at,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "creator_id": self.creator_id,
            "events": list(self.events),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(
        cls,
        data: Optional[Dict[str, Any]],
    ) -> "RelationshipHistory":
        if not isinstance(data, dict):
            return cls()
        history = cls(creator_id=data.get("creator_id", "creator"))
        events = data.get("events", [])
        if isinstance(events, list):
            history.events = events
        history.created_at = data.get("created_at", history.created_at)
        history.updated_at = data.get("updated_at", history.updated_at)
        return history

    def _touch(self) -> None:
        self.updated_at = datetime.now().isoformat()

    @staticmethod
    def _clamp(value: float) -> float:
        try:
            value = float(value)
        except (TypeError, ValueError):
            value = 0.5
        return max(0.0, min(1.0, value))

    @staticmethod
    def _new_id() -> str:
        return "relationship_" f"{uuid.uuid4().hex[:12]}"
