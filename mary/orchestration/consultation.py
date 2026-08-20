"""MaryV2 external expert consultation bridge.

A consultation is intentionally task-local. The specialist may propose or
criticize, but its output cannot mutate Mary's durable memory, identity,
creator model, preferences, or developed self through this bridge.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from mary.llm.interface import LLMMessage
from mary.llm.router import LLMRouter
from mary.orchestration.models import ProvenanceSource
from mary.orchestration.workspace import TaskWorkspaceManager


@dataclass(frozen=True)
class ExpertConsultationResult:
    """Normalized result returned to Mary's task workspace."""

    provider: str
    model: str
    role: str
    content: str
    finish_reason: str | None = None
    usage: dict[str, Any] = field(default_factory=dict)
    provider_attempts: tuple[dict[str, str], ...] = ()


class ExpertConsultant:
    """Ask an intentionally selected paid/expert model for task-local help."""

    def __init__(
        self,
        router: LLMRouter,
        workspace: TaskWorkspaceManager,
    ) -> None:
        self.router = router
        self.workspace = workspace

    def status(self) -> dict[str, Any]:
        order = self.router._provider_order(None, route="expert")
        provider = order[0] if order else "unknown"
        return {
            "route": "expert",
            "provider": provider,
            "model": self.router.model_name(provider),
            "available": self.router.is_available(route="expert"),
            "persistence": "task_workspace_only",
            "authority": "advisory_only",
            "paid_policy": "explicit_task_authorization",
            "paid_calls_per_task": self.router.config.governance.paid_calls_per_task,
        }

    def consult(
        self,
        task_id: str,
        question: str,
        *,
        role: str = "expert_reasoning",
        context: Iterable[str] = (),
        max_evidence: int = 8,
        max_tokens: int | None = None,
        allow_paid: bool | None = None,
    ) -> ExpertConsultationResult:
        task = self.workspace.get(task_id)
        if task is None:
            raise KeyError(f"Unknown task: {task_id}")
        if not task.active:
            raise RuntimeError(
                f"Task {task.task_id} is {task.status.value} and cannot be consulted."
            )

        paid_authorized = (
            bool(task.metadata.get("allow_paid", False))
            if allow_paid is None
            else bool(allow_paid)
        )
        if not paid_authorized:
            raise PermissionError(
                "Paid expert consultation is disabled for this task. "
                "Set task metadata allow_paid=True or explicitly authorize this consultation."
            )

        governor = self.router.resource_governor
        if not governor.reserve_paid_call(task.task_id):
            raise RuntimeError(
                f"Paid-call budget exhausted for {task.task_id}; "
                f"limit={governor.limits.paid_calls_per_task}."
            )

        prompt = self._build_prompt(
            task_id=task_id,
            question=question,
            context=context,
            max_evidence=max_evidence,
        )

        response = self.router.generate(
            [
                LLMMessage(
                    role="system",
                    content=(
                        "You are an external specialist consulting for MaryV2. "
                        "Analyze the bounded task context and return useful "
                        "criticism, reasoning, or recommendations. Do not "
                        "roleplay as Mary. Do not claim to mutate Mary's memory, "
                        "identity, preferences, creator model, permissions, or "
                        "durable state. Your output is advisory evidence for "
                        "Mary to evaluate."
                    ),
                ),
                LLMMessage(role="user", content=prompt),
            ],
            route="expert",
            max_tokens=min(
                int(max_tokens or self.router.config.governance.expert_max_output_tokens),
                int(self.router.config.governance.expert_max_output_tokens),
            ),
        )

        attempts = tuple(
            dict(item)
            for item in self.router.last_generation_attempts
        )
        normalized_role = str(role).strip().lower() or "expert_reasoning"

        self.workspace.record_consultation(
            task_id,
            role=normalized_role,
            source=response.provider,
            request_summary=str(question).strip(),
            response_summary=response.content,
            status="completed",
            metadata={
                "model": response.model,
                "finish_reason": response.finish_reason,
                "usage": dict(response.usage),
                "provider_attempts": [dict(item) for item in attempts],
            },
        )

        provenance = (
            response.provider
            if response.provider in {item.value for item in ProvenanceSource}
            else ProvenanceSource.INFERENCE.value
        )
        self.workspace.add_evidence(
            task_id,
            response.content,
            provenance=provenance,
            source_detail=f"{normalized_role}:{response.model}",
            confidence=0.6,
            metadata={
                "consultation": True,
                "advisory_only": True,
            },
        )

        return ExpertConsultationResult(
            provider=response.provider,
            model=response.model,
            role=normalized_role,
            content=response.content,
            finish_reason=response.finish_reason,
            usage=dict(response.usage),
            provider_attempts=attempts,
        )

    def _build_prompt(
        self,
        *,
        task_id: str,
        question: str,
        context: Iterable[str],
        max_evidence: int,
    ) -> str:
        task = self.workspace.get(task_id)
        if task is None:
            raise KeyError(f"Unknown task: {task_id}")

        lines = [
            f"TASK OBJECTIVE:\n{task.objective}",
            f"\nQUESTION FOR THE SPECIALIST:\n{str(question).strip()}",
        ]

        bounded_context = [
            str(item).strip()
            for item in context
            if str(item).strip()
        ]
        if bounded_context:
            lines.append("\nEXPLICIT TASK CONTEXT:")
            for item in bounded_context[:8]:
                lines.append(f"- {item[:1600]}")

        evidence = task.evidence[-max(0, int(max_evidence)) :]
        if evidence:
            lines.append("\nCURRENT TASK EVIDENCE:")
            for item in evidence:
                lines.append(
                    f"- [{item.provenance}] {item.content[:1600]}"
                )

        lines.append(
            "\nReturn a concise expert analysis. Distinguish facts, "
            "assumptions, risks, and recommendations when relevant."
        )
        return "\n".join(lines)


__all__ = [
    "ExpertConsultant",
    "ExpertConsultationResult",
]
