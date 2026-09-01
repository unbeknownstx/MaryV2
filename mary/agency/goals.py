"""
MaryV2 - Goal System

Responsible for creating, tracking, updating, and completing
Mary's persistent goals.

Goals represent longer-term objectives that Mary is actively
trying to accomplish.

This module intentionally does not decide:
- what Mary should want,
- what Mary should prioritize,
- what action Mary should take,
- or how goals are reasoned about.

Those responsibilities belong to other agency/cognition systems.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mary.governance.bounds import clip_text, enforce_capacity
from mary.runtime.persistence import atomic_write_json, cleanup_stale_temps, load_json_recovering


class GoalSystem:
    """Manager for Mary's long-term goals with optional persistence."""

    VALID_STATUSES = {
        "active",
        "paused",
        "completed",
        "abandoned",
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
        self.goals: list[dict[str, Any]] = []

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
            raw = payload.get("goals", [])
        elif isinstance(payload, list):
            raw = payload
        else:
            raw = []
        self.goals = [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []
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
            {"goals": self.goals},
            backup_generations=self.backup_generations,
            indent=2,
        )

    def _compact(self) -> int:
        before = len(self.goals)
        for item in self.goals:
            if isinstance(item, dict) and isinstance(item.get("description"), str):
                item["description"] = clip_text(item["description"], self.content_limit)
        enforce_capacity(
            self.goals,
            self.capacity,
            keep_score=lambda item: (
                1.0 if str(item.get("status", "")) in {'active', 'paused'} else 0.0,
                float(item.get("importance", item.get("priority", 0.0)) or 0.0),
                str(item.get("updated_at", item.get("created_at", ""))),
            ),
        )
        return max(0, before - len(self.goals))

    def _ensure_directory(self) -> None:
        """Create the configured goal storage directory if necessary."""
        if self.path is None:
            return

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    # ============================================================
    # CREATE
    # ============================================================

    def add_goal(
        self,
        description: str,
        importance: float = 0.7,
    ) -> dict[str, Any] | None:
        """
        Create and persist a new goal.

        Returns the created goal or None if the description is empty.
        """

        description = clip_text(str(description).strip(), self.content_limit)

        if not description:
            return None

        importance = self._clamp_importance(
            importance
        )

        now = self._timestamp()

        goal = {
            "id": self._next_id(),
            "description": description,
            "importance": importance,
            "status": "active",
            "created_at": now,
            "updated_at": now,
            "completed_at": None,
        }

        self.goals.append(goal)
        self.save()

        return goal

    def create_goal(
        self,
        description: str,
        importance: float = 0.7,
    ) -> dict[str, Any] | None:
        """Compatibility alias for add_goal()."""

        return self.add_goal(
            description,
            importance,
        )

    # ============================================================
    # READ
    # ============================================================

    def get_goals(self) -> list[dict[str, Any]]:
        """Return all stored goals."""

        return list(self.goals)

    def get_active_goals(self) -> list[dict[str, Any]]:
        """Return goals currently marked as active."""

        return self._get_by_status("active")

    def get_paused_goals(self) -> list[dict[str, Any]]:
        """Return paused goals."""

        return self._get_by_status("paused")

    def get_completed_goals(self) -> list[dict[str, Any]]:
        """Return completed goals."""

        return self._get_by_status("completed")

    def get_abandoned_goals(self) -> list[dict[str, Any]]:
        """Return abandoned goals."""

        return self._get_by_status("abandoned")

    def get_goal(
        self,
        goal_id: str,
    ) -> dict[str, Any] | None:
        """Find a goal by ID."""

        for goal in self.goals:
            if goal.get("id") == goal_id:
                return goal

        return None

    def _get_by_status(
        self,
        status: str,
    ) -> list[dict[str, Any]]:
        return [
            goal
            for goal in self.goals
            if goal.get("status") == status
        ]

    # ============================================================
    # UPDATE
    # ============================================================

    def update_goal(
        self,
        goal_id: str,
        *,
        description: str | None = None,
        importance: float | None = None,
    ) -> bool:
        """
        Update editable goal properties.

        Returns True if the goal was found and updated.
        """

        goal = self.get_goal(goal_id)

        if goal is None:
            return False

        if description is not None:
            description = clip_text(str(description).strip(), self.content_limit)

            if description:
                goal["description"] = description

        if importance is not None:
            goal["importance"] = self._clamp_importance(
                importance
            )

        goal["updated_at"] = self._timestamp()

        self.save()

        return True

    # ============================================================
    # STATE TRANSITIONS
    # ============================================================

    def complete_goal(
        self,
        goal_id: str,
    ) -> bool:
        """Mark a goal as completed."""

        return self._set_status(
            goal_id,
            "completed",
            completed=True,
        )

    def pause_goal(
        self,
        goal_id: str,
    ) -> bool:
        """Pause an active goal."""

        return self._set_status(
            goal_id,
            "paused",
        )

    def reactivate_goal(
        self,
        goal_id: str,
    ) -> bool:
        """Reactivate a paused or previously abandoned goal."""

        return self._set_status(
            goal_id,
            "active",
            completed=False,
        )

    def abandon_goal(
        self,
        goal_id: str,
    ) -> bool:
        """Permanently mark a goal as abandoned."""

        return self._set_status(
            goal_id,
            "abandoned",
            completed=False,
        )

    def _set_status(
        self,
        goal_id: str,
        status: str,
        *,
        completed: bool | None = None,
    ) -> bool:
        if status not in self.VALID_STATUSES:
            return False

        goal = self.get_goal(goal_id)

        if goal is None:
            return False

        goal["status"] = status
        goal["updated_at"] = self._timestamp()

        if completed is True:
            goal["completed_at"] = self._timestamp()

        elif completed is False:
            goal["completed_at"] = None

        self.save()

        return True

    # ============================================================
    # PRIORITY SUPPORT
    # ============================================================

    def get_highest_priority_goal(
        self,
    ) -> dict[str, Any] | None:
        """
        Return the active goal with the highest importance.

        This does not replace the V2 priority system. It is simply
        a convenient read operation for other components.
        """

        active = self.get_active_goals()

        if not active:
            return None

        return max(
            active,
            key=lambda goal: float(
                goal.get("importance", 0.0)
            ),
        )

    # ============================================================
    # UTILITIES
    # ============================================================

    def count_active(self) -> int:
        """Return the number of active goals."""

        return len(
            self.get_active_goals()
        )

    def remove_goal(
        self,
        goal_id: str,
    ) -> bool:
        """
        Remove a goal from storage.

        This is intentionally separate from abandoning a goal.
        """

        goal = self.get_goal(goal_id)

        if goal is None:
            return False

        self.goals.remove(goal)
        self.save()

        return True

    # ============================================================
    # INTERNAL HELPERS
    # ============================================================

    def _next_id(self) -> str:
        """Generate the next persistent goal ID."""

        highest = 0

        for goal in self.goals:
            goal_id = str(
                goal.get("id", "")
            )

            if not goal_id.startswith("goal_"):
                continue

            try:
                number = int(
                    goal_id.split("_")[-1]
                )
            except ValueError:
                continue

            highest = max(
                highest,
                number,
            )

        return f"goal_{highest + 1}"

    @staticmethod
    def _timestamp() -> str:
        """Return a timezone-aware UTC timestamp."""

        return datetime.now(
            timezone.utc
        ).isoformat()

    @staticmethod
    def _clamp_importance(
        importance: float,
    ) -> float:
        """Keep importance within the 0.0-1.0 range."""

        try:
            value = float(importance)
        except (
            TypeError,
            ValueError,
        ):
            value = 0.7

        return max(
            0.0,
            min(
                1.0,
                value,
            ),
        )