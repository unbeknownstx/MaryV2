"""MaryV2 bounded ephemeral task workspace.

Task work is temporary by design. It may contain hypotheses, model suggestions,
debug output, and evidence without becoming Mary/creator durable state. Both the
number of tasks and every per-task collection have hard ceilings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from mary.governance.bounds import bounded_payload, clip_text, enforce_capacity
from mary.governance.limits import RuntimeLimits
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
    limits: RuntimeLimits = field(default_factory=RuntimeLimits, repr=False, compare=False)

    def __post_init__(self) -> None:
        self.objective = clip_text(str(self.objective).strip(), self.limits.task_text_characters)
        if not self.objective:
            raise ValueError("Task objective cannot be empty.")
        if not isinstance(self.status, TaskStatus):
            self.status = TaskStatus(str(self.status).strip().lower())
        self.metadata = bounded_payload(
            self.metadata,
            text_limit=self.limits.task_text_characters,
            item_limit=self.limits.metadata_item_capacity,
            depth_limit=self.limits.metadata_depth,
        )
        self._compact()

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

    def _compact(self) -> None:
        enforce_capacity(self.evidence, self.limits.task_evidence_capacity)
        enforce_capacity(self.hypotheses, self.limits.task_hypothesis_capacity)
        enforce_capacity(self.questions, self.limits.task_question_capacity)
        enforce_capacity(self.actions, self.limits.task_action_capacity)
        enforce_capacity(self.consultations, self.limits.task_consultation_capacity)
        enforce_capacity(self.decisions, self.limits.task_decision_capacity)

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
        text = clip_text(str(content).strip(), self.limits.task_text_characters)
        if not text:
            raise ValueError("Evidence content cannot be empty.")
        source = _normalize_provenance(provenance)
        if not source:
            raise ValueError("Evidence provenance cannot be empty.")
        item = TaskEvidence(
            evidence_id=evidence_id,
            content=text,
            provenance=source,
            source_detail=clip_text(source_detail, 512),
            confidence=confidence,
            metadata=bounded_payload(
                metadata or {},
                text_limit=self.limits.task_text_characters,
                item_limit=self.limits.metadata_item_capacity,
                depth_limit=self.limits.metadata_depth,
            ),
        )
        self.evidence.append(item)
        self._compact()
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
        text = clip_text(str(content).strip(), self.limits.task_text_characters)
        if not text:
            raise ValueError("Hypothesis content cannot be empty.")
        item = TaskHypothesis(
            hypothesis_id=hypothesis_id,
            content=text,
            confidence=confidence,
            metadata=bounded_payload(
                metadata or {},
                text_limit=self.limits.task_text_characters,
                item_limit=self.limits.metadata_item_capacity,
                depth_limit=self.limits.metadata_depth,
            ),
        )
        self.hypotheses.append(item)
        self._compact()
        self._touch()
        return item

    def add_question(self, question: str) -> str:
        self._require_active()
        text = clip_text(str(question).strip(), self.limits.task_text_characters)
        if not text:
            raise ValueError("Task question cannot be empty.")
        self.questions.append(text)
        self._compact()
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
        name = clip_text(str(action).strip(), 1000)
        if not name:
            raise ValueError("Task action cannot be empty.")
        record = {
            "action": name,
            "status": str(status).strip().lower() or "unknown",
            "result": clip_text(str(result).strip(), self.limits.task_text_characters),
            "created_at": _timestamp(),
            "metadata": dict(metadata or {}),
        }
        self.actions.append(record)
        self._compact()
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
            role=clip_text(role, 256),
            source=clip_text(source, 256),
            request_summary=clip_text(request_summary, self.limits.task_text_characters),
            response_summary=clip_text(response_summary, self.limits.task_text_characters),
            status=status,
            metadata=bounded_payload(
                metadata or {},
                text_limit=self.limits.task_text_characters,
                item_limit=self.limits.metadata_item_capacity,
                depth_limit=self.limits.metadata_depth,
            ),
        )
        self.consultations.append(item)
        self._compact()
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
        text = clip_text(str(description).strip(), self.limits.task_text_characters)
        if not text:
            raise ValueError("Task decision description cannot be empty.")
        item = TaskDecisionRecord(
            decision_id=decision_id,
            description=text,
            reason=clip_text(reason, self.limits.task_text_characters),
            status=status,
            metadata=bounded_payload(
                metadata or {},
                text_limit=self.limits.task_text_characters,
                item_limit=self.limits.metadata_item_capacity,
                depth_limit=self.limits.metadata_depth,
            ),
        )
        self.decisions.append(item)
        self._compact()
        self._touch()
        return item

    def close(self, status: TaskStatus, *, outcome: str = "") -> None:
        self._require_active()
        if status == TaskStatus.ACTIVE:
            raise ValueError("Closing a task requires a terminal status.")
        self.status = status
        self.outcome = clip_text(str(outcome).strip(), self.limits.task_text_characters)
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
    """Process-local bounded manager for Mary's ephemeral workspaces."""

    PERSISTENCE_POLICY = "ephemeral_process_local"
    PROMOTION_POLICY = "explicit_existing_paths_only"

    def __init__(self, *, limits: RuntimeLimits | None = None, on_evict=None) -> None:
        self.limits = limits or RuntimeLimits()
        self.on_evict = on_evict
        self._tasks: dict[str, TaskWorkspace] = {}
        self._current_task_id: str | None = None
        self._task_counter = 0
        self._evidence_counter = 0
        self._hypothesis_counter = 0
        self._consultation_counter = 0
        self._decision_counter = 0
        self.evicted_tasks = 0

    def _compact_tasks(self) -> None:
        while len(self._tasks) > self.limits.task_capacity:
            candidates = [task for task in self._tasks.values() if not task.active]
            if not candidates:
                # Active tasks are protected in normal operation. If the caller
                # tries to create more simultaneous tasks than the hard ceiling,
                # reject creation instead of silently discarding active work.
                raise RuntimeError("Active task capacity reached; close a task before creating another.")
            victim = min(candidates, key=lambda item: (item.updated_at, item.created_at))
            self._tasks.pop(victim.task_id, None)
            self.evicted_tasks += 1
            if callable(self.on_evict):
                self.on_evict(victim.task_id)

    def create_task(
        self,
        objective: str,
        *,
        metadata: dict[str, Any] | None = None,
        make_current: bool = True,
    ) -> TaskWorkspace:
        text = clip_text(str(objective).strip(), self.limits.task_text_characters)
        if not text:
            raise ValueError("Task objective cannot be empty.")
        if len(self._tasks) >= self.limits.task_capacity and all(t.active for t in self._tasks.values()):
            raise RuntimeError("Active task capacity reached; close a task before creating another.")
        self._task_counter += 1
        task = TaskWorkspace(
            task_id=f"task_{self._task_counter:04d}",
            objective=text,
            metadata=bounded_payload(
                metadata or {},
                text_limit=self.limits.task_text_characters,
                item_limit=self.limits.metadata_item_capacity,
                depth_limit=self.limits.metadata_depth,
            ),
            limits=self.limits,
        )
        self._tasks[task.task_id] = task
        self._compact_tasks()
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

    def add_evidence(self, task_id: str, content: str, *, provenance, source_detail="", confidence=0.5, metadata=None):
        task = self._require_task(task_id)
        self._evidence_counter += 1
        return task.add_evidence(
            evidence_id=f"evidence_{self._evidence_counter:04d}", content=content,
            provenance=provenance, source_detail=source_detail, confidence=confidence, metadata=metadata,
        )

    def add_hypothesis(self, task_id: str, content: str, *, confidence=0.5, metadata=None):
        task = self._require_task(task_id)
        self._hypothesis_counter += 1
        return task.add_hypothesis(
            hypothesis_id=f"hypothesis_{self._hypothesis_counter:04d}", content=content,
            confidence=confidence, metadata=metadata,
        )

    def add_question(self, task_id: str, question: str) -> str:
        return self._require_task(task_id).add_question(question)

    def record_action(self, task_id: str, *, action: str, status: str, result: str = "", metadata=None):
        return self._require_task(task_id).record_action(
            action=action, status=status, result=result, metadata=metadata,
        )

    def record_consultation(self, task_id: str, *, role: str, source: str, request_summary: str, response_summary: str, status="completed", metadata=None):
        task = self._require_task(task_id)
        self._consultation_counter += 1
        return task.record_consultation(
            consultation_id=f"consultation_{self._consultation_counter:04d}", role=role, source=source,
            request_summary=request_summary, response_summary=response_summary, status=status, metadata=metadata,
        )

    def record_decision(self, task_id: str, *, description: str, reason: str = "", status="proposed", metadata=None):
        task = self._require_task(task_id)
        self._decision_counter += 1
        return task.record_decision(
            decision_id=f"task_decision_{self._decision_counter:04d}", description=description,
            reason=reason, status=status, metadata=metadata,
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
            "task_capacity": self.limits.task_capacity,
            "evicted_tasks": self.evicted_tasks,
            "active_count": len(active),
            "current_task_id": current.task_id if current is not None else None,
            "per_task_limits": {
                "evidence": self.limits.task_evidence_capacity,
                "hypotheses": self.limits.task_hypothesis_capacity,
                "questions": self.limits.task_question_capacity,
                "actions": self.limits.task_action_capacity,
                "consultations": self.limits.task_consultation_capacity,
                "decisions": self.limits.task_decision_capacity,
            },
        }

    def _close(self, task_id: str, status: TaskStatus, *, outcome: str) -> TaskWorkspace:
        task = self._require_task(task_id)
        task.close(status, outcome=outcome)
        if self._current_task_id == task.task_id:
            self._current_task_id = None
        self._compact_tasks()
        return task

    def _require_task(self, task_id: str) -> TaskWorkspace:
        task = self.get(task_id)
        if task is None:
            raise KeyError(f"Unknown task: {task_id}")
        return task


__all__ = ["TaskWorkspace", "TaskWorkspaceManager"]
