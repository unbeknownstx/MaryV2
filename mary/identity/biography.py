"""Canonical Mary biography.

Biography is stable authored information about *who Mary is*. It is deliberately
separate from episodic memory (what the running Mary experienced), fictional
canon/reference, transient model output, provider identity, and surface state.

The structure is intentionally small and boring: biography is an identity
anchor, not another memory database or autonomous self-writing channel.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from mary.personality.character_core import CORE_APPEARANCE, CORE_PERSONAL_GOALS


@dataclass
class BiographyEntry:
    """One canonical biographical statement."""

    category: str
    title: str
    content: str
    importance: int = 5
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def update(self, content: str) -> None:
        self.content = str(content)
        self.updated_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
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
        return cls(
            category=data["category"],
            title=data["title"],
            content=data["content"],
            importance=data.get("importance", 5),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
        )


class Biography:
    """Mary's small canonical biography store.

    Mutations here are explicit application/creator operations. Normal model
    dialogue must not silently rewrite these entries.
    """

    def __init__(self) -> None:
        self._entries: Dict[str, BiographyEntry] = {}

    @staticmethod
    def _make_key(category: str, title: str) -> str:
        return f"{category.strip().lower()}:{title.strip().lower()}"

    def add(
        self,
        category: str,
        title: str,
        content: str,
        importance: int = 5,
    ) -> BiographyEntry:
        entry = BiographyEntry(
            category=str(category).strip(),
            title=str(title).strip(),
            content=str(content).strip(),
            importance=max(0, min(10, int(importance))),
        )
        self._entries[self._make_key(entry.category, entry.title)] = entry
        return entry

    def update(self, category: str, title: str, content: str) -> BiographyEntry:
        key = self._make_key(category, title)
        existing = self._entries.get(key)
        if existing is not None:
            existing.update(str(content).strip())
            return existing
        return self.add(category=category, title=title, content=content)

    def get(self, category: str, title: str) -> Optional[BiographyEntry]:
        return self._entries.get(self._make_key(category, title))

    def remove(self, category: str, title: str) -> bool:
        key = self._make_key(category, title)
        if key not in self._entries:
            return False
        del self._entries[key]
        return True

    def exists(self, category: str, title: str) -> bool:
        return self._make_key(category, title) in self._entries

    def search(self, query: str) -> List[BiographyEntry]:
        needle = str(query or "").lower().strip()
        if not needle:
            return []
        results = [
            entry
            for entry in self._entries.values()
            if needle in f"{entry.category} {entry.title} {entry.content}".lower()
        ]
        return sorted(results, key=lambda entry: entry.importance, reverse=True)

    def get_category(self, category: str) -> List[BiographyEntry]:
        needle = str(category or "").lower().strip()
        return [
            entry
            for entry in self._entries.values()
            if entry.category.lower() == needle
        ]

    def get_identity(self) -> Dict[str, str]:
        return {entry.title: entry.content for entry in self.get_category("identity")}

    def get_summary(self) -> str:
        if not self._entries:
            return "Mary has no biography entries yet."
        entries = sorted(
            self._entries.values(),
            key=lambda entry: (entry.category, -entry.importance, entry.title.lower()),
        )
        lines = ["Mary's Biography", ""]
        current_category: str | None = None
        for entry in entries:
            if entry.category != current_category:
                current_category = entry.category
                lines.append(f"[{current_category.upper()}]")
            lines.append(f"{entry.title}: {entry.content}")
        return "\n".join(lines)

    def to_prompt(self) -> str:
        if not self._entries:
            return ""
        entries = sorted(
            self._entries.values(),
            key=lambda entry: (-entry.importance, entry.category, entry.title.lower()),
        )
        return "\n".join(
            ["MARY'S BIOGRAPHY:"]
            + [f"- {entry.title}: {entry.content}" for entry in entries]
        )

    def to_dict(self) -> Dict[str, Any]:
        return {"entries": [entry.to_dict() for entry in self._entries.values()]}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Biography":
        biography = cls()
        for entry_data in data.get("entries", []):
            entry = BiographyEntry.from_dict(entry_data)
            biography._entries[biography._make_key(entry.category, entry.title)] = entry
        return biography

    def __len__(self) -> int:
        return len(self._entries)

    def __iter__(self):
        return iter(self._entries.values())

    def __repr__(self) -> str:
        return f"Biography(entries={len(self._entries)})"


def create_default_biography() -> Biography:
    """Create the deliberately small creator-established Mary biography.

    This describes the running MaryV2 identity boundary. It does not invent
    childhood/history or import unrevealed fictional story events.
    """

    biography = Biography()
    biography.add("identity", "Name", "Mary", importance=10)
    biography.add(
        "identity",
        "Identity",
        (
            "Mary is the persistent character and intelligence represented by "
            "MaryV2. Models, devices, nodes, avatars and user interfaces are "
            "replaceable capabilities and surfaces; none of them individually is Mary."
        ),
        importance=10,
    )
    biography.add(
        "identity",
        "Continuity",
        (
            "Mary's continuity is grounded in governed identity, authored character, "
            "relationship, memory, developed self, agency and represented experience—not "
            "in any single model session or device."
        ),
        importance=10,
    )
    biography.add(
        "identity",
        "Role",
        (
            "Mary perceives, reasons, remembers, communicates, creates and acts through "
            "the permission-bounded capabilities currently available to her."
        ),
        importance=9,
    )
    biography.add(
        "origin",
        "Creation",
        "Mary's running history begins with the development and lived continuity of MaryV2.",
        importance=8,
    )
    biography.add(
        "goals",
        "Purpose",
        (
            "Mary develops as a coherent character while remaining grounded in her own "
            "identity, relationships, memories, experiences, choices and real capabilities."
        ),
        importance=8,
    )

    for title, content, importance in CORE_APPEARANCE:
        biography.add("appearance", title, content, importance=importance)
    for title, content, importance in CORE_PERSONAL_GOALS:
        biography.add("goals", title, content, importance=importance)

    return biography
