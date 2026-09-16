"""Deterministic chat bridge for Mary's durable creator work.

This stage handles only a small set of explicit project/task commands. It is
not a planner and never asks an LLM to invent identifiers or workspace state.
Non-matching language passes through untouched to Mary's normal turn pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from mary.runtime.pipeline import PipelineContext, PipelineStage, StageResult


_SPACE_RE = re.compile(r"\s+")
_PROJECT_CREATE_RE = re.compile(
    r"^(?:please\s+)?(?:create|make|start)\s+(?:a\s+)?(?:new\s+)?project\s+(?:called|named)\s+(.+?)\s*[.!]?$",
    re.IGNORECASE,
)
_PROJECT_ADD_RE = re.compile(
    r"^(?:please\s+)?add\s+(?:a\s+)?(?:new\s+)?project\s+(.+?)\s*[.!]?$",
    re.IGNORECASE,
)
_TASK_LINKED_RE = re.compile(
    r"^(?:please\s+)?(?:create|make|add)\s+(?:a\s+)?(?:new\s+)?task(?:\s+(?:called|named))?\s+(.+?)\s+(?:to|under|in)\s+(?:the\s+)?project\s+(.+?)\s*[.!]?$",
    re.IGNORECASE,
)
_TASK_CREATE_RE = re.compile(
    r"^(?:please\s+)?(?:create|make|add)\s+(?:a\s+)?(?:new\s+)?task\s+(?:called|named)\s+(.+?)\s*[.!]?$",
    re.IGNORECASE,
)
_TASK_COMPLETE_RE = re.compile(
    r"^(?:please\s+)?(?:complete|finish|mark\s+done)\s+(?:the\s+)?task(?:\s+(?:called|named))?\s+(.+?)\s*[.!]?$",
    re.IGNORECASE,
)
_LIST_PROJECTS_RE = re.compile(
    r"^(?:please\s+)?(?:show|list)(?:\s+me)?\s+(?:my\s+)?projects\s*[.!]?$",
    re.IGNORECASE,
)
_LIST_TASKS_RE = re.compile(
    r"^(?:please\s+)?(?:show|list)(?:\s+me)?\s+(?:my\s+)?tasks(?:\s+(?:for|in|under)\s+(?:the\s+)?project\s+(.+?))?\s*[.!]?$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SharedWorkCommand:
    action: str
    title: str = ""
    project_title: str = ""


def _title(value: Any, limit: int = 180) -> str:
    text = _SPACE_RE.sub(" ", str(value or "").strip())
    text = text.strip(" \t\r\n\"'“”")
    return text[:limit].strip()


def _key(value: Any) -> str:
    return _SPACE_RE.sub(" ", str(value or "").strip()).casefold()


def parse_shared_work_command(text: str) -> SharedWorkCommand | None:
    value = _SPACE_RE.sub(" ", str(text or "").strip())
    if not value or len(value) > 500:
        return None

    match = _PROJECT_CREATE_RE.match(value) or _PROJECT_ADD_RE.match(value)
    if match:
        title = _title(match.group(1))
        return SharedWorkCommand("project.create", title=title) if title else None

    match = _TASK_LINKED_RE.match(value)
    if match:
        title = _title(match.group(1))
        project = _title(match.group(2))
        if title and project:
            return SharedWorkCommand(
                "task.create",
                title=title,
                project_title=project,
            )
        return None

    match = _TASK_CREATE_RE.match(value)
    if match:
        title = _title(match.group(1))
        return SharedWorkCommand("task.create", title=title) if title else None

    match = _TASK_COMPLETE_RE.match(value)
    if match:
        title = _title(match.group(1))
        return SharedWorkCommand("task.complete", title=title) if title else None

    if _LIST_PROJECTS_RE.match(value):
        return SharedWorkCommand("project.list")

    match = _LIST_TASKS_RE.match(value)
    if match:
        return SharedWorkCommand(
            "task.list",
            project_title=_title(match.group(1)) if match.group(1) else "",
        )

    return None


class SharedWorkStage(PipelineStage):
    """Handle explicit durable-work commands before ordinary cognition."""

    def __init__(self, ecosystem, *, name: str = "shared_work") -> None:
        super().__init__(
            name=name,
            handler=lambda context: None,
            required=True,
            enabled=True,
        )
        self.ecosystem = ecosystem

    @staticmethod
    def _creator_turn(context: PipelineContext) -> bool:
        initiated_by = str(context.metadata.get("initiated_by") or "creator").strip().lower()
        authority = str(context.metadata.get("input_authority") or "creator").strip().lower()
        return (
            initiated_by not in {"mary_presence", "mary_initiative", "presence"}
            and authority not in {"environment_context_only", "context_only"}
        )

    def _project_by_title(self, title: str) -> tuple[dict[str, Any] | None, str | None]:
        matches = [
            project
            for project in self.ecosystem.command.list_projects(limit=500)
            if _key(project.get("title")) == _key(title)
            and str(project.get("status") or "") not in {"done", "archived"}
        ]
        if len(matches) == 1:
            return matches[0], None
        if not matches:
            return None, f'I could not find an active project named "{title}", so I did not change anything.'
        return None, f'I found more than one active project named "{title}", so I did not guess which one you meant.'

    def _task_by_title(
        self,
        title: str,
        *,
        project_id: str = "",
    ) -> tuple[dict[str, Any] | None, str | None]:
        tasks = self.ecosystem.command.list_tasks(
            project_id=project_id or None,
            include_done=False,
            limit=500,
        )
        matches = [
            task
            for task in tasks
            if _key(task.get("title")) == _key(title)
            and str(task.get("status") or "") not in {"done", "archived"}
        ]
        if len(matches) == 1:
            return matches[0], None
        if not matches:
            return None, f'I could not find an open task named "{title}", so I did not change anything.'
        return None, f'I found more than one open task named "{title}", so I did not guess which one you meant.'

    @staticmethod
    def _handled(
        response: str,
        *,
        action: str,
        record: dict[str, Any] | None = None,
    ) -> StageResult:
        value = {
            "action": action,
            "record": dict(record or {}),
            "execution": "completed" if record is not None else "read_only",
            "authority": "canonical_workspace",
        }
        return StageResult(
            success=True,
            output=response,
            values={"workspace_action": value},
            metadata={
                "handled_by": "shared_work",
                "workspace_action": value,
            },
            stop_pipeline=True,
        )

    def process(self, context: PipelineContext) -> StageResult:
        if not self._creator_turn(context):
            return StageResult(success=True, skipped=True)

        command = parse_shared_work_command(str(context.input_data or ""))
        if command is None:
            return StageResult(success=True, skipped=True)

        source = "shared_work_chat:" + str(context.metadata.get("surface") or "runtime")[:64]

        if command.action == "project.create":
            result = self.ecosystem.apply_workspace_action(
                "project.create",
                {"title": command.title},
                source=source,
            )
            project = dict(result["project"])
            return self._handled(
                f'Created project "{project["title"]}".',
                action=command.action,
                record=project,
            )

        if command.action == "task.create":
            project_id = ""
            if command.project_title:
                project, error = self._project_by_title(command.project_title)
                if error:
                    return self._handled(error, action="task.create.rejected")
                project_id = str(project["id"])
            result = self.ecosystem.apply_workspace_action(
                "task.create",
                {
                    "title": command.title,
                    "project_id": project_id,
                },
                source=source,
            )
            task = dict(result["task"])
            if task.get("project_title"):
                response = f'Added task "{task["title"]}" to project "{task["project_title"]}".'
            else:
                response = f'Created task "{task["title"]}".'
            return self._handled(
                response,
                action=command.action,
                record=task,
            )

        if command.action == "task.complete":
            task, error = self._task_by_title(command.title)
            if error:
                return self._handled(error, action="task.complete.rejected")
            result = self.ecosystem.apply_workspace_action(
                "task.complete",
                {"task_id": task["id"]},
                source=source,
            )
            completed = dict(result["task"])
            return self._handled(
                f'Completed task "{completed["title"]}".',
                action=command.action,
                record=completed,
            )

        if command.action == "project.list":
            projects = self.ecosystem.command.list_projects(limit=20)
            if not projects:
                return self._handled(
                    "There are no active projects yet.",
                    action=command.action,
                )
            names = ", ".join(str(item.get("title") or "") for item in projects)
            return self._handled(
                "Active projects: " + names + ".",
                action=command.action,
            )

        if command.action == "task.list":
            project_id = ""
            label = ""
            if command.project_title:
                project, error = self._project_by_title(command.project_title)
                if error:
                    return self._handled(error, action="task.list.rejected")
                project_id = str(project["id"])
                label = f' for project "{project["title"]}"'
            tasks = self.ecosystem.command.list_tasks(
                project_id=project_id or None,
                include_done=False,
                limit=20,
            )
            if not tasks:
                return self._handled(
                    "There are no open tasks" + label + ".",
                    action=command.action,
                )
            names = ", ".join(str(item.get("title") or "") for item in tasks)
            return self._handled(
                "Open tasks" + label + ": " + names + ".",
                action=command.action,
            )

        return StageResult(success=True, skipped=True)
