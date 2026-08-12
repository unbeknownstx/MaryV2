"""
MaryV2 - Character Canon

Stores the fictional canon from which Mary's character originated.

Canon describes the established fictional version of Mary.
It is intentionally separate from Mary's current identity,
personality, memories, experiences, and development.

Canon is source material, not current lived experience.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Canon:
    """
    Represents the established fictional canon surrounding Mary.
    """

    source: str = "Unspecified"

    character_name: str = "Mary"

    fictional_age: Optional[int] = 21

    description: str = ""

    history: List[str] = field(
        default_factory=list
    )

    relationships: Dict[str, str] = field(
        default_factory=dict
    )

    mannerisms: List[str] = field(
        default_factory=list
    )

    personality_notes: List[str] = field(
        default_factory=list
    )

    preferences: Dict[str, Any] = field(
        default_factory=dict
    )

    events: List[str] = field(
        default_factory=list
    )

    knowledge: List[str] = field(
        default_factory=list
    )

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    # ============================================================
    # ADD
    # ============================================================

    def add_history(self, item: str) -> None:
        """Add an established piece of fictional history."""

        item = str(item).strip()

        if item and item not in self.history:
            self.history.append(item)

    def add_mannerism(self, item: str) -> None:
        """Add an established character mannerism."""

        item = str(item).strip()

        if item and item not in self.mannerisms:
            self.mannerisms.append(item)

    def add_personality_note(self, item: str) -> None:
        """Add a canonical personality observation."""

        item = str(item).strip()

        if item and item not in self.personality_notes:
            self.personality_notes.append(item)

    def add_event(self, item: str) -> None:
        """Add a canonical fictional event."""

        item = str(item).strip()

        if item and item not in self.events:
            self.events.append(item)

    def add_knowledge(self, item: str) -> None:
        """Add knowledge established by the fiction."""

        item = str(item).strip()

        if item and item not in self.knowledge:
            self.knowledge.append(item)

    def set_relationship(
        self,
        person: str,
        relationship: str,
    ) -> None:
        """Register a canonical relationship."""

        person = str(person).strip()
        relationship = str(relationship).strip()

        if person and relationship:
            self.relationships[person] = relationship

    def set_preference(
        self,
        key: str,
        value: Any,
    ) -> None:
        """Register a canonical preference."""

        key = str(key).strip()

        if key:
            self.preferences[key] = value

    # ============================================================
    # ACCESS
    # ============================================================

    def has_event(self, event: str) -> bool:
        """Check whether an event exists in canon."""

        return event in self.events

    def has_mannerism(self, mannerism: str) -> bool:
        """Check whether a mannerism exists in canon."""

        return mannerism in self.mannerisms

    def get_relationship(
        self,
        person: str,
        default: Optional[str] = None,
    ) -> Optional[str]:
        """Return Mary's canonical relationship with someone."""

        return self.relationships.get(
            person,
            default,
        )

    # ============================================================
    # SUMMARY
    # ============================================================

    def summary(self) -> Dict[str, Any]:
        """
        Return a compact summary of Mary's fictional canon.
        """

        return {
            "source": self.source,
            "character_name": self.character_name,
            "fictional_age": self.fictional_age,
            "history_count": len(self.history),
            "relationship_count": len(self.relationships),
            "mannerism_count": len(self.mannerisms),
            "personality_note_count": len(
                self.personality_notes
            ),
            "event_count": len(self.events),
            "knowledge_count": len(self.knowledge),
        }

    # ============================================================
    # SERIALIZATION
    # ============================================================

    def to_dict(self) -> Dict[str, Any]:
        """Serialize canon state."""

        return {
            "source": self.source,
            "character_name": self.character_name,
            "fictional_age": self.fictional_age,
            "description": self.description,
            "history": list(self.history),
            "relationships": dict(self.relationships),
            "mannerisms": list(self.mannerisms),
            "personality_notes": list(
                self.personality_notes
            ),
            "preferences": dict(self.preferences),
            "events": list(self.events),
            "knowledge": list(self.knowledge),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(
        cls,
        data: Optional[Dict[str, Any]],
    ) -> "Canon":
        """Restore canon from serialized data."""

        if not isinstance(data, dict):
            return cls()

        return cls(
            source=data.get(
                "source",
                "Unspecified",
            ),
            character_name=data.get(
                "character_name",
                "Mary",
            ),
            fictional_age=data.get(
                "fictional_age",
                21,
            ),
            description=data.get(
                "description",
                "",
            ),
            history=list(
                data.get(
                    "history",
                    [],
                )
            ),
            relationships=dict(
                data.get(
                    "relationships",
                    {},
                )
            ),
            mannerisms=list(
                data.get(
                    "mannerisms",
                    [],
                )
            ),
            personality_notes=list(
                data.get(
                    "personality_notes",
                    [],
                )
            ),
            preferences=dict(
                data.get(
                    "preferences",
                    {},
                )
            ),
            events=list(
                data.get(
                    "events",
                    [],
                )
            ),
            knowledge=list(
                data.get(
                    "knowledge",
                    [],
                )
            ),
            metadata=dict(
                data.get(
                    "metadata",
                    {},
                )
            ),
        )