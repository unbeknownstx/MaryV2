"""Verify controlled orchestration execution boundaries."""
from __future__ import annotations

from mary.core.mary import Mary
from mary.orchestration.execution import ExecutionStatus


def check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"PASS  {label}")


def main() -> int:
    print("=" * 72)
    print("MARYV2 ORCHESTRATION EXECUTION")
    print("=" * 72)
    mary = Mary()

    tool_task = mary.task_workspace.create_task("Inspect a local file", metadata={"requires_tool": True})
    tool_plan = mary.task_orchestrator.plan(tool_task.task_id, requires_tool=True)
    result = mary.task_executor.execute(tool_plan)
    check("tool plans never silently execute without a host handler", result.status == ExecutionStatus.NEEDS_HANDLER.value)

    verify_task = mary.task_workspace.create_task("Verify a deterministic claim")
    verify_plan = mary.task_orchestrator.plan(verify_task.task_id, requires_verification=True)
    verified = mary.task_executor.execute(verify_plan, handlers={"verify": lambda _plan: "PASS: deterministic probe"})
    check("verification handler result is captured as evidence", verified.success and mary.task_workspace.get(verify_task.task_id).evidence[-1].provenance == "test_result")

    human_task = mary.task_workspace.create_task("Change creator authority", metadata={"consequential": True})
    human_plan = mary.task_orchestrator.plan(human_task.task_id, consequential=True)
    blocked = mary.task_executor.execute(human_plan)
    check("human-authority decisions cannot silently execute", blocked.status == ExecutionStatus.NEEDS_APPROVAL.value)

    expert_task = mary.task_workspace.create_task("Ask a paid expert", metadata={"allow_paid": False})
    expert_plan = mary.task_orchestrator.plan(expert_task.task_id, needs_expert=True, allow_paid=False)
    expert_result = mary.task_executor.execute(expert_plan)
    check("paid expert cannot execute without task authorization", expert_result.status != ExecutionStatus.COMPLETED.value and mary.llm.resource_governor.paid_calls == 0)

    print("=" * 72)
    print("ORCHESTRATION EXECUTION VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
