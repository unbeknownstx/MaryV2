from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from mary.continuity import CompetenceLedger, ExecutivePlanGraph, SkillLibrary
from mary.core.service import MaryCoreService
from mary.protocol.models import RuntimeActionRequest


def _service_with_continuity(tmp_path: Path):
    skills = SkillLibrary(tmp_path / "skills.json")
    skill = skills.register_candidate(
        name="local knowledge lookup",
        description="Use one bounded node-local knowledge search.",
        source="creator",
        required_capabilities=("knowledge.search",),
        required_permissions=("knowledge.search",),
        steps=("search local pack",),
        verification=("typed result returns",),
    )
    skill = skills.approve(skill.id)

    plans = ExecutivePlanGraph(tmp_path / "plans.json")
    plan = plans.create(objective="Answer from local knowledge", source="creator")
    step = plans.add_step(
        plan.id,
        title="Search the local knowledge pack",
        required_capabilities=("knowledge.search",),
        verification=("typed result returns",),
        skill_id=skill.id,
    )
    plans.start_step(plan.id, step.id, node_id="mac")

    service = object.__new__(MaryCoreService)
    service.mary = SimpleNamespace(
        procedural_skills=skills,
        executive_plans=plans,
        competence=CompetenceLedger(tmp_path / "competence.json"),
    )
    service._continuity_task_links = {
        "task-1": {
            "plan_id": plan.id,
            "step_id": step.id,
            "skill_id": skill.id,
        }
    }
    return service, plan, step, skill


def test_terminal_task_settles_plan_skill_and_skill_specific_competence(tmp_path: Path):
    service, plan, step, skill = _service_with_continuity(tmp_path)
    task = SimpleNamespace(
        task_id="task-1",
        capability="knowledge.search",
        operation="search",
        selected_node_id="mac",
        status="completed",
        result={"ok": True, "summary": "found three local references"},
        error="",
    )

    service._settle_continuity_task_link(task)

    assert "task-1" not in service._continuity_task_links
    assert service.mary.executive_plans.get_step(plan.id, step.id).status == "completed"
    assert service.mary.executive_plans.get(plan.id).status == "completed"

    updated_skill = service.mary.procedural_skills.get(skill.id)
    assert updated_skill.success_count == 1
    assert updated_skill.failure_count == 0

    competence = service.mary.competence.find(
        capability="knowledge.search",
        node_id="mac",
        skill_id=skill.id,
    )[0]
    assert competence.attempts == 1
    assert competence.verified_successes == 1


def test_failed_linked_task_waits_for_creator_recovery_instead_of_erasing_plan(tmp_path: Path):
    service, plan, step, skill = _service_with_continuity(tmp_path)
    task = SimpleNamespace(
        task_id="task-1",
        capability="knowledge.search",
        operation="search",
        selected_node_id="mac",
        status="failed",
        result={},
        error="node became unavailable",
    )

    service._settle_continuity_task_link(task)

    waiting = service.mary.executive_plans.get_step(plan.id, step.id)
    assert waiting.status == "waiting"
    assert waiting.blockers
    assert service.mary.executive_plans.get(plan.id).status == "waiting"
    updated_skill = service.mary.procedural_skills.get(skill.id)
    assert updated_skill.failure_count == 1


def test_plan_runtime_actions_are_typed_but_arbitrary_execution_is_still_rejected():
    for name in (
        "continuity.plan.status",
        "continuity.plan.create",
        "continuity.plan.add_step",
        "continuity.plan.satisfy_approval",
        "continuity.plan.resolve_blocker",
        "continuity.plan.next",
        "continuity.plan.dispatch",
    ):
        parsed = RuntimeActionRequest.from_dict({
            "action": name,
            "args": {},
            "device_id": "iphone",
        })
        assert parsed.action == name
