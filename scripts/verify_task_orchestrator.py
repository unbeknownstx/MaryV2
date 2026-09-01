"""Verify MaryV2 Task Orchestrator V1 installation."""

from __future__ import annotations

from mary.runtime.application import create_application


def _pass(message: str) -> None:
    print(f"PASS {message}")


def main() -> int:
    print("=" * 72)
    print("MARY V2 TASK ORCHESTRATOR V1")
    print("=" * 72)

    app = create_application()
    mary = app.mary
    planner = mary.task_orchestrator
    workspace = mary.task_workspace

    ordinary = workspace.create_task(
        "Draft a concise architecture explanation",
        make_current=False,
    )
    free_plan = planner.plan(ordinary.task_id)
    assert free_plan.route == "free_generation"
    assert free_plan.provider_route == "free_first"
    _pass("ordinary model work selects the existing free-first route")

    private = workspace.create_task(
        "Review this private memory and API key handling",
        metadata={"needs_expert": True, "allow_paid": True},
        make_current=False,
    )
    private_plan = planner.plan(private.task_id)
    assert private_plan.route == "private_generation"
    assert private_plan.provider_route == "private"
    _pass("privacy wins over paid capability and keeps sensitive work local")

    research = workspace.create_task(
        "Find the latest provider documentation",
        make_current=False,
    )
    research_plan = planner.plan(research.task_id)
    assert research_plan.route == "research"
    _pass("current-information tasks select research instead of model guessing")

    verify = workspace.create_task(
        "Run tests and verify the routing guarantee",
        make_current=False,
    )
    verify_plan = planner.plan(verify.task_id)
    assert verify_plan.route == "verify"
    assert verify_plan.should_verify is True
    _pass("testable claims select verification/evidence before acceptance")

    blocked = workspace.create_task(
        "Critique this difficult architecture",
        metadata={"needs_expert": True},
        make_current=False,
    )
    blocked_plan = planner.plan(blocked.task_id)
    assert blocked_plan.route == "free_generation"
    assert blocked_plan.paid_allowed is False
    _pass("paid expert use stays blocked unless the individual task opts in")

    paid = workspace.create_task(
        "Critique this difficult architecture",
        metadata={"needs_expert": True, "allow_paid": True},
        make_current=False,
    )
    paid_plan = planner.plan(paid.task_id)
    assert paid_plan.route == "expert"
    assert paid_plan.provider_route == "expert"
    _pass("explicitly approved specialist work can select the paid expert route")

    authority = workspace.create_task(
        "Change Mary's values to match a model suggestion",
        make_current=False,
    )
    authority_plan = planner.plan(authority.task_id)
    assert authority_plan.route == "human_decision"
    assert authority_plan.requires_approval is True
    _pass("creator-authority boundaries route consequential changes to Unbe")

    assert all(task.decisions for task in workspace.list_tasks())
    _pass("every orchestration plan is recorded as task-local rationale")

    status = mary.status()["orchestration"]["task_orchestrator"]
    assert status["planning"] == "deterministic"
    assert status["paid_policy"] == "explicit_task_opt_in"
    assert status["execution_policy"] == "plan_only_no_silent_execution"
    _pass("runtime status exposes cost/authority safeguards")

    try:
        print("=" * 72)
        print("TASK ORCHESTRATOR V1 INSTALLED CORRECTLY")
        return 0
    finally:
        app.close()


if __name__ == "__main__":
    raise SystemExit(main())
