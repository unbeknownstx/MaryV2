"""MaryV2 deterministic task orchestrator.

Task Orchestrator V1 decides *how* Mary should approach one ephemeral task.
It does not execute providers, tools, writes, or external actions itself.

The planner keeps five concerns explicit:
    - capability: what kind of help the task needs
    - privacy: what may leave the local process
    - cost: zero/local, free cloud, paid expert, or human review
    - verification: whether claims should be tested before acceptance
    - authority: when the creator must remain the decision maker

Paid expert use is intentionally opt-in per task. Merely installing or funding
OpenAI never allows this planner to spend credits by itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from mary.llm.router import LLMRouter
from mary.orchestration.workspace import TaskWorkspaceManager


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


class PrivacyMode(str, Enum):
    """How task context may leave Mary's local process."""

    LOCAL_ONLY = "local_only"
    CLOUD_OK = "cloud_ok"
    REDACT_FIRST = "redact_first"
    APPROVAL_REQUIRED = "approval_required"


class OrchestrationRoute(str, Enum):
    """High-level route selected for a task."""

    LOCAL = "local"
    FREE_GENERATION = "free_generation"
    PRIVATE_GENERATION = "private_generation"
    RESEARCH = "research"
    TOOL = "tool"
    VERIFY = "verify"
    EXPERT = "expert"
    HUMAN_DECISION = "human_decision"


class CapabilityRole(str, Enum):
    """Capability Mary wants, independent of provider brand."""

    DETERMINISTIC = "deterministic"
    FAST_GENERATION = "fast_generation"
    PRIVATE_GENERATION = "private_generation"
    RESEARCH = "research"
    TOOL_USE = "tool_use"
    VERIFICATION = "verification"
    EXPERT_REASONING = "expert_reasoning"
    HUMAN_JUDGMENT = "human_judgment"


class CostClass(str, Enum):
    """Expected resource-cost class for a planned route."""

    ZERO_LOCAL = "zero_local"
    FREE_CLOUD = "free_cloud"
    PAID_LOW = "paid_low"
    HUMAN = "human"


@dataclass(frozen=True)
class OrchestrationPlan:
    """Deterministic plan for one active task."""

    task_id: str
    route: str
    capability: str
    privacy: str
    cost_class: str
    provider_route: str | None = None
    requires_approval: bool = False
    paid_allowed: bool = False
    should_verify: bool = False
    rationale: tuple[str, ...] = ()
    created_at: str = field(default_factory=_timestamp)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "route": self.route,
            "capability": self.capability,
            "privacy": self.privacy,
            "cost_class": self.cost_class,
            "provider_route": self.provider_route,
            "requires_approval": self.requires_approval,
            "paid_allowed": self.paid_allowed,
            "should_verify": self.should_verify,
            "rationale": list(self.rationale),
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
        }


