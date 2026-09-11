"""Durable resumable workflow checkpoints for MaryV2."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

from .storage import AtomicJsonStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class WorkflowCheckpoint:
    id: str
    objective: str
    source: str
    status: str
    steps: tuple[str, ...]
    current_step: int
    completed_steps: tuple[int, ...]
    outstanding_dependencies: tuple[str, ...]
    required_approvals: tuple[str, ...]
    trace_id: str
    created_at: str
    updated_at: str
    last_result: str = ""


class DurableWorkflowStore:
    """Persist task progress without persisting hidden chain-of-thought."""

    VERSION = 1
    ACTIVE = {"ready", "running", "paused", "waiting", "recovering"}
    TERMINAL = {"completed", "failed", "cancelled"}

    def __init__(self, path: Path, *, capacity: int = 1000) -> None:
        self.capacity = max(32, int(capacity))
        self._store = AtomicJsonStore(path, default={"version": self.VERSION, "workflows": []})

    def create(
        self,
        *,
        objective: str,
        steps: Iterable[str],
        source: str,
        trace_id: str = "",
        dependencies: Iterable[str] = (),
        approvals: Iterable[str] = (),
    ) -> WorkflowCheckpoint:
        step_tuple = tuple(str(s).strip()[:600] for s in steps if str(s).strip())
        if not str(objective).strip() or not step_tuple:
            raise ValueError("objective and at least one step are required")
        now = _now()
        row = WorkflowCheckpoint(
            id=f"workflow_{uuid4().hex}",
            objective=str(objective).strip()[:1200],
            source=str(source).strip()[:160] or "unknown",
            status="ready",
            steps=step_tuple,
            current_step=0,
            completed_steps=(),
            outstanding_dependencies=tuple(dict.fromkeys(str(x).strip()[:240] for x in dependencies if str(x).strip())),
            required_approvals=tuple(dict.fromkeys(str(x).strip()[:240] for x in approvals if str(x).strip())),
            trace_id=str(trace_id).strip()[:160],
            created_at=now,
            updated_at=now,
        )
        self._append(row)
        return row

    def start(self, workflow_id: str) -> WorkflowCheckpoint:
        return self._update(workflow_id, status="running")

    def pause(self, workflow_id: str, *, reason: str = "") -> WorkflowCheckpoint:
        return self._update(workflow_id, status="paused", last_result=reason)

    def wait(self, workflow_id: str, *, dependency: str) -> WorkflowCheckpoint:
        current = self.get(workflow_id)
        deps = tuple(dict.fromkeys((*current.outstanding_dependencies, str(dependency).strip()[:240])))
        return self._update(workflow_id, status="waiting", outstanding_dependencies=deps)

    def resolve_dependency(self, workflow_id: str, dependency: str) -> WorkflowCheckpoint:
        current = self.get(workflow_id)
        deps = tuple(x for x in current.outstanding_dependencies if x != dependency)
        status = "ready" if not deps and current.status == "waiting" else current.status
        return self._update(workflow_id, outstanding_dependencies=deps, status=status)

    def satisfy_approval(self, workflow_id: str, approval: str) -> WorkflowCheckpoint:
        current = self.get(workflow_id)
        approvals = tuple(x for x in current.required_approvals if x != approval)
        return self._update(workflow_id, required_approvals=approvals)

    def complete_step(self, workflow_id: str, *, result: str = "") -> WorkflowCheckpoint:
        current = self.get(workflow_id)
        if current.status in self.TERMINAL:
            raise ValueError("terminal workflow cannot advance")
        completed = tuple(dict.fromkeys((*current.completed_steps, current.current_step)))
        next_step = current.current_step + 1
        if next_step >= len(current.steps):
            return self._update(
                workflow_id,
                status="completed",
                completed_steps=completed,
                current_step=len(current.steps),
                last_result=str(result).strip()[:1200],
            )
        return self._update(
            workflow_id,
            status="running",
            completed_steps=completed,
            current_step=next_step,
            last_result=str(result).strip()[:1200],
        )

    def fail(self, workflow_id: str, *, reason: str) -> WorkflowCheckpoint:
        return self._update(workflow_id, status="failed", last_result=str(reason).strip()[:1200])

    def recover(self, workflow_id: str) -> WorkflowCheckpoint:
        current = self.get(workflow_id)
        if current.status not in {"failed", "paused", "waiting", "recovering"}:
            return current
        return self._update(workflow_id, status="recovering")

    def resumable(self) -> list[WorkflowCheckpoint]:
        return [
            self._decode(row)
            for row in self._store.snapshot().get("workflows", [])
            if row.get("status") in self.ACTIVE
        ]

    def get(self, workflow_id: str) -> WorkflowCheckpoint:
        for row in self._store.snapshot().get("workflows", []):
            if row.get("id") == workflow_id:
                return self._decode(row)
        raise KeyError(workflow_id)

    def status(self) -> dict[str, Any]:
        rows = list(self._store.snapshot().get("workflows") or [])
        return {
            "version": self.VERSION,
            "workflows": len(rows),
            "resumable": sum(1 for row in rows if row.get("status") in self.ACTIVE),
            "terminal": sum(1 for row in rows if row.get("status") in self.TERMINAL),
            "persistence": "task progress only; no hidden reasoning persisted",
        }

    def _append(self, checkpoint: WorkflowCheckpoint) -> None:
        def mutate(data: dict[str, Any]) -> None:
            rows = list(data.get("workflows") or [])
            rows.append(self._encode(checkpoint))
            data["workflows"] = rows[-self.capacity :]
            data["version"] = self.VERSION
        self._store.mutate(mutate)

    def _update(self, workflow_id: str, **changes: Any) -> WorkflowCheckpoint:
        found = False
        updated = _now()

        def mutate(data: dict[str, Any]) -> None:
            nonlocal found
            for row in list(data.get("workflows") or []):
                if row.get("id") != workflow_id:
                    continue
                row.update(changes)
                for key in ("steps", "completed_steps", "outstanding_dependencies", "required_approvals"):
                    if key in row and isinstance(row[key], tuple):
                        row[key] = list(row[key])
                row["updated_at"] = updated
                found = True
                break

        self._store.mutate(mutate)
        if not found:
            raise KeyError(workflow_id)
        return self.get(workflow_id)

    @staticmethod
    def _encode(checkpoint: WorkflowCheckpoint) -> dict[str, Any]:
        row = asdict(checkpoint)
        for key in ("steps", "completed_steps", "outstanding_dependencies", "required_approvals"):
            row[key] = list(row[key])
        return row

    @staticmethod
    def _decode(row: dict[str, Any]) -> WorkflowCheckpoint:
        values = dict(row)
        for key in ("steps", "completed_steps", "outstanding_dependencies", "required_approvals"):
            values[key] = tuple(values.get(key) or [])
        return WorkflowCheckpoint(**values)
