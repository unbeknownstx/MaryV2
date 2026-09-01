"""
MaryV2 - Intention System

Responsible for managing Mary's short-term intentions.

Goals describe what Mary is trying to accomplish over a longer
period of time.

Intentions describe things Mary intends to do next or in the
near future.

This module does not decide whether an intention is a good idea.
That belongs to the cognition and decision systems.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mary.governance.bounds import clip_text, enforce_capacity
from mary.runtime.persistence import atomic_write_json, cleanup_stale_temps, load_json_recovering


class IntentionSystem:
    """Manager for Mary's short-term intentions with optional persistence."""

    VALID_STATUSES = {
        "pending",
        "active",
        "completed",
        "cancelled",
    }

    def __init__(
        self,
        path: str | Path | None = None,
        capacity: int = 512,
        content_limit: int = 2000,
        backup_generations: int = 3,
    ) -> None:
        self.path = Path(path) if path is not None else None
        self.capacity = max(1, int(capacity))
        self.content_limit = max(128, int(content_limit))
        self.backup_generations = max(1, int(backup_generations))
        self.recovered_from_backup = False
        self.intentions: list[dict[str, Any]] = []

    # ============================================================
    # LIFECYCLE
    # ============================================================

    def load(self) -> None:
        """Load state with finite-backup recovery when persistence is configured."""
        if self.path is None:
            return

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
            raw = payload.get("intentions", [])
        elif isinstance(payload, list):
            raw = payload
        else:
            raw = []
        self.intentions = [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []
        self._compact()
        self.recovered_from_backup = bool(source is not None and source != self.path)

    def save(self) -> None:
        """Persist bounded state atomically when persistence is configured."""
        if self.path is None:
            self._compact()
            return

        self._ensure_directory()
        self._compact()
        atomic_write_json(
            self.path,
            {"intentions": self.intentions},
            backup_generations=self.backup_generations,
            indent=2,
        )

    def _compact(self) -> int:
        before = len(self.intentions)
        for item in self.intentions:
            if isinstance(item, dict) and isinstance(item.get("description"), str):
                item["description"] = clip_text(item["description"], self.content_limit)
        enforce_capacity(
            self.intentions,
            self.capacity,
            keep_score=lambda item: (
                1.0 if str(item.get("status", "")) in {'active', 'pending'} else 0.0,
                float(item.get("importance", item.get("priority", 0.0)) or 0.0),
                str(item.get("updated_at", item.get("created_at", ""))),
            ),
        )
        return max(0, before - len(self.intentions))

    def _ensure_directory(self) -> None:
        """Create the configured storage directory if necessary."""
        if self.path is None:
            return

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    # ============================================================
    # CREATE
    # ============================================================

    def add_intention(
        self,
        description: str,
        priority: float = 0.5,
        goal_id: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Create and persist a new intention.

        An intention may optionally be associated with a goal.
        """

        description = clip_text(str(
            description
        ).strip(), self.content_limit)

        if not description:
            return None

        priority = self._clamp_priority(
            priority
        )

        now = self._timestamp()

        intention = {
            "id": self._next_id(),
            "description": description,
            "priority": priority,
            "goal_id": goal_id,
            "status": "pending",
            "created_at": now,
            "updated_at": now,
            "completed_at": None,
        }

        self.intentions.append(
            intention
        )

        self.save()

        return intention

    def create_intention(
        self,
        description: str,
        priority: float = 0.5,
        goal_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Compatibility alias for add_intention()."""

        return self.add_intention(
            description,
            priority,
            goal_id,
        )

    # ============================================================
    # READ
    # ============================================================

    def get_intentions(
        self,
    ) -> list[dict[str, Any]]:
        """Return all intentions."""

        return list(
            self.intentions
        )

    def get_intention(
        self,
        intention_id: str,
    ) -> dict[str, Any] | None:
        """Find an intention by ID."""

        for intention in self.intentions:
            if intention.get("id") == intention_id:
                return intention

        return None

    def get_pending_intentions(
        self,
    ) -> list[dict[str, Any]]:
        """Return intentions waiting to be acted upon."""

        return self._get_by_status(
            "pending"
        )

    def get_active_intentions(
        self,
    ) -> list[dict[str, Any]]:
        """Return intentions currently being pursued."""

        return self._get_by_status(
            "active"
        )

    def get_completed_intentions(
        self,
    ) -> list[dict[str, Any]]:
        """Return completed intentions."""

        return self._get_by_status(
            "completed"
        )

    def get_cancelled_intentions(
        self,
    ) -> list[dict[str, Any]]:
        """Return cancelled intentions."""

        return self._get_by_status(
            "cancelled"
        )

    def _get_by_status(
        self,
        status: str,
    ) -> list[dict[str, Any]]:
        return [
            intention
            for intention in self.intentions
            if intention.get("status") == status
        ]

    # ============================================================
    # UPDATE
    # ============================================================

    def update_intention(
        self,
        intention_id: str,
        *,
        description: str | None = None,
        priority: float | None = None,
        goal_id: str | None = None,
    ) -> bool:
        """Update an intention's editable properties."""

        intention = self.get_intention(
            intention_id
        )

        if intention is None:
            return False

        if description is not None:
            description = str(
                description
            ).strip()

            if description:
                intention["description"] = description

        if priority is not None:
            intention["priority"] = (
                self._clamp_priority(
                    priority
                )
            )

        if goal_id is not None:
            intention["goal_id"] = goal_id

        intention["updated_at"] = (
            self._timestamp()
        )

        self.save()

        return True

    # ============================================================
    # STATE TRANSITIONS
    # ============================================================

    def activate_intention(
        self,
        intention_id: str,
    ) -> bool:
        """Move a pending intention into active execution."""

        return self._set_status(
            intention_id,
            "active",
        )

    def complete_intention(
        self,
        intention_id: str,
    ) -> bool:
        """Mark an intention as completed."""

        intention = self.get_intention(
            intention_id
        )

        if intention is None:
            return False

        intention["status"] = "completed"
        intention["completed_at"] = (
            self._timestamp()
        )
        intention["updated_at"] = (
            self._timestamp()
        )

        self.save()

        return True

    def cancel_intention(
        self,
        intention_id: str,
    ) -> bool:
        """Cancel an intention."""

        return self._set_status(
            intention_id,
            "cancelled",
        )

    def reactivate_intention(
        self,
        intention_id: str,
    ) -> bool:
        """Return a completed or cancelled intention to pending."""

        intention = self.get_intention(
            intention_id
        )

        if intention is None:
            return False

        intention["status"] = "pending"
        intention["completed_at"] = None
        intention["updated_at"] = (
            self._timestamp()
        )

        self.save()

        return True

    def _set_status(
        self,
        intention_id: str,
        status: str,
    ) -> bool:
        if status not in self.VALID_STATUSES:
            return False

        intention = self.get_intention(
            intention_id
        )

        if intention is None:
            return False

        intention["status"] = status
        intention["updated_at"] = (
            self._timestamp()
        )

        if status != "completed":
            intention["completed_at"] = None

        self.save()

        return True

    # ============================================================
    # GOAL RELATIONSHIP
    # ============================================================

    def get_for_goal(
        self,
        goal_id: str,
    ) -> list[dict[str, Any]]:
        """Return all intentions associated with a goal."""

        return [
            intention
            for intention in self.intentions
            if intention.get("goal_id") == goal_id
        ]

    def get_active_for_goal(
        self,
        goal_id: str,
    ) -> list[dict[str, Any]]:
        """Return active intentions associated with a goal."""

        return [
            intention
            for intention in self.get_for_goal(
                goal_id
            )
            if intention.get("status") in {
                "pending",
                "active",
            }
        ]

    # ============================================================
    # PRIORITY SUPPORT
    # ============================================================

    def get_highest_priority(
        self,
    ) -> dict[str, Any] | None:
        """
        Return the highest-priority pending or active intention.

        This is a convenience query. The dedicated priority system
        remains responsible for broader prioritization.
        """

        candidates = [
            intention
            for intention in self.intentions
            if intention.get("status") in {
                "pending",
                "active",
            }
        ]

        if not candidates:
            return None

        return max(
            candidates,
            key=lambda intention: float(
                intention.get(
                    "priority",
                    0.0,
                )
            ),
        )

    # ============================================================
    # DELETE
    # ============================================================

    def remove_intention(
        self,
        intention_id: str,
    ) -> bool:
        """Remove an intention from persistent storage."""

        intention = self.get_intention(
            intention_id
        )

        if intention is None:
            return False

        self.intentions.remove(
            intention
        )

        self.save()

        return True

    # ============================================================
    # UTILITIES
    # ============================================================

    def count_pending(self) -> int:
        """Return the number of pending intentions."""

        return len(
            self.get_pending_intentions()
        )

    def count_active(self) -> int:
        """Return the number of active intentions."""

        return len(
            self.get_active_intentions()
        )

    # ============================================================
    # INTERNAL HELPERS
    # ============================================================

    def _next_id(self) -> str:
        """Generate the next persistent intention ID."""

        highest = 0

        for intention in self.intentions:
            intention_id = str(
                intention.get(
                    "id",
                    "",
                )
            )

            if not intention_id.startswith(
                "intention_"
            ):
                continue

            try:
                number = int(
                    intention_id.split(
                        "_"
                    )[-1]
                )
            except ValueError:
                continue

            highest = max(
                highest,
                number,
            )

        return f"intention_{highest + 1}"

    @staticmethod
    def _timestamp() -> str:
        """Return a timezone-aware UTC timestamp."""

        return datetime.now(
            timezone.utc
        ).isoformat()

    @staticmethod
    def _clamp_priority(
        priority: float,
    ) -> float:
        """Keep priority within the 0.0-1.0 range."""

        try:
            value = float(priority)
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