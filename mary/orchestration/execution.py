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
from mary.llm.interface import (
    GenerationOperation,
    GenerationRequest,
    LLMMessage,
    LLMProviderError,
    RedactionReceipt,
    _create_message_redaction_receipt,
    _create_text_redaction_receipt,
)
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
    error_code: str | None = None
    retryable: bool | None = None

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
            "error_code": self.error_code,
            "retryable": self.retryable,
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

        redacted_prompt = prompt
        redaction_receipt: RedactionReceipt | None = None
        if (
            plan.privacy == "redact_first"
            and route in {
                OrchestrationRoute.FREE_GENERATION,
                OrchestrationRoute.PRIVATE_GENERATION,
                OrchestrationRoute.EXPERT,
            }
        ):
            redactor = handlers.get("redact")
            if redactor is None:
                return self._finish(ExecutionResult(
                    task_id=task.task_id,
                    route=route.value,
                    status=ExecutionStatus.NEEDS_HANDLER.value,
                    content=(
                        "Redact-first generation requires an explicit host "
                        "redaction handler before provider dispatch."
                    ),
                    metadata={"executed": False, "required_handler": "redact"},
                ))
            try:
                redacted_prompt = clip_text(
                    str(redactor(plan)),
                    self.router.config.governance.task_text_characters,
                )
            except Exception as exc:
                return self._failure_result(
                    task_id=task.task_id,
                    route=route.value,
                    operation="redaction",
                    exc=exc,
                    metadata={"executed": True},
                )
            if not redacted_prompt.strip():
                return self._finish(ExecutionResult(
                    task_id=task.task_id,
                    route=route.value,
                    status=ExecutionStatus.BLOCKED.value,
                    content="The redaction handler returned no dispatchable context.",
                    metadata={"executed": False, "required_handler": "redact"},
                ))
            redaction_receipt = _create_text_redaction_receipt(
                redacted_prompt,
                provenance="host_handler:redact",
            )

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
                return self._failure_result(
                    task_id=task.task_id,
                    route=route.value,
                    operation=route.value,
                    exc=exc,
                    metadata={"executed": True},
                )
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
                    redacted_prompt or task.objective,
                    allow_paid=True,
                    privacy=plan.privacy,
                    deadline_seconds=self._deadline_seconds(plan),
                    structured_output=bool(
                        plan.metadata.get("structured_output", False)
                    ),
                    _redaction_receipt=redaction_receipt,
                )
            except Exception as exc:
                return self._failure_result(
                    task_id=task.task_id,
                    route=route.value,
                    operation=GenerationOperation.EXPERT_REASONING.value,
                    exc=exc,
                    metadata={"paid_allowed": True},
                )
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
            bounded_prompt = self._generation_prompt(
                task,
                prompt=redacted_prompt,
                redacted_only=redaction_receipt is not None,
            )
            try:
                generation_messages = (
                        LLMMessage(
                            role="system",
                            content=(
                                "You are a task specialist working for MaryV2. "
                                "Return task-focused analysis only. Your response is evidence/input "
                                "for Mary and does not alter durable identity or memory."
                            ),
                        ),
                        LLMMessage(role="user", content=bounded_prompt),
                )
                message_receipt = (
                    _create_message_redaction_receipt(
                        generation_messages,
                        provenance=redaction_receipt.provenance,
                    )
                    if redaction_receipt is not None
                    else None
                )
                response = self.router.generate_request(
                    GenerationRequest(
                        messages=generation_messages,
                        operation=GenerationOperation.TASK_GENERATION.value,
                        privacy=plan.privacy,
                        cost_class=plan.cost_class,
                        structured_output=bool(plan.metadata.get("structured_output", False)),
                        structured_schema_json=plan.metadata.get(
                            "structured_schema_json"
                        ),
                        redaction_receipt=message_receipt,
                        deadline_seconds=self._deadline_seconds(plan),
                        correlation_id=task.task_id,
                        purpose="task",
                    ),
                    route=(
                        "private"
                        if route == OrchestrationRoute.PRIVATE_GENERATION
                        else None
                    ),
                )
            except Exception as exc:
                return self._failure_result(
                    task_id=task.task_id,
                    route=route.value,
                    operation=GenerationOperation.TASK_GENERATION.value,
                    exc=exc,
                )
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

    def _generation_prompt(
        self,
        task,
        *,
        prompt: str | None,
        redacted_only: bool = False,
    ) -> str:
        limit = self.router.config.governance.task_text_characters
        if redacted_only:
            return clip_text(
                f"REDACTED REQUEST: {clip_text(prompt or '', limit)}",
                limit * 2,
            )
        lines = [f"TASK: {clip_text(task.objective, limit)}"]
        if prompt:
            lines.append(f"REQUEST: {clip_text(prompt, limit)}")
        evidence = task.evidence[-8:]
        if evidence:
            lines.append("EVIDENCE:")
            for item in evidence:
                lines.append(f"- [{item.provenance}] {clip_text(item.content, 1200)}")
        return clip_text("\n".join(lines), limit * 2)

    @staticmethod
    def _deadline_seconds(plan: OrchestrationPlan) -> float | None:
        value = plan.metadata.get("deadline_seconds")
        if value is None:
            return None
        try:
            return max(0.1, min(float(value), 600.0))
        except (TypeError, ValueError):
            return None

    def _failure_result(
        self,
        *,
        task_id: str,
        route: str,
        operation: str,
        exc: Exception,
        metadata: dict[str, Any] | None = None,
    ) -> ExecutionResult:
        """Normalize external failures without retaining provider/tool prose."""

        if isinstance(exc, LLMProviderError):
            error_code = exc.category
            retryable = exc.retryable
            status_code = exc.status_code
            source = exc.provider
        elif isinstance(exc, TimeoutError):
            error_code = "timeout"
            retryable = True
            status_code = None
            source = "external_capability"
        elif isinstance(exc, ConnectionError):
            error_code = "unavailable"
            retryable = True
            status_code = None
            source = "external_capability"
        elif isinstance(exc, PermissionError):
            error_code = "permission"
            retryable = False
            status_code = None
            source = "external_capability"
        else:
            error_code = "capability_failed"
            retryable = bool(getattr(exc, "retryable", False))
            status_code = None
            source = "external_capability"

        safe_metadata = dict(metadata or {})
        safe_metadata.update({
            "operation": operation,
            "failure_category": error_code,
        })
        if status_code is not None:
            safe_metadata["status_code"] = status_code
        return self._finish(ExecutionResult(
            task_id=task_id,
            route=route,
            status=ExecutionStatus.FAILED.value,
            content=f"The {operation} operation failed at its external boundary.",
            source=source,
            metadata=safe_metadata,
            error_code=error_code,
            retryable=retryable,
        ))

    def _finish(self, result: ExecutionResult) -> ExecutionResult:
        self._last_result = result
        return result


__all__ = ["ExecutionStatus", "ExecutionResult", "OrchestrationExecutor"]
