"""Small persistent project/task command center for MaryV2.

This is intentionally not another planner/agent.  It stores creator-approved
threads that Mary can surface in Home/Focus/Study workspaces.  Nothing here
executes shell commands or external actions.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
import uuid
from typing import Any

from mary.runtime.persistence import atomic_write_json, load_json_recovering


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any, limit: int = 300) -> str:
    return " ".join(str(value or "").split())[:limit]


@dataclass
class CommandItem:
    id: str
    kind: str
    title: str
    status: str = "active"
    priority: int = 2
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CommandCenter:
    KINDS = {"task", "project", "goal", "waiting", "idea"}
    STATUSES = {"active", "waiting", "done", "paused", "archived"}

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.path = self.root / "command_center.json"
        self.items: list[CommandItem] = []
        self._load()

    def _load(self) -> None:
        payload, _ = load_json_recovering(self.path)
        if not isinstance(payload, dict):
            return
        loaded: list[CommandItem] = []
        for raw in payload.get("items", []):
            if not isinstance(raw, dict):
                continue
            try:
                loaded.append(CommandItem(**{k: raw.get(k) for k in CommandItem.__dataclass_fields__}))
            except TypeError:
                continue
        self.items = loaded[-500:]

    def save(self) -> bool:
        return atomic_write_json(self.path, {"version": 1, "items": [item.to_dict() for item in self.items[-500:]]})

    def add(self, title: str, *, kind: str = "task", priority: int = 2, notes: str = "") -> dict[str, Any]:
        kind = _clean(kind, 20).lower()
        if kind not in self.KINDS:
            raise ValueError(f"Unsupported command-center item kind: {kind}")
        title = _clean(title, 180)
        if not title:
            raise ValueError("Item title cannot be empty.")
        timestamp = _now()
        item = CommandItem(
            id=f"{kind}_{uuid.uuid4().hex[:10]}", kind=kind, title=title,
            priority=max(0, min(4, int(priority))), notes=_clean(notes, 1000),
            created_at=timestamp, updated_at=timestamp,
        )
        self.items.append(item)
        self.save()
        return item.to_dict()

    def update(self, item_id: str, **changes: Any) -> dict[str, Any]:
        item = next((entry for entry in self.items if entry.id == item_id), None)
        if item is None:
            raise KeyError(item_id)
        if "title" in changes:
            title = _clean(changes["title"], 180)
            if title:
                item.title = title
        if "notes" in changes:
            item.notes = _clean(changes["notes"], 1000)
        if "status" in changes:
            status = _clean(changes["status"], 20).lower()
            if status not in self.STATUSES:
                raise ValueError(f"Unsupported status: {status}")
            item.status = status
        if "priority" in changes:
            item.priority = max(0, min(4, int(changes["priority"])))
        item.updated_at = _now()
        self.save()
        return item.to_dict()

    def list(self, *, include_archived: bool = False, limit: int = 100) -> list[dict[str, Any]]:
        values = self.items if include_archived else [item for item in self.items if item.status != "archived"]
        ordered = sorted(values, key=lambda item: (item.status == "done", -item.priority, item.updated_at), reverse=False)
        return [item.to_dict() for item in ordered[: max(1, min(500, int(limit)))]]

    def summary(self) -> dict[str, Any]:
        active = [item for item in self.items if item.status == "active"]
        waiting = [item for item in self.items if item.status == "waiting"]
        return {
            "active": len(active), "waiting": len(waiting),
            "projects": sum(item.kind == "project" and item.status not in {"done", "archived"} for item in self.items),
            "goals": sum(item.kind == "goal" and item.status not in {"done", "archived"} for item in self.items),
            "top": [item.to_dict() for item in sorted(active, key=lambda x: (-x.priority, x.created_at))[:5]],
        }
