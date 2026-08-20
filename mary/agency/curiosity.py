"""
MaryV2 - Curiosity System

Responsible for managing Mary's persistent curiosities.

A curiosity represents something Mary wants to understand,
investigate, explore, or learn more about.

Curiosity is intentionally different from:

    Goal
        Something Mary is actively trying to accomplish.

    Intention
        Something Mary intends to do.

    Curiosity
        Something Mary wants to understand or explore.

This module stores and manages curiosities. It does not perform
research itself. Research belongs to the learning/research systems.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mary.governance.bounds import bounded_payload, clip_text, enforce_capacity
from mary.runtime.persistence import atomic_write_json, cleanup_stale_temps, load_json_recovering


class CuriositySystem:
    """Persistent manager for Mary's curiosities."""

    VALID_STATUSES = {
        "open",
        "exploring",
        "resolved",
        "dismissed",
    }

    def __init__(
        self,
        path: str | Path = "data/goals/curiosities.json",
        capacity: int = 1024,
        content_limit: int = 2000,
        backup_generations: int = 3,
    ) -> None:
        self.path = Path(path)
        self.capacity = max(1, int(capacity))
        self.content_limit = max(128, int(content_limit))
        self.backup_generations = max(1, int(backup_generations))
        self.recovered_from_backup = False
        self.curiosities: list[dict[str, Any]] = []

    # ============================================================
    # LIFECYCLE
    # ============================================================

    def load(self) -> None:
        """Load state with finite-backup recovery."""
        cleanup_stale_temps(self.path)
        if not self.path.exists() and not any(
            self.path.with_name(f"{self.path.name}.bak{i}").exists()
            for i in range(1, self.backup_generations + 1)
        ):
            self._ensure_directory()
            self.save()
            return
        payload, source = load_json_recovering(
            self.path, backup_generations=self.backup_generations
        )
        if isinstance(payload, dict):
            raw = payload.get("curiosities", [])
        elif isinstance(payload, list):
            raw = payload
        else:
            raw = []
        self.curiosities = [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []
        self._compact()
        self.recovered_from_backup = bool(source is not None and source != self.path)

    def save(self) -> None:
        """Persist bounded state atomically."""
        self._ensure_directory()
        self._compact()
        atomic_write_json(
            self.path,
            {"curiosities": self.curiosities},
            backup_generations=self.backup_generations,
            indent=2,
        )

    def _compact(self) -> int:
        before = len(self.curiosities)
        for item in self.curiosities:
            if isinstance(item, dict):
                if isinstance(item.get("description"), str):
                    item["description"] = clip_text(item["description"], self.content_limit)
                item["metadata"] = bounded_payload(item.get("metadata", {}), text_limit=self.content_limit)
        enforce_capacity(
            self.curiosities,
            self.capacity,
            keep_score=lambda item: (
                1.0 if str(item.get("status", "")) in {'exploring', 'open'} else 0.0,
                float(item.get("importance", item.get("priority", 0.0)) or 0.0),
                str(item.get("updated_at", item.get("created_at", ""))),
            ),
        )
        return max(0, before - len(self.curiosities))

    def _ensure_directory(self) -> None:
        """Create the storage directory if necessary."""

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    # ============================================================
    # CREATE
    # ============================================================

    def add_curiosity(
        self,
        description: str,
        importance: float = 0.5,
        source: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """
        Create and persist a new curiosity.

        source may identify where the curiosity came from, such as:

            user
            conversation
            observation
            research
            reflection
            autonomous
        """

        description = clip_text(str(
            description
        ).strip(), self.content_limit)

        if not description:
            return None

        importance = self._clamp_score(
            importance
        )

        now = self._timestamp()

        curiosity = {
            "id": self._next_id(),
            "description": description,
            "importance": importance,
            "source": source,
            "status": "open",
            "created_at": now,
            "updated_at": now,
            "resolved_at": None,
            "metadata": bounded_payload(metadata or {}, text_limit=self.content_limit),
        }

        self.curiosities.append(
            curiosity
        )

        self.save()

        return curiosity

    def create_curiosity(
        self,
        description: str,
        importance: float = 0.5,
        source: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Compatibility alias for add_curiosity()."""

        return self.add_curiosity(
            description,
            importance,
            source,
            metadata,
        )

    # ============================================================
    # READ
    # ============================================================

    def get_curiosities(
        self,
    ) -> list[dict[str, Any]]:
        """Return all curiosities."""

        return list(
            self.curiosities
        )

    def get_curiosity(
        self,
        curiosity_id: str,
    ) -> dict[str, Any] | None:
        """Find a curiosity by ID."""

        for curiosity in self.curiosities:
            if curiosity.get("id") == curiosity_id:
                return curiosity

        return None

    def get_open_curiosities(
        self,
    ) -> list[dict[str, Any]]:
        """Return unresolved curiosities."""

        return self._get_by_status(
            "open"
        )

    def get_exploring_curiosities(
        self,
    ) -> list[dict[str, Any]]:
        """Return curiosities currently being explored."""

        return self._get_by_status(
            "exploring"
        )

    def get_resolved_curiosities(
        self,
    ) -> list[dict[str, Any]]:
        """Return curiosities that have been resolved."""

        return self._get_by_status(
            "resolved"
        )

    def get_dismissed_curiosities(
        self,
    ) -> list[dict[str, Any]]:
        """Return curiosities that were dismissed."""

        return self._get_by_status(
            "dismissed"
        )

    def _get_by_status(
        self,
        status: str,
    ) -> list[dict[str, Any]]:
        return [
            curiosity
            for curiosity in self.curiosities
            if curiosity.get("status") == status
        ]

    # ============================================================
    # UPDATE
    # ============================================================

    def update_curiosity(
        self,
        curiosity_id: str,
        *,
        description: str | None = None,
        importance: float | None = None,
        source: str | None = None,
    ) -> bool:
        """Update an existing curiosity."""

        curiosity = self.get_curiosity(
            curiosity_id
        )

        if curiosity is None:
            return False

        if description is not None:
            description = str(
                description
            ).strip()

            if description:
                curiosity["description"] = description

        if importance is not None:
            curiosity["importance"] = (
                self._clamp_score(
                    importance
                )
            )

        if source is not None:
            curiosity["source"] = source

        curiosity["updated_at"] = (
            self._timestamp()
        )

        self.save()

        return True

    # ============================================================
    # STATE TRANSITIONS
    # ============================================================

    def begin_exploration(
        self,
        curiosity_id: str,
    ) -> bool:
        """Mark a curiosity as currently being explored."""

        return self._set_status(
            curiosity_id,
            "exploring",
        )

    def resolve_curiosity(
        self,
        curiosity_id: str,
    ) -> bool:
        """Mark a curiosity as resolved."""

        curiosity = self.get_curiosity(
            curiosity_id
        )

        if curiosity is None:
            return False

        now = self._timestamp()

        curiosity["status"] = "resolved"
        curiosity["updated_at"] = now
        curiosity["resolved_at"] = now

        self.save()

        return True

    def dismiss_curiosity(
        self,
        curiosity_id: str,
    ) -> bool:
        """Dismiss a curiosity without resolving it."""

        return self._set_status(
            curiosity_id,
            "dismissed",
        )

    def reopen_curiosity(
        self,
        curiosity_id: str,
    ) -> bool:
        """Return a resolved or dismissed curiosity to open."""

        curiosity = self.get_curiosity(
            curiosity_id
        )

        if curiosity is None:
            return False

        curiosity["status"] = "open"
        curiosity["updated_at"] = (
            self._timestamp()
        )
        curiosity["resolved_at"] = None

        self.save()

        return True

    def _set_status(
        self,
        curiosity_id: str,
        status: str,
    ) -> bool:
        if status not in self.VALID_STATUSES:
            return False

        curiosity = self.get_curiosity(
            curiosity_id
        )

        if curiosity is None:
            return False

        curiosity["status"] = status
        curiosity["updated_at"] = (
            self._timestamp()
        )

        if status != "resolved":
            curiosity["resolved_at"] = None

        self.save()

        return True

    # ============================================================
    # PRIORITY SUPPORT
    # ============================================================

    def get_highest_importance(
        self,
    ) -> dict[str, Any] | None:
        """
        Return the most important unresolved curiosity.

        This is only a convenience query. The dedicated priority
        system will eventually combine curiosity with goals,
        intentions, relationship needs, and other factors.
        """

        candidates = [
            curiosity
            for curiosity in self.curiosities
            if curiosity.get("status") in {
                "open",
                "exploring",
            }
        ]

        if not candidates:
            return None

        return max(
            candidates,
            key=lambda curiosity: float(
                curiosity.get(
                    "importance",
                    0.0,
                )
            ),
        )

    # ============================================================
    # SEARCH
    # ============================================================

    def search(
        self,
        query: str,
    ) -> list[dict[str, Any]]:
        """
        Perform a simple local text search.

        This is deliberately lightweight.

        Semantic/vector retrieval belongs to the knowledge and
        memory systems rather than this agency component.
        """

        query = str(
            query
        ).strip().lower()

        if not query:
            return []

        return [
            curiosity
            for curiosity in self.curiosities
            if query in str(
                curiosity.get(
                    "description",
                    "",
                )
            ).lower()
        ]

    # ============================================================
    # DELETE
    # ============================================================

    def remove_curiosity(
        self,
        curiosity_id: str,
    ) -> bool:
        """Remove a curiosity from persistent storage."""

        curiosity = self.get_curiosity(
            curiosity_id
        )

        if curiosity is None:
            return False

        self.curiosities.remove(
            curiosity
        )

        self.save()

        return True

    # ============================================================
    # UTILITIES
    # ============================================================

    def count_open(self) -> int:
        """Return the number of unresolved open curiosities."""

        return len(
            self.get_open_curiosities()
        )

    def count_exploring(self) -> int:
        """Return the number of curiosities being explored."""

        return len(
            self.get_exploring_curiosities()
        )

    def count_unresolved(self) -> int:
        """Return all curiosities that are not resolved."""

        return len([
            curiosity
            for curiosity in self.curiosities
            if curiosity.get("status") in {
                "open",
                "exploring",
            }
        ])

    # ============================================================
    # INTERNAL HELPERS
    # ============================================================

    def _next_id(self) -> str:
        """Generate the next persistent curiosity ID."""

        highest = 0

        for curiosity in self.curiosities:
            curiosity_id = str(
                curiosity.get(
                    "id",
                    "",
                )
            )

            if not curiosity_id.startswith(
                "curiosity_"
            ):
                continue

            try:
                number = int(
                    curiosity_id.split(
                        "_"
                    )[-1]
                )
            except ValueError:
                continue

            highest = max(
                highest,
                number,
            )

        return f"curiosity_{highest + 1}"

    @staticmethod
    def _timestamp() -> str:
        """Return a timezone-aware UTC timestamp."""

        return datetime.now(
            timezone.utc
        ).isoformat()

    @staticmethod
    def _clamp_score(
        score: float,
    ) -> float:
        """Keep a score within the 0.0-1.0 range."""

        try:
            value = float(score)
        except (
            TypeError,
            ValueError,
        ):
            value = 0.5

        return max(
            0.0,
            min(
                1.0,
                value,
            ),
        )