"""
MaryV2 - Creator Directive System

Persistent internal record of explicit directions Unbe gives Mary about
how she should orient her own internal relationship, curiosity, priorities,
or development.

A creator directive is not ordinary memory:
- memory records what happened or what was said;
- a directive represents an explicit instruction Mary should adopt internally.

Directives never authorize external tools, internet access, code changes, or
other protected actions. Those boundaries remain enforced by the tool and
approval systems.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class CreatorDirectiveSystem:
    """Persistent manager for explicit creator directives."""

    VALID_STATUSES = {
        "active",
        "superseded",
        "revoked",
    }

    def __init__(
        self,
        path: str | Path = "data/relationship/creator_directives.json",
    ) -> None:
        self.path = Path(path)
        self.directives: list[dict[str, Any]] = []

    # ============================================================
    # LIFECYCLE
    # ============================================================

    def load(self) -> None:
        """Load directives from persistent storage."""

        if not self.path.exists():
            self._ensure_directory()
            self.save()
            return

        try:
            with self.path.open("r", encoding="utf-8") as file:
                payload = json.load(file)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            self.directives = []
            return

        if isinstance(payload, dict):
            raw = payload.get("directives", [])
        elif isinstance(payload, list):
            raw = payload
        else:
            raw = []

        self.directives = [
            item
            for item in raw
            if isinstance(item, dict)
        ] if isinstance(raw, list) else []

    def save(self) -> None:
        """Persist directive state."""

        self._ensure_directory()
        with self.path.open("w", encoding="utf-8") as file:
            json.dump(
                {"directives": self.directives},
                file,
                indent=4,
                ensure_ascii=False,
            )

    def _ensure_directory(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

    # ============================================================
    # CREATE / UPDATE
    # ============================================================

    def add(
        self,
        instruction: str,
        *,
        category: str,
        target: str,
        priority: float = 0.8,
        source: str = "creator_explicit",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Create or refresh an active directive for the same category/target."""

        instruction = str(instruction).strip()
        category = str(category).strip().lower()
        target = str(target).strip().lower()

        if not instruction or not category or not target:
            return None

        now = self._timestamp()
        priority = self._clamp(priority)

        existing = self.find_active(category=category, target=target)
        if existing is not None:
            existing["instruction"] = instruction
            existing["priority"] = priority
            existing["source"] = source
            existing["metadata"] = dict(metadata or {})
            existing["updated_at"] = now
            self.save()
            return existing

        directive = {
            "id": self._next_id(),
            "instruction": instruction,
            "category": category,
            "target": target,
            "priority": priority,
            "source": source,
            "status": "active",
            "metadata": dict(metadata or {}),
            "created_at": now,
            "updated_at": now,
        }

        self.directives.append(directive)
        self.save()
        return directive

    def revoke(self, directive_id: str) -> bool:
        directive = self.get(directive_id)
        if directive is None:
            return False
        directive["status"] = "revoked"
        directive["updated_at"] = self._timestamp()
        self.save()
        return True

    # ============================================================
    # READ
    # ============================================================

    def get(self, directive_id: str) -> dict[str, Any] | None:
        for directive in self.directives:
            if directive.get("id") == directive_id:
                return directive
        return None

    def get_all(self) -> list[dict[str, Any]]:
        return list(self.directives)

    def get_active(self) -> list[dict[str, Any]]:
        return [
            directive
            for directive in self.directives
            if directive.get("status") == "active"
        ]

    def find_active(
        self,
        *,
        category: str,
        target: str,
    ) -> dict[str, Any] | None:
        category = str(category).strip().lower()
        target = str(target).strip().lower()

        for directive in reversed(self.directives):
            if directive.get("status") != "active":
                continue
            if str(directive.get("category", "")).lower() != category:
                continue
            if str(directive.get("target", "")).lower() != target:
                continue
            return directive
        return None

    # ============================================================
    # UTILITIES
    # ============================================================

    def _next_id(self) -> str:
        highest = 0
        for directive in self.directives:
            directive_id = str(directive.get("id", ""))
            if not directive_id.startswith("directive_"):
                continue
            try:
                value = int(directive_id.rsplit("_", 1)[-1])
            except ValueError:
                continue
            highest = max(highest, value)
        return f"directive_{highest + 1}"

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _clamp(value: float) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            number = 0.8
        return max(0.0, min(1.0, number))
