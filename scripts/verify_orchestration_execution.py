"""Verify controlled orchestration execution boundaries."""
from __future__ import annotations

from dataclasses import replace

from mary.orchestration.execution import ExecutionStatus
from mary.orchestration.orchestrator import OrchestrationRoute
from mary.runtime.application import create_application


def check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"PASS  {label}")


def main() -> int:
    print("=" * 72)
    print("MARYV2 ORCHESTRATION EXECUTION")
    print("=" * 72)
    app = create_application()
    mary = app.mary

    tool_task = mary.task_workspace.create_task(
        "Inspect a local file",
        metadata={"requires_tool": True},
    )
    tool_plan = mary.task_orchestrator.plan(
        tool_task.task_id,
        requires_tool=True,
    )
    result = mary.task_executor.execute(tool_plan)
    check(
        "tool plans never silently execute without a host handler",
        result.status == ExecutionStatus.NEEDS_HANDLER.value,
    )

    verify_task = mary.task_workspace.create_task("Verify a deterministic claim")
    verify_plan = mary.task_orchestrator.plan(
        verify_task.task_id,
        requires_verification=True,
    )
    verified = mary.task_executor.execute(
        verify_plan,
        handlers={"verify": lambda _plan: "PASS: deterministic probe"},
    )
    check(
        "verification handler result is captured as evidence",
        verified.success
        and mary.task_workspace.get(verify_task.task_id).evidence[-1].provenance
        == "test_result",
    )

    human_task = mary.task_workspace.create_task(
        "Change creator authority",
        metadata={"consequential": True},
    )
    human_plan = mary.task_orchestrator.plan(
        human_task.task_id,
        consequential=True,
    )
    blocked = mary.task_executor.execute(human_plan)
    check(
        "human-authority decisions cannot silently execute",
        blocked.status == ExecutionStatus.NEEDS_APPROVAL.value,
    )

    # An expert request without explicit paid authorization is intentionally
    # downgraded by the planner to Mary's normal free-first route. The release
    # verifier must not execute that fallback because the offline gate itself
    # should never depend on real provider/network availability.
    expert_task = mary.task_workspace.create_task(
        "Ask a paid expert",
        metadata={"needs_expert": True, "allow_paid": False},
    )
    expert_plan = mary.task_orchestrator.plan(
        expert_task.task_id,
        needs_expert=True,
        allow_paid=False,
    )
    check(
        "unauthorized expert request downgrades to free-first without paid authorization",
        expert_plan.route == OrchestrationRoute.FREE_GENERATION.value
        and expert_plan.provider_route == "free_first"
        and expert_plan.paid_allowed is False,
    )

    # Defense in depth: even if a malformed/forced plan tries to reach the
    # expert executor directly, paid_allowed=False must block before any paid
    # consultation or resource accounting can occur.
    paid_before = mary.llm.resource_governor.paid_calls
    forced_expert_plan = replace(
        expert_plan,
        route=OrchestrationRoute.EXPERT.value,
        provider_route="expert",
        capability="expert_reasoning",
        cost_class="paid_low",
        paid_allowed=False,
        requires_approval=False,
    )
    expert_result = mary.task_executor.execute(forced_expert_plan)
    check(
        "paid expert execution is blocked without task authorization",
        expert_result.status == ExecutionStatus.BLOCKED.value
        and mary.llm.resource_governor.paid_calls == paid_before,
    )

    try:
        print("=" * 72)
        print("ORCHESTRATION EXECUTION VERIFIED")
        return 0
    finally:
        app.close()


if __name__ == "__main__":
    raise SystemExit(main())
