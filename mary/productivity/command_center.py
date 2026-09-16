"""Small persistent project/task command center for MaryV2.

This is intentionally not another planner/agent. It stores creator-approved
shared work that Mary can surface across Home/Focus/Study/workspace views.
Nothing here executes shell commands or external actions.

The durable CommandCenter is distinct from mary.orchestration.TaskWorkspace:
TaskWorkspace is an ephemeral reasoning scratchpad; CommandCenter is the
canonical durable owner for creator projects and tasks.
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
    project_id: str = ""
    due_at: str = ""
    completed_at: str = ""
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
        fields = CommandItem.__dataclass_fields__
        for raw in payload.get("items", []):
            if not isinstance(raw, dict):
                continue
            # Only pass fields that actually exist in the persisted record so
            # newly-added schema fields retain their dataclass defaults. This is
            # the backward-compatible v1 -> v2 migration path.
            values = {
                key: raw[key]
                for key in fields
                if key in raw and raw[key] is not None
            }
            try:
                item = CommandItem(**values)
            except TypeError:
                continue
            if item.kind not in self.KINDS or item.status not in self.STATUSES:
                continue
            item.title = _clean(item.title, 180)
            item.notes = _clean(item.notes, 1000)
            item.project_id = _clean(item.project_id, 80)
            item.due_at = _clean(item.due_at, 80)
            item.completed_at = _clean(item.completed_at, 80)
            loaded.append(item)
        self.items = loaded[-500:]

    def save(self) -> bool:
        return atomic_write_json(
            self.path,
            {
                "version": 2,
                "items": [item.to_dict() for item in self.items[-500:]],
            },
        )

    def _find_item(self, item_id: str) -> CommandItem:
        clean_id = _clean(item_id, 80)
        item = next((entry for entry in self.items if entry.id == clean_id), None)
        if item is None:
            raise KeyError(clean_id)
        return item

    def _project_item(
        self,
        project_id: str,
        *,
        require_available: bool = True,
    ) -> CommandItem:
        project = self._find_item(project_id)
        if project.kind != "project":
            raise ValueError(f"Command item {project.id} is not a project.")
        if require_available and project.status in {"done", "archived"}:
            raise ValueError("Cannot attach work to a completed or archived project.")
        return project

    def _present(self, item: CommandItem) -> dict[str, Any]:
        payload = item.to_dict()
        if item.project_id:
            try:
                payload["project_title"] = self._project_item(
                    item.project_id,
                    require_available=False,
                ).title
            except (KeyError, ValueError):
                # Preserve the durable link for repair/diagnostics without
                # manufacturing a project title when historical data is stale.
                payload["project_title"] = ""
        return payload

    def get(self, item_id: str) -> dict[str, Any] | None:
        try:
            return self._present(self._find_item(item_id))
        except KeyError:
            return None

    def add(
        self,
        title: str,
        *,
        kind: str = "task",
        priority: int = 2,
        notes: str = "",
        project_id: str = "",
        due_at: str = "",
    ) -> dict[str, Any]:
        kind = _clean(kind, 20).lower()
        if kind not in self.KINDS:
            raise ValueError(f"Unsupported command-center item kind: {kind}")
        title = _clean(title, 180)
        if not title:
            raise ValueError("Item title cannot be empty.")

        linked_project = _clean(project_id, 80)
        due = _clean(due_at, 80)
        if kind != "task" and linked_project:
            raise ValueError("Only task items may reference a project.")
        if kind != "task" and due:
            raise ValueError("Only task items may have a due date.")
        if linked_project:
            self._project_item(linked_project)

        timestamp = _now()
        item = CommandItem(
            id=f"{kind}_{uuid.uuid4().hex[:10]}",
            kind=kind,
            title=title,
            priority=max(0, min(4, int(priority))),
            notes=_clean(notes, 1000),
            project_id=linked_project,
            due_at=due,
            created_at=timestamp,
            updated_at=timestamp,
        )
        self.items.append(item)
        self.save()
        return self._present(item)

    def create_project(
        self,
        title: str,
        *,
        priority: int = 2,
        notes: str = "",
    ) -> dict[str, Any]:
        return self.add(
            title,
            kind="project",
            priority=priority,
            notes=notes,
        )

    def create_task(
        self,
        title: str,
        *,
        project_id: str = "",
        priority: int = 2,
        notes: str = "",
        due_at: str = "",
    ) -> dict[str, Any]:
        return self.add(
            title,
            kind="task",
            priority=priority,
            notes=notes,
            project_id=project_id,
            due_at=due_at,
        )

    def update(self, item_id: str, **changes: Any) -> dict[str, Any]:
        item = self._find_item(item_id)

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
            if item.kind == "task":
                if status == "done" and not item.completed_at:
                    item.completed_at = _now()
                elif status != "done":
                    item.completed_at = ""
        if "priority" in changes:
            item.priority = max(0, min(4, int(changes["priority"])))
        if "project_id" in changes:
            if item.kind != "task":
                raise ValueError("Only task items may reference a project.")
            project_id = _clean(changes["project_id"], 80)
            if project_id:
                self._project_item(project_id)
            item.project_id = project_id
        if "due_at" in changes:
            if item.kind != "task":
                raise ValueError("Only task items may have a due date.")
            item.due_at = _clean(changes["due_at"], 80)

        item.updated_at = _now()
        self.save()
        return self._present(item)

    def complete_task(self, task_id: str) -> dict[str, Any]:
        item = self._find_item(task_id)
        if item.kind != "task":
            raise ValueError(f"Command item {item.id} is not a task.")
        return self.update(item.id, status="done")

    def list(
        self,
        *,
        include_archived: bool = False,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        values = (
            self.items
            if include_archived
            else [item for item in self.items if item.status != "archived"]
        )
        ordered = sorted(
            values,
            key=lambda item: (
                item.status == "done",
                -item.priority,
                item.updated_at,
            ),
        )
        return [
            self._present(item)
            for item in ordered[: max(1, min(500, int(limit)))]
        ]

    def list_projects(
        self,
        *,
        include_archived: bool = False,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        projects = [
            item
            for item in self.items
            if item.kind == "project"
            and (include_archived or item.status != "archived")
        ]
        ordered = sorted(
            projects,
            key=lambda item: (
                item.status in {"done", "archived"},
                -item.priority,
                item.updated_at,
            ),
        )
        return [
            self._present(item)
            for item in ordered[: max(1, min(500, int(limit)))]
        ]

    def list_tasks(
        self,
        *,
        project_id: str | None = None,
        include_archived: bool = False,
        include_done: bool = True,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        linked_project = _clean(project_id, 80) if project_id else ""
        if linked_project:
            self._project_item(linked_project, require_available=False)
        tasks = [
            item
            for item in self.items
            if item.kind == "task"
            and (not linked_project or item.project_id == linked_project)
            and (include_archived or item.status != "archived")
            and (include_done or item.status != "done")
        ]
        ordered = sorted(
            tasks,
            key=lambda item: (
                item.status == "done",
                -item.priority,
                item.due_at or "9999",
                item.updated_at,
            ),
        )
        return [
            self._present(item)
            for item in ordered[: max(1, min(500, int(limit)))]
        ]

    def summary(self) -> dict[str, Any]:
        active_items = [item for item in self.items if item.status == "active"]
        active_tasks = [
            item
            for item in active_items
            if item.kind == "task"
        ]
        waiting = [item for item in self.items if item.status == "waiting"]
        projects = [
            item
            for item in self.items
            if item.kind == "project" and item.status not in {"done", "archived"}
        ]
        open_tasks = [
            item
            for item in self.items
            if item.kind == "task" and item.status not in {"done", "archived"}
        ]
        completed_tasks = [
            item
            for item in self.items
            if item.kind == "task" and item.status == "done"
        ]
        ordered_active = sorted(
            active_items,
            key=lambda item: (-item.priority, item.created_at),
        )
        ordered_tasks = sorted(
            active_tasks,
            key=lambda item: (
                -item.priority,
                item.due_at or "9999",
                item.created_at,
            ),
        )
        ordered_projects = sorted(
            projects,
            key=lambda item: (-item.priority, item.created_at),
        )
        return {
            # Compatibility: "active" remains the count of all active command
            # items. Consumers that mean tasks should use active_tasks.
            "active": len(active_items),
            "active_tasks": len(active_tasks),
            "waiting": len(waiting),
            "projects": len(projects),
            "tasks": len(open_tasks),
            "completed_tasks": len(completed_tasks),
            "goals": sum(
                item.kind == "goal" and item.status not in {"done", "archived"}
                for item in self.items
            ),
            "top": [self._present(item) for item in ordered_active[:5]],
            "top_tasks": [self._present(item) for item in ordered_tasks[:5]],
            "project_list": [self._present(item) for item in ordered_projects[:20]],
        }
