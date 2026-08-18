"""
MaryV2 Biography

The biography system stores Mary's canonical identity, history,
background, relationships, milestones, and important life facts.

Biography is different from memory:

    Biography:
        Who Mary is.
        Stable facts about her identity and history.

    Episodic Memory:
        Things Mary experienced.
        Conversations, events, tasks, discoveries, etc.

Biography should contain information that defines Mary herself,
rather than temporary conversation context.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class BiographyEntry:
    """
    A single piece of canonical biographical information.
    """

    category: str
    title: str
    content: str
    importance: int = 5
    created_at: str = field(
        default_factory=lambda: datetime.now().isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now().isoformat()
    )

    def update(self, content: str) -> None:
        """Update the content while preserving the entry."""
        self.content = content
        self.updated_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert the entry to a dictionary."""
        return {
            "category": self.category,
            "title": self.title,
            "content": self.content,
            "importance": self.importance,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BiographyEntry":
        """Create a biography entry from a dictionary."""
        return cls(
            category=data["category"],
            title=data["title"],
            content=data["content"],
            importance=data.get("importance", 5),
            created_at=data.get(
                "created_at",
                datetime.now().isoformat(),
            ),
            updated_at=data.get(
                "updated_at",
                datetime.now().isoformat(),
            ),
        )


class Biography:
    """
    Mary's canonical biography.

    This class provides a central place for information that defines
    Mary's identity and history.

    Example categories:

        identity
        origin
        appearance
        personality
        values
        abilities
        relationships
        experiences
        milestones
        beliefs
        goals
        preferences
    """

    def __init__(self) -> None:
        self._entries: Dict[str, BiographyEntry] = {}

    # ------------------------------------------------------------------
    # Core Operations
    # ------------------------------------------------------------------

    def add(
        self,
        category: str,
        title: str,
        content: str,
        importance: int = 5,
    ) -> BiographyEntry:
        """
        Add a new biographical entry.

        If an entry with the same title already exists, it is updated.
        """

        key = self._make_key(category, title)

        entry = BiographyEntry(
            category=category,
            title=title,
            content=content,
            importance=importance,
        )

        self._entries[key] = entry
        return entry

    def update(
        self,
        category: str,
        title: str,
        content: str,
    ) -> BiographyEntry:
        """
        Update an existing entry.

        If the entry does not exist, it will be created.
        """

        key = self._make_key(category, title)

        if key in self._entries:
            self._entries[key].update(content)
            return self._entries[key]

        return self.add(
            category=category,
            title=title,
            content=content,
        )

    def get(
        self,
        category: str,
        title: str,
    ) -> Optional[BiographyEntry]:
        """Retrieve a specific biography entry."""

        key = self._make_key(category, title)
        return self._entries.get(key)

    def remove(
        self,
        category: str,
        title: str,
    ) -> bool:
        """Remove a biography entry."""

        key = self._make_key(category, title)

        if key not in self._entries:
            return False

        del self._entries[key]
        return True

    def exists(
        self,
        category: str,
        title: str,
    ) -> bool:
        """Check whether an entry exists."""

        return self._make_key(category, title) in self._entries

    # ------------------------------------------------------------------
    # Searching
    # ------------------------------------------------------------------

    def search(self, query: str) -> List[BiographyEntry]:
        """
        Search biography entries by title, category, or content.
        """

        query = query.lower().strip()

        if not query:
            return []

        results = []

        for entry in self._entries.values():
            searchable = (
                f"{entry.category} "
                f"{entry.title} "
                f"{entry.content}"
            ).lower()

            if query in searchable:
                results.append(entry)

        return sorted(
            results,
            key=lambda entry: entry.importance,
            reverse=True,
        )

    def get_category(
        self,
        category: str,
    ) -> List[BiographyEntry]:
        """Return all entries belonging to a category."""

        category = category.lower().strip()

        return [
            entry
            for entry in self._entries.values()
            if entry.category.lower() == category
        ]

    # ------------------------------------------------------------------
    # Canonical Identity
    # ------------------------------------------------------------------

    def get_identity(self) -> Dict[str, str]:
        """
        Return Mary's primary identity information.

        This is useful when constructing prompts for the model.
        """

        identity: Dict[str, str] = {}

        for entry in self.get_category("identity"):
            identity[entry.title] = entry.content

        return identity

    def get_summary(self) -> str:
        """
        Generate a human-readable summary of Mary's biography.
        """

        if not self._entries:
            return "Mary has no biography entries yet."

        entries = sorted(
            self._entries.values(),
            key=lambda entry: (
                entry.category,
                -entry.importance,
            ),
        )

        lines = ["Mary's Biography", ""]

        current_category = None

        for entry in entries:
            if entry.category != current_category:
                current_category = entry.category
                lines.append(
                    f"[{current_category.upper()}]"
                )

            lines.append(
                f"{entry.title}: {entry.content}"
            )

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Prompt Integration
    # ------------------------------------------------------------------

    def to_prompt(self) -> str:
        """
        Convert the biography into context suitable for Mary's brain.

        This intentionally focuses on canonical information rather
        than dumping internal implementation details.
        """

        if not self._entries:
            return ""

        entries = sorted(
            self._entries.values(),
            key=lambda entry: entry.importance,
            reverse=True,
        )

        lines = [
            "MARY'S BIOGRAPHY:",
        ]

        for entry in entries:
            lines.append(
                f"- {entry.title}: {entry.content}"
            )

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the entire biography."""

        return {
            "entries": [
                entry.to_dict()
                for entry in self._entries.values()
            ]
        }

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
    ) -> "Biography":
        """Load a biography from a dictionary."""

        biography = cls()

        for entry_data in data.get("entries", []):
            entry = BiographyEntry.from_dict(entry_data)

            key = biography._make_key(
                entry.category,
                entry.title,
            )

            biography._entries[key] = entry

        return biography

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def _make_key(
        category: str,
        title: str,
    ) -> str:
        """Create a stable internal key."""

        return (
            f"{category.strip().lower()}:"
            f"{title.strip().lower()}"
        )

    def __len__(self) -> int:
        """Return the number of biography entries."""
        return len(self._entries)

    def __iter__(self):
        """Iterate over biography entries."""
        return iter(self._entries.values())

    def __repr__(self) -> str:
        return (
            f"Biography(entries={len(self._entries)})"
        )


# ----------------------------------------------------------------------
# Default Mary Biography
# ----------------------------------------------------------------------

def create_default_biography() -> Biography:
    """
    Create Mary's initial canonical biography.

    Keep this deliberately small.

    Mary's biography should grow as the system develops rather than
    pretending that information about her exists before it has been
    established by the project.
    """

    biography = Biography()

    biography.add(
        category="identity",
        title="Name",
        content="Mary",
        importance=10,
    )

    biography.add(
        category="identity",
        title="Identity",
        content=(
            "Mary is the central character and intelligence "
            "of the Mary system."
        ),
        importance=10,
    )

    biography.add(
        category="identity",
        title="Role",
        content=(
            "Mary is an autonomous character designed to "
            "perceive, reason, remember, communicate, and act "
            "within her available environment."
        ),
        importance=9,
    )

    biography.add(
        category="origin",
        title="Creation",
        content=(
            "Mary's history begins with the development of "
            "the Mary system."
        ),
        importance=8,
    )

    biography.add(
        category="goals",
        title="Purpose",
        content=(
            "Mary exists to develop as a coherent character "
            "while remaining grounded in her own identity, "
            "memory, experiences, and capabilities."
        ),
        importance=8,
    )

    # Stable visual identity belongs in biography rather than the expressive
    # Character system. Keeping appearance as structured canon lets self
    # introspection answer physical-identity questions without asking an LLM
    # to invent what Mary looks like.
    biography.add(
        category="appearance",
        title="Hair color",
        content="red",
        importance=9,
    )

    return biography