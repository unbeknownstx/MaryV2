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

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mary.governance.bounds import bounded_payload, clip_text, enforce_capacity
from mary.runtime.persistence import atomic_write_json, cleanup_stale_temps, load_json_recovering


class CreatorDirectiveSystem:
    """Manage explicit creator directives, optionally persisting them."""

    VALID_STATUSES = {
        "active",
        "superseded",
        "revoked",
    }

    def __init__(
        self,
        path: str | Path | None = None,
        *,
        capacity: int = 512,
        content_limit: int = 2000,
        backup_generations: int = 3,
    ) -> None:
        self.path: Path | None = Path(path) if path is not None else None
        self.capacity = max(1, int(capacity))
        self.content_limit = max(128, int(content_limit))
        self.backup_generations = max(1, int(backup_generations))
        self.directives: list[dict[str, Any]] = []
        self.recovered_from_backup = False

    # ============================================================
    # LIFECYCLE
    # ============================================================

    def load(self) -> None:
        """Load directives with finite-backup recovery when configured."""
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
            raw = payload.get("directives", [])
        elif isinstance(payload, list):
            raw = payload
        else:
            raw = []
        self.directives = [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []
        self._compact()
        self.recovered_from_backup = bool(source is not None and source != self.path)

    def save(self) -> None:
        """Persist directives atomically after bounded compaction when configured."""
        self._compact()
        if self.path is None:
            return
        self._ensure_directory()
        atomic_write_json(
            self.path,
            {"directives": self.directives},
            backup_generations=self.backup_generations,
            indent=2,
        )

    def _compact(self) -> int:
        before = len(self.directives)
        for item in self.directives:
            if isinstance(item, dict):
                item["instruction"] = clip_text(item.get("instruction", ""), self.content_limit)
                item["metadata"] = bounded_payload(item.get("metadata", {}), text_limit=self.content_limit)
        enforce_capacity(
            self.directives,
            self.capacity,
            keep_score=lambda item: (
                1.0 if item.get("status") == "active" else 0.0,
                float(item.get("priority", 0.0) or 0.0),
                str(item.get("updated_at", item.get("created_at", ""))),
            ),
        )
        return max(0, before - len(self.directives))

    def _ensure_directory(self) -> None:
        if self.path is not None:
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

        instruction = clip_text(str(instruction).strip(), self.content_limit)
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
            existing["metadata"] = bounded_payload(metadata or {}, text_limit=self.content_limit)
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
            "metadata": bounded_payload(metadata or {}, text_limit=self.content_limit),
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
