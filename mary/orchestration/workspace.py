"""MaryV2 ephemeral task workspace.

The workspace gives Mary a bounded place to organize work before the future
orchestrator chooses models, tools, research, verification, or human review.

Important persistence boundary:
    - task workspaces are process-local and ephemeral
    - they never write Mary's memory or developed-self state themselves
    - model/tool consultation records are suggestions/evidence, not truth
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable

from mary.orchestration.models import (
    ProvenanceSource,
    TaskConsultation,
    TaskDecisionRecord,
    TaskEvidence,
    TaskHypothesis,
    TaskStatus,
)


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_provenance(value: str | ProvenanceSource) -> str:
    if isinstance(value, ProvenanceSource):
        return value.value
    return str(value).strip().lower()


@dataclass
class TaskWorkspace:
    """Temporary structured state for one piece of work."""

    task_id: str
    objective: str
    status: TaskStatus = TaskStatus.ACTIVE
    created_at: str = field(default_factory=_timestamp)
    updated_at: str = field(default_factory=_timestamp)
    completed_at: str | None = None
    outcome: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    evidence: list[TaskEvidence] = field(default_factory=list)
    hypotheses: list[TaskHypothesis] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    actions: list[dict[str, Any]] = field(default_factory=list)
    consultations: list[TaskConsultation] = field(default_factory=list)
    decisions: list[TaskDecisionRecord] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.objective = str(self.objective).strip()
        if not self.objective:
            raise ValueError("Task objective cannot be empty.")
        if not isinstance(self.status, TaskStatus):
            self.status = TaskStatus(str(self.status).strip().lower())
        self.metadata = dict(self.metadata)

    @property
    def active(self) -> bool:
        return self.status == TaskStatus.ACTIVE

    def _require_active(self) -> None:
        if not self.active:
            raise RuntimeError(
                f"Task {self.task_id} is {self.status.value} and cannot be modified."
            )

    def _touch(self) -> None:
        self.updated_at = _timestamp()

    def add_evidence(
        self,
        *,
        evidence_id: str,
        content: str,
        provenance: str | ProvenanceSource,
        source_detail: str = "",
        confidence: float = 0.5,
        metadata: dict[str, Any] | None = None,
    ) -> TaskEvidence:
        self._require_active()
        text = str(content).strip()
        if not text:
            raise ValueError("Evidence content cannot be empty.")
        source = _normalize_provenance(provenance)
        if not source:
            raise ValueError("Evidence provenance cannot be empty.")

        item = TaskEvidence(
            evidence_id=evidence_id,
            content=text,
            provenance=source,
            source_detail=source_detail,
            confidence=confidence,
            metadata=metadata or {},
        )
        self.evidence.append(item)
        self._touch()
        return item

    def add_hypothesis(
        self,
        *,
        hypothesis_id: str,
        content: str,
        confidence: float = 0.5,
        metadata: dict[str, Any] | None = None,
    ) -> TaskHypothesis:
        self._require_active()
        text = str(content).strip()
        if not text:
            raise ValueError("Hypothesis content cannot be empty.")

        item = TaskHypothesis(
            hypothesis_id=hypothesis_id,
            content=text,
            confidence=confidence,
            metadata=metadata or {},
        )
        self.hypotheses.append(item)
        self._touch()
        return item

    def add_question(self, question: str) -> str:
        self._require_active()
        text = str(question).strip()
        if not text:
            raise ValueError("Task question cannot be empty.")
        self.questions.append(text)
        self._touch()
        return text

    def record_action(
        self,
        *,
        action: str,
        status: str,
        result: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._require_active()
        name = str(action).strip()
        if not name:
            raise ValueError("Task action cannot be empty.")
        record = {
            "action": name,
            "status": str(status).strip().lower() or "unknown",
            "result": str(result).strip(),
            "created_at": _timestamp(),
            "metadata": dict(metadata or {}),
        }
        self.actions.append(record)
        self._touch()
        return dict(record)

    def record_consultation(
        self,
        *,
        consultation_id: str,
        role: str,
        source: str,
        request_summary: str,
        response_summary: str,
        status: str = "completed",
        metadata: dict[str, Any] | None = None,
    ) -> TaskConsultation:
        self._require_active()
        item = TaskConsultation(
            consultation_id=consultation_id,
            role=role,
            source=source,
            request_summary=request_summary,
            response_summary=response_summary,
            status=status,
            metadata=metadata or {},
        )
        self.consultations.append(item)
        self._touch()
        return item

    def record_decision(
        self,
        *,
        decision_id: str,
        description: str,
        reason: str = "",
        status: str = "proposed",
        metadata: dict[str, Any] | None = None,
    ) -> TaskDecisionRecord:
        self._require_active()
        text = str(description).strip()
        if not text:
            raise ValueError("Task decision description cannot be empty.")
        item = TaskDecisionRecord(
            decision_id=decision_id,
            description=text,
            reason=reason,
            status=status,
            metadata=metadata or {},
        )
        self.decisions.append(item)
        self._touch()
        return item

    def close(self, status: TaskStatus, *, outcome: str = "") -> None:
        self._require_active()
        if status == TaskStatus.ACTIVE:
            raise ValueError("Closing a task requires a terminal status.")
        self.status = status
        self.outcome = str(outcome).strip()
        self.completed_at = _timestamp()
        self._touch()

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "objective": self.objective,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "outcome": self.outcome,
            "metadata": dict(self.metadata),
            "evidence": [item.to_dict() for item in self.evidence],
            "hypotheses": [item.to_dict() for item in self.hypotheses],
            "questions": list(self.questions),
            "actions": [dict(item) for item in self.actions],
            "consultations": [item.to_dict() for item in self.consultations],
            "decisions": [item.to_dict() for item in self.decisions],
        }

    def summary(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "objective": self.objective,
            "status": self.status.value,
            "evidence_count": len(self.evidence),
            "hypothesis_count": len(self.hypotheses),
            "question_count": len(self.questions),
            "action_count": len(self.actions),
            "consultation_count": len(self.consultations),
            "decision_count": len(self.decisions),
        }


class TaskWorkspaceManager:
    """Process-local manager for Mary's ephemeral task workspaces."""

    PERSISTENCE_POLICY = "ephemeral_process_local"
    PROMOTION_POLICY = "explicit_existing_paths_only"

    def __init__(self) -> None:
        self._tasks: dict[str, TaskWorkspace] = {}
        self._current_task_id: str | None = None
        self._task_counter = 0
        self._evidence_counter = 0
        self._hypothesis_counter = 0
        self._consultation_counter = 0
        self._decision_counter = 0

    def create_task(
        self,
        objective: str,
        *,
        metadata: dict[str, Any] | None = None,
        make_current: bool = True,
    ) -> TaskWorkspace:
        text = str(objective).strip()
        if not text:
            raise ValueError("Task objective cannot be empty.")
        self._task_counter += 1
        task = TaskWorkspace(
            task_id=f"task_{self._task_counter:04d}",
            objective=text,
            metadata=metadata or {},
        )
        self._tasks[task.task_id] = task
        if make_current:
            self._current_task_id = task.task_id
        return task

    def get(self, task_id: str) -> TaskWorkspace | None:
        return self._tasks.get(str(task_id).strip())

    def current(self) -> TaskWorkspace | None:
        if self._current_task_id is None:
            return None
        task = self._tasks.get(self._current_task_id)
        if task is None or not task.active:
            return None
        return task

    def set_current(self, task_id: str) -> TaskWorkspace:
        task = self._require_task(task_id)
        if not task.active:
            raise RuntimeError("Only active tasks can become the current task.")
        self._current_task_id = task.task_id
        return task

    def list_tasks(self, *, status: TaskStatus | str | None = None) -> list[TaskWorkspace]:
        tasks = list(self._tasks.values())
        if status is None:
            return tasks
        expected = status if isinstance(status, TaskStatus) else TaskStatus(str(status))
        return [task for task in tasks if task.status == expected]

    def add_evidence(
        self,
        task_id: str,
        content: str,
        *,
        provenance: str | ProvenanceSource,
        source_detail: str = "",
        confidence: float = 0.5,
        metadata: dict[str, Any] | None = None,
    ) -> TaskEvidence:
        task = self._require_task(task_id)
        self._evidence_counter += 1
        return task.add_evidence(
            evidence_id=f"evidence_{self._evidence_counter:04d}",
            content=content,
            provenance=provenance,
            source_detail=source_detail,
            confidence=confidence,
            metadata=metadata,
        )

    def add_hypothesis(
        self,
        task_id: str,
        content: str,
        *,
        confidence: float = 0.5,
        metadata: dict[str, Any] | None = None,
    ) -> TaskHypothesis:
        task = self._require_task(task_id)
        self._hypothesis_counter += 1
        return task.add_hypothesis(
            hypothesis_id=f"hypothesis_{self._hypothesis_counter:04d}",
            content=content,
            confidence=confidence,
            metadata=metadata,
        )

    def add_question(self, task_id: str, question: str) -> str:
        return self._require_task(task_id).add_question(question)

    def record_action(
        self,
        task_id: str,
        *,
        action: str,
        status: str,
        result: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._require_task(task_id).record_action(
            action=action,
            status=status,
            result=result,
            metadata=metadata,
        )

    def record_consultation(
        self,
        task_id: str,
        *,
        role: str,
        source: str,
        request_summary: str,
        response_summary: str,
        status: str = "completed",
        metadata: dict[str, Any] | None = None,
    ) -> TaskConsultation:
        task = self._require_task(task_id)
        self._consultation_counter += 1
        return task.record_consultation(
            consultation_id=f"consultation_{self._consultation_counter:04d}",
            role=role,
            source=source,
            request_summary=request_summary,
            response_summary=response_summary,
            status=status,
            metadata=metadata,
        )

    def record_decision(
        self,
        task_id: str,
        *,
        description: str,
        reason: str = "",
        status: str = "proposed",
        metadata: dict[str, Any] | None = None,
    ) -> TaskDecisionRecord:
        task = self._require_task(task_id)
        self._decision_counter += 1
        return task.record_decision(
            decision_id=f"task_decision_{self._decision_counter:04d}",
            description=description,
            reason=reason,
            status=status,
            metadata=metadata,
        )

    def complete(self, task_id: str, *, outcome: str = "") -> TaskWorkspace:
        return self._close(task_id, TaskStatus.COMPLETED, outcome=outcome)

    def cancel(self, task_id: str, *, outcome: str = "") -> TaskWorkspace:
        return self._close(task_id, TaskStatus.CANCELLED, outcome=outcome)

    def fail(self, task_id: str, *, outcome: str = "") -> TaskWorkspace:
        return self._close(task_id, TaskStatus.FAILED, outcome=outcome)

    def status(self) -> dict[str, Any]:
        active = [task for task in self._tasks.values() if task.active]
        current = self.current()
        return {
            "persistence": self.PERSISTENCE_POLICY,
            "promotion_policy": self.PROMOTION_POLICY,
            "task_count": len(self._tasks),
            "active_count": len(active),
            "current_task_id": current.task_id if current is not None else None,
        }

    def _close(
        self,
        task_id: str,
        status: TaskStatus,
        *,
        outcome: str,
    ) -> TaskWorkspace:
        task = self._require_task(task_id)
        task.close(status, outcome=outcome)
        if self._current_task_id == task.task_id:
            self._current_task_id = None
        return task

    def _require_task(self, task_id: str) -> TaskWorkspace:
        task = self.get(task_id)
        if task is None:
            raise KeyError(f"Unknown task: {task_id}")
        return task


__all__ = [
    "TaskWorkspace",
    "TaskWorkspaceManager",
]
