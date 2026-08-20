"""Controlled execution for MaryV2 orchestration plans.

The executor turns a deterministic plan into one normalized result while
preserving capability/permission separation. It does not invent tool access:
research/tool/verification/local operations require an explicit host handler.
Consequential/human routes never execute automatically.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Mapping

from mary.governance.bounds import clip_text
from mary.llm.interface import LLMMessage
from mary.llm.router import LLMRouter
from mary.orchestration.consultation import ExpertConsultant
from mary.orchestration.models import ProvenanceSource
from mary.orchestration.orchestrator import OrchestrationPlan, OrchestrationRoute
from mary.orchestration.workspace import TaskWorkspaceManager


class ExecutionStatus(str, Enum):
    COMPLETED = "completed"
    NEEDS_HANDLER = "needs_handler"
    NEEDS_APPROVAL = "needs_approval"
    BLOCKED = "blocked"
    FAILED = "failed"


@dataclass(frozen=True)
class ExecutionResult:
    task_id: str
    route: str
    status: str
    content: str = ""
    source: str = "local/system"
    model: str = "n/a"
    usage: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return self.status == ExecutionStatus.COMPLETED.value

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "route": self.route,
            "status": self.status,
            "content": self.content,
            "source": self.source,
            "model": self.model,
            "usage": dict(self.usage),
            "metadata": dict(self.metadata),
        }


Handler = Callable[[OrchestrationPlan], Any]


class OrchestrationExecutor:
    """Execute explicit plans with bounded context and normalized provenance."""

    POLICY = "controlled_explicit_execution"

    def __init__(
        self,
        *,
        router: LLMRouter,
        workspace: TaskWorkspaceManager,
        expert: ExpertConsultant,
    ) -> None:
        self.router = router
        self.workspace = workspace
        self.expert = expert
        self._last_result: ExecutionResult | None = None

    def status(self) -> dict[str, Any]:
        return {
            "policy": self.POLICY,
            "silent_tool_execution": False,
            "silent_paid_execution": False,
            "human_authority_route_executes": False,
            "last_result": self._last_result.to_dict() if self._last_result else None,
        }

    def execute(
        self,
        plan: OrchestrationPlan,
        *,
        prompt: str | None = None,
        handlers: Mapping[str, Handler] | None = None,
    ) -> ExecutionResult:
        task = self.workspace.get(plan.task_id)
        if task is None:
            raise KeyError(f"Unknown task: {plan.task_id}")
        if not task.active:
            raise RuntimeError(f"Task {task.task_id} is not active.")

        route = OrchestrationRoute(plan.route)
        handlers = dict(handlers or {})

        if plan.requires_approval or route == OrchestrationRoute.HUMAN_DECISION:
            return self._finish(ExecutionResult(
                task_id=task.task_id,
                route=route.value,
                status=ExecutionStatus.NEEDS_APPROVAL.value,
                content="Creator approval/judgment is required before this plan can execute.",
                metadata={"requires_approval": True},
            ))

        if route in {
            OrchestrationRoute.LOCAL,
            OrchestrationRoute.RESEARCH,
            OrchestrationRoute.TOOL,
            OrchestrationRoute.VERIFY,
        }:
            handler = handlers.get(route.value)
            if handler is None:
                return self._finish(ExecutionResult(
                    task_id=task.task_id,
                    route=route.value,
                    status=ExecutionStatus.NEEDS_HANDLER.value,
                    content=f"The {route.value} capability requires an explicit host handler.",
                    metadata={"executed": False},
                ))
            try:
                raw = handler(plan)
            except Exception as exc:
                return self._finish(ExecutionResult(
                    task_id=task.task_id,
                    route=route.value,
                    status=ExecutionStatus.FAILED.value,
                    content=f"{type(exc).__name__}: {exc}",
                    metadata={"executed": True},
                ))
            content = clip_text(str(raw), self.router.config.governance.task_text_characters)
            result = ExecutionResult(
                task_id=task.task_id,
                route=route.value,
                status=ExecutionStatus.COMPLETED.value,
                content=content,
                source="local_tool",
                metadata={"handler": route.value},
            )
            self.workspace.record_action(
                task.task_id,
                action=route.value,
                status="completed",
                result=content,
            )
            self.workspace.add_evidence(
                task.task_id,
                content,
                provenance=(
                    ProvenanceSource.TEST_RESULT.value
                    if route == OrchestrationRoute.VERIFY
                    else ProvenanceSource.LOCAL_TOOL.value
                ),
                confidence=1.0 if route == OrchestrationRoute.VERIFY else 0.85,
            )
            return self._finish(result)

        if route == OrchestrationRoute.EXPERT:
            if not plan.paid_allowed:
                return self._finish(ExecutionResult(
                    task_id=task.task_id,
                    route=route.value,
                    status=ExecutionStatus.BLOCKED.value,
                    content="Paid expert use was not authorized for this task.",
                    metadata={"paid_allowed": False},
                ))
            try:
                consultation = self.expert.consult(
                    task.task_id,
                    prompt or task.objective,
                    allow_paid=True,
                )
            except Exception as exc:
                return self._finish(ExecutionResult(
                    task_id=task.task_id,
                    route=route.value,
                    status=ExecutionStatus.FAILED.value,
                    content=f"{type(exc).__name__}: {exc}",
                    metadata={"paid_allowed": True},
                ))
            return self._finish(ExecutionResult(
                task_id=task.task_id,
                route=route.value,
                status=ExecutionStatus.COMPLETED.value,
                content=consultation.content,
                source=consultation.provider,
                model=consultation.model,
                usage=dict(consultation.usage),
                metadata={"advisory_only": True},
            ))

        if route in {
            OrchestrationRoute.FREE_GENERATION,
            OrchestrationRoute.PRIVATE_GENERATION,
        }:
            bounded_prompt = self._generation_prompt(task, prompt=prompt)
            try:
                response = self.router.generate(
                    [
                        LLMMessage(
                            role="system",
                            content=(
                                "You are a task specialist working for MaryV2. "
                                "Return task-focused analysis only. Your response is evidence/input "
                                "for Mary and does not alter durable identity or memory."
                            ),
                        ),
                        LLMMessage(role="user", content=bounded_prompt),
                    ],
                    route=("private" if route == OrchestrationRoute.PRIVATE_GENERATION else None),
                )
            except Exception as exc:
                return self._finish(ExecutionResult(
                    task_id=task.task_id,
                    route=route.value,
                    status=ExecutionStatus.FAILED.value,
                    content=f"{type(exc).__name__}: {exc}",
                ))
            content = clip_text(response.content, self.router.config.governance.task_text_characters)
            self.workspace.record_action(
                task.task_id,
                action=route.value,
                status="completed",
                result=content,
                metadata={"provider": response.provider, "model": response.model},
            )
            provenance = (
                response.provider
                if response.provider in {item.value for item in ProvenanceSource}
                else ProvenanceSource.INFERENCE.value
            )
            self.workspace.add_evidence(
                task.task_id,
                content,
                provenance=provenance,
                source_detail=response.model,
                confidence=0.6,
                metadata={"advisory_only": True},
            )
            return self._finish(ExecutionResult(
                task_id=task.task_id,
                route=route.value,
                status=ExecutionStatus.COMPLETED.value,
                content=content,
                source=response.provider,
                model=response.model,
                usage=dict(response.usage),
            ))

        return self._finish(ExecutionResult(
            task_id=task.task_id,
            route=route.value,
            status=ExecutionStatus.BLOCKED.value,
            content="Unsupported orchestration route.",
        ))

    def _generation_prompt(self, task, *, prompt: str | None) -> str:
        limit = self.router.config.governance.task_text_characters
        lines = [f"TASK: {clip_text(task.objective, limit)}"]
        if prompt:
            lines.append(f"REQUEST: {clip_text(prompt, limit)}")
        evidence = task.evidence[-8:]
        if evidence:
            lines.append("EVIDENCE:")
            for item in evidence:
                lines.append(f"- [{item.provenance}] {clip_text(item.content, 1200)}")
        return clip_text("\n".join(lines), limit * 2)

    def _finish(self, result: ExecutionResult) -> ExecutionResult:
        self._last_result = result
        return result


__all__ = ["ExecutionStatus", "ExecutionResult", "OrchestrationExecutor"]