class TaskOrchestrator:
    """Plan task routing without silently performing the planned work."""

    PAID_POLICY = "explicit_task_opt_in"
    EXECUTION_POLICY = "plan_only_no_silent_execution"

    _LOCAL_SENSITIVE_TERMS = (
        "api key",
        "api_key",
        "password",
        "credential",
        "secret",
        ".env",
        "private memory",
        "confidential",
    )
    _RESEARCH_TERMS = (
        "latest",
        "current",
        "today",
        "research",
        "search the web",
        "look up",
        "lookup",
    )
    _VERIFY_TERMS = (
        "verify",
        "test this",
        "run tests",
        "prove",
        "reproduce",
        "confirm with a test",
    )
    _HUMAN_AUTHORITY_TERMS = (
        "change mary's values",
        "change marys values",
        "change mary's identity",
        "change marys identity",
        "change creator permissions",
        "change security policy",
        "spend money",
        "purchase",
        "send the email",
        "delete the file",
    )

    def __init__(
        self,
        *,
        workspace: TaskWorkspaceManager,
        router: LLMRouter,
    ) -> None:
        self.workspace = workspace
        self.router = router
        self._last_plan: OrchestrationPlan | None = None

    def status(self) -> dict[str, Any]:
        return {
            "planning": "deterministic",
            "execution_policy": self.EXECUTION_POLICY,
            "paid_policy": self.PAID_POLICY,
            "free_route": "free_first",
            "private_route": "private",
            "expert_route": "expert",
            "last_plan": (
                self._last_plan.to_dict()
                if self._last_plan is not None
                else None
            ),
        }

    def plan(
        self,
        task_id: str,
        *,
        privacy: str | PrivacyMode | None = None,
        allow_paid: bool | None = None,
        requires_current_info: bool | None = None,
        requires_tool: bool | None = None,
        requires_verification: bool | None = None,
        needs_expert: bool | None = None,
        consequential: bool | None = None,
        local_capable: bool | None = None,
    ) -> OrchestrationPlan:
        task = self.workspace.get(task_id)
        if task is None:
            raise KeyError(f"Unknown task: {task_id}")
        if not task.active:
            raise RuntimeError(
                f"Task {task.task_id} is {task.status.value} and cannot be planned."
            )

        objective = task.objective.strip()
        lowered = objective.lower()
        metadata = dict(task.metadata)

        privacy_mode = self._privacy_mode(
            explicit=privacy,
            metadata=metadata,
            objective=lowered,
        )
        paid_allowed = self._bool_option(
            allow_paid,
            metadata.get("allow_paid"),
            default=False,
        )
        current_info = self._bool_option(
            requires_current_info,
            metadata.get("requires_current_info", metadata.get("research")),
            default=self._contains_any(lowered, self._RESEARCH_TERMS),
        )
        tool_needed = self._bool_option(
            requires_tool,
            metadata.get("requires_tool"),
            default=False,
        )
        verify_needed = self._bool_option(
            requires_verification,
            metadata.get("requires_verification", metadata.get("verification")),
            default=self._contains_any(lowered, self._VERIFY_TERMS),
        )
        expert_needed = self._bool_option(
            needs_expert,
            metadata.get("needs_expert"),
            default=False,
        )
        human_required = self._bool_option(
            consequential,
            metadata.get("consequential"),
            default=self._contains_any(lowered, self._HUMAN_AUTHORITY_TERMS),
        )
        deterministic_local = self._bool_option(
            local_capable,
            metadata.get("local_capable"),
            default=False,
        )

        rationale: list[str] = []

        if human_required or privacy_mode == PrivacyMode.APPROVAL_REQUIRED:
            route = OrchestrationRoute.HUMAN_DECISION
            capability = CapabilityRole.HUMAN_JUDGMENT
            cost = CostClass.HUMAN
            provider_route = None
            requires_approval = True
            rationale.append(
                "The task crosses a creator-authority or explicit-approval boundary."
            )

        elif privacy_mode == PrivacyMode.LOCAL_ONLY:
            if deterministic_local:
                route = OrchestrationRoute.LOCAL
                capability = CapabilityRole.DETERMINISTIC
            else:
                route = OrchestrationRoute.PRIVATE_GENERATION
                capability = CapabilityRole.PRIVATE_GENERATION
            cost = CostClass.ZERO_LOCAL
            provider_route = "private"
            requires_approval = False
            rationale.append(
                "Sensitive/private task context is kept on the local Ollama route."
            )

        elif tool_needed:
            route = OrchestrationRoute.TOOL
            capability = CapabilityRole.TOOL_USE
            cost = CostClass.ZERO_LOCAL
            provider_route = None
            requires_approval = False
            rationale.append("The task explicitly requires a tool capability.")

        elif current_info:
            route = OrchestrationRoute.RESEARCH
            capability = CapabilityRole.RESEARCH
            cost = CostClass.FREE_CLOUD
            provider_route = None
            requires_approval = privacy_mode == PrivacyMode.REDACT_FIRST
            rationale.append(
                "The task depends on current/external information rather than model memory."
            )
            if privacy_mode == PrivacyMode.REDACT_FIRST:
                rationale.append("Outbound context must be minimized/redacted first.")

        elif verify_needed:
            route = OrchestrationRoute.VERIFY
            capability = CapabilityRole.VERIFICATION
            cost = CostClass.ZERO_LOCAL
            provider_route = None
            requires_approval = False
            rationale.append(
                "A testable claim should be checked with evidence/tools before acceptance."
            )

        elif deterministic_local:
            route = OrchestrationRoute.LOCAL
            capability = CapabilityRole.DETERMINISTIC
            cost = CostClass.ZERO_LOCAL
            provider_route = None
            requires_approval = False
            rationale.append("The task is marked as solvable by Mary's local deterministic systems.")

        elif expert_needed and paid_allowed:
            route = OrchestrationRoute.EXPERT
            capability = CapabilityRole.EXPERT_REASONING
            cost = CostClass.PAID_LOW
            provider_route = "expert"
            requires_approval = privacy_mode == PrivacyMode.REDACT_FIRST
            rationale.append(
                "The task requests specialist reasoning and paid expert use was explicitly allowed."
            )
            if privacy_mode == PrivacyMode.REDACT_FIRST:
                rationale.append("Only redacted/minimum necessary context may be consulted externally.")

        else:
            route = OrchestrationRoute.FREE_GENERATION
            capability = CapabilityRole.FAST_GENERATION
            cost = CostClass.FREE_CLOUD
            provider_route = "free_first"
            requires_approval = privacy_mode == PrivacyMode.REDACT_FIRST
            if expert_needed and not paid_allowed:
                rationale.append(
                    "Expert reasoning was requested, but paid use is not authorized for this task."
                )
                rationale.append(
                    "Use the free-first model team or request explicit paid escalation."
                )
            else:
                rationale.append(
                    "No stronger local/tool/research/expert requirement was established; use free-first generation."
                )
            if privacy_mode == PrivacyMode.REDACT_FIRST:
                rationale.append("Outbound context must be minimized/redacted first.")

        plan = OrchestrationPlan(
            task_id=task.task_id,
            route=route.value,
            capability=capability.value,
            privacy=privacy_mode.value,
            cost_class=cost.value,
            provider_route=provider_route,
            requires_approval=requires_approval,
            paid_allowed=paid_allowed,
            should_verify=verify_needed,
            rationale=tuple(rationale),
            metadata={
                "planner": "task_orchestrator_v1",
                "executes_actions": False,
                "structured_output": bool(metadata.get("structured_output", False)),
                "structured_schema_json": metadata.get("structured_schema_json"),
                "deadline_seconds": self._bounded_deadline(
                    metadata.get("deadline_seconds")
                ),
            },
        )

        self.workspace.record_decision(
            task.task_id,
            description=(
                f"Plan task via {plan.route} using {plan.capability}."
            ),
            reason=" ".join(plan.rationale),
            status="planned",
            metadata={
                "orchestration_plan": plan.to_dict(),
                "advisory": True,
            },
        )
        self._last_plan = plan
        return plan

    @staticmethod
    def _bounded_deadline(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return max(0.1, min(float(value), 600.0))
        except (TypeError, ValueError):
            return None

    @classmethod
    def _contains_any(cls, text: str, terms: tuple[str, ...]) -> bool:
        return any(term in text for term in terms)

    @staticmethod
    def _bool_option(
        explicit: bool | None,
        metadata_value: Any,
        *,
        default: bool,
    ) -> bool:
        if explicit is not None:
            return bool(explicit)
        if isinstance(metadata_value, bool):
            return metadata_value
        if metadata_value is not None:
            value = str(metadata_value).strip().lower()
            if value in {"1", "true", "yes", "on"}:
                return True
            if value in {"0", "false", "no", "off"}:
                return False
        return bool(default)

    def _privacy_mode(
        self,
        *,
        explicit: str | PrivacyMode | None,
        metadata: dict[str, Any],
        objective: str,
    ) -> PrivacyMode:
        if explicit is not None:
            return self._coerce_privacy(explicit)

        metadata_value = metadata.get("privacy")
        if metadata_value is not None:
            return self._coerce_privacy(metadata_value)

        if self._contains_any(objective, self._LOCAL_SENSITIVE_TERMS):
            return PrivacyMode.LOCAL_ONLY

        return PrivacyMode.CLOUD_OK

    @staticmethod
    def _coerce_privacy(value: str | PrivacyMode) -> PrivacyMode:
        if isinstance(value, PrivacyMode):
            return value
        normalized = str(value).strip().lower()
        aliases = {
            "private": PrivacyMode.LOCAL_ONLY,
            "local": PrivacyMode.LOCAL_ONLY,
            "offline": PrivacyMode.LOCAL_ONLY,
            "cloud": PrivacyMode.CLOUD_OK,
            "redact": PrivacyMode.REDACT_FIRST,
            "approval": PrivacyMode.APPROVAL_REQUIRED,
        }
        if normalized in aliases:
            return aliases[normalized]
        return PrivacyMode(normalized)


__all__ = [
    "PrivacyMode",
    "OrchestrationRoute",
    "CapabilityRole",
    "CostClass",
    "OrchestrationPlan",
    "TaskOrchestrator",
]
