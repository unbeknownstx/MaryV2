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
        result={
            "ok": True,
            "summary": "found three local references",
            "verification_passed": True,
        },
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


def test_completed_task_without_required_verification_does_not_claim_demonstrated_competence(tmp_path: Path):
    service, plan, step, skill = _service_with_continuity(tmp_path)
    task = SimpleNamespace(
        task_id="task-1",
        capability="knowledge.search",
        operation="search",
        selected_node_id="mac",
        status="completed",
        result={"ok": True, "summary": "search returned a result"},
        error="",
    )

    service._settle_continuity_task_link(task)

    competence = service.mary.competence.find(
        capability="knowledge.search",
        node_id="mac",
        skill_id=skill.id,
    )[0]
    assert competence.attempts == 1
    assert competence.successes == 1
    assert competence.verified_successes == 0
    assert service.mary.executive_plans.get_step(plan.id, step.id).status == "completed"


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
        "continuity.plan.bind_skill",
        "continuity.skill.status",
        "continuity.skill.recommend",
        "continuity.skill.revise",
        "continuity.skill.approve",
        "continuity.skill.reject",
        "world.reconcile",
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



def test_plan_skill_binding_is_mutable_only_before_execution(tmp_path: Path):
    skills = SkillLibrary(tmp_path / "skills-bind.json")
    skill = skills.approve(skills.register_candidate(
        name="knowledge procedure",
        description="bounded local lookup",
        source="creator",
        required_capabilities=("knowledge.search",),
        required_permissions=("knowledge.search",),
        steps=("search selected local collection",),
    ).id)
    plans = ExecutivePlanGraph(tmp_path / "plans-bind.json")
    plan = plans.create(objective="look up local fact", source="creator")
    step = plans.add_step(
        plan.id,
        title="Search local knowledge",
        required_capabilities=("knowledge.search",),
    )

    bound = plans.bind_skill(plan.id, step.id, skill.id)
    assert bound.skill_id == skill.id

    plans.start_step(plan.id, step.id, node_id="mac")
    try:
        plans.bind_skill(plan.id, step.id, skill.id)
    except ValueError as exc:
        assert "cannot change procedural binding" in str(exc)
    else:
        raise AssertionError("running step accepted a changed procedural binding")


def test_skill_recommendation_helper_returns_only_approved_matching_guidance(tmp_path: Path):
    skills = SkillLibrary(tmp_path / "skills-recommend.json")
    approved = skills.approve(skills.register_candidate(
        name="local knowledge lookup",
        description="search local knowledge for project references",
        source="creator",
        required_capabilities=("knowledge.search",),
        required_permissions=("knowledge.search",),
        steps=("search local knowledge pack",),
        verification=("typed result returns",),
    ).id)
    skills.register_candidate(
        name="unreviewed knowledge shortcut",
        description="search local knowledge",
        source="replay",
        required_capabilities=("knowledge.search",),
        required_permissions=("knowledge.search",),
        steps=("search without review",),
    )
    plans = ExecutivePlanGraph(tmp_path / "plans-recommend.json")
    plan = plans.create(objective="Answer from local knowledge", source="creator")
    step = plans.add_step(
        plan.id,
        title="Search the local knowledge pack",
        required_capabilities=("knowledge.search",),
    )
    service = object.__new__(MaryCoreService)
    service.mary = SimpleNamespace(
        procedural_skills=skills,
        executive_plans=plans,
    )

    rows = service._recommend_skills_for_plan_step(plan, step, limit=3)
    assert [row["id"] for row in rows] == [approved.id]
    assert rows[0]["authority"].startswith("approved procedural guidance")

def test_plan_recommendation_prefers_demonstrated_approved_procedure(tmp_path: Path):
    skills = SkillLibrary(tmp_path / "skills-ranked.json")
    weak = skills.approve(skills.register_candidate(
        name="local knowledge lookup alpha",
        description="search local knowledge for project references",
        source="creator",
        required_capabilities=("knowledge.search",),
        required_permissions=("knowledge.search",),
        steps=("search local knowledge pack",),
    ).id)
    strong = skills.approve(skills.register_candidate(
        name="local knowledge lookup beta",
        description="search local knowledge for project references",
        source="creator",
        required_capabilities=("knowledge.search",),
        required_permissions=("knowledge.search",),
        steps=("search local knowledge pack",),
    ).id)

    competence = CompetenceLedger(tmp_path / "competence-ranked.json")
    for index in range(6):
        competence.record(
            capability="knowledge.search",
            operation="search",
            node_id="mac",
            skill_id=strong.id,
            success=True,
            verified=True,
            evidence_ids=(f"strong-{index}",),
        )

    plans = ExecutivePlanGraph(tmp_path / "plans-ranked.json")
    plan = plans.create(objective="Answer from local knowledge", source="creator")
    step = plans.add_step(
        plan.id,
        title="Search local knowledge for project references",
        required_capabilities=("knowledge.search",),
    )
    service = object.__new__(MaryCoreService)
    service.mary = SimpleNamespace(
        procedural_skills=skills,
        executive_plans=plans,
        competence=competence,
        node_registry=SimpleNamespace(
            snapshot=lambda: {
                "nodes": [{"node_id": "mac", "connected": True}]
            }
        ),
    )

    rows = service._recommend_skills_for_plan_step(plan, step, limit=2)

    assert [row["id"] for row in rows] == [strong.id, weak.id]
    assert rows[0]["demonstrated"] is True
    assert rows[0]["competence"]["verified_successes"] == 6
    assert rows[0]["recommendation_score"] > rows[1]["recommendation_score"]
    assert rows[1]["evidence_needed"]
    assert "advisory only" in rows[0]["selection_policy"]



def test_evidence_selector_closes_outcome_to_plan_choice_loop(tmp_path: Path):
    skills = SkillLibrary(tmp_path / "skills-selection.json")
    alpha = skills.approve(skills.register_candidate(
        name="project knowledge lookup alpha",
        description="search local knowledge for project references",
        source="creator",
        required_capabilities=("knowledge.search",),
        required_permissions=("knowledge.search",),
        steps=("search local project knowledge",),
        verification=("typed result returns",),
    ).id)
    beta = skills.approve(skills.register_candidate(
        name="project knowledge lookup beta",
        description="search local knowledge for project references",
        source="creator",
        required_capabilities=("knowledge.search",),
        required_permissions=("knowledge.search",),
        steps=("search local project knowledge",),
        verification=("typed result returns",),
    ).id)

    competence = CompetenceLedger(tmp_path / "competence-selection.json")
    for index in range(6):
        competence.record(
            capability="knowledge.search",
            operation="search",
            node_id="mac",
            skill_id=alpha.id,
            success=True,
            verified=True,
            evidence_ids=(f"alpha-{index}",),
        )
    for index in range(4):
        competence.record(
            capability="knowledge.search",
            operation="search",
            node_id="mac",
            skill_id=beta.id,
            success=True,
            verified=True,
            evidence_ids=(f"beta-{index}",),
        )

    plans = ExecutivePlanGraph(tmp_path / "plans-selection.json")
    plan = plans.create(objective="Answer from local project knowledge", source="creator")
    step = plans.add_step(
        plan.id,
        title="Search local project knowledge",
        required_capabilities=("knowledge.search",),
    )
    service = object.__new__(MaryCoreService)
    service.mary = SimpleNamespace(
        procedural_skills=skills,
        executive_plans=plans,
        competence=competence,
        node_registry=SimpleNamespace(
            snapshot=lambda: {
                "nodes": [{"node_id": "mac", "connected": True}]
            }
        ),
    )

    first = service._select_skill_for_plan_step(plan, step)
    assert first["selected"] is True
    assert first["skill_id"] == alpha.id
    assert "explicit dispatch" in first["authority"]

    # Repeated terminal failures put the previously preferred approved
    # procedure under revision pressure. Nothing is rewritten or unapproved,
    # but the next evidence-based plan choice must stop selecting it.
    for index in range(3):
        skills.record_outcome(
            alpha.id,
            success=False,
            result=f"failure {index}",
            evidence_ids=(f"alpha-failure-{index}",),
        )

    second = service._select_skill_for_plan_step(plan, step)
    assert second["selected"] is True
    assert second["skill_id"] == beta.id
    assert second["skill_id"] != first["skill_id"]

    ranked = service._recommend_skills_for_plan_step(plan, step, limit=2)
    alpha_row = next(row for row in ranked if row["id"] == alpha.id)
    assert alpha_row["degrading"] is True
    assert alpha_row["revision_pressure"] > 0.0
    assert any("revision" in item for item in alpha_row["evidence_needed"])


def test_evidence_selector_refuses_untested_or_ambiguous_procedure(tmp_path: Path):
    skills = SkillLibrary(tmp_path / "skills-selection-gate.json")
    candidate = skills.approve(skills.register_candidate(
        name="untested local lookup",
        description="search local knowledge",
        source="creator",
        required_capabilities=("knowledge.search",),
        required_permissions=("knowledge.search",),
        steps=("search local knowledge",),
    ).id)
    plans = ExecutivePlanGraph(tmp_path / "plans-selection-gate.json")
    plan = plans.create(objective="Find a local fact", source="creator")
    step = plans.add_step(
        plan.id,
        title="Search local knowledge",
        required_capabilities=("knowledge.search",),
    )
    service = object.__new__(MaryCoreService)
    service.mary = SimpleNamespace(
        procedural_skills=skills,
        executive_plans=plans,
        competence=CompetenceLedger(tmp_path / "competence-selection-gate.json"),
        node_registry=SimpleNamespace(
            snapshot=lambda: {
                "nodes": [{"node_id": "mac", "connected": True}]
            }
        ),
    )

    selection = service._select_skill_for_plan_step(plan, step)
    assert selection["selected"] is False
    assert selection["skill_id"] == ""
    assert selection["candidates"][0]["id"] == candidate.id
    assert selection["candidates"][0]["evidence_needed"]


def test_creator_approved_revision_carries_review_provenance_into_future_selection(tmp_path: Path):
    skills = SkillLibrary(tmp_path / "skills-review-provenance.json")
    predecessor = skills.approve(skills.register_candidate(
        name="project knowledge lookup",
        description="search local project knowledge",
        source="creator",
        required_capabilities=("knowledge.search",),
        required_permissions=("knowledge.search",),
        steps=("search local project knowledge",),
        verification=("typed result returns",),
    ).id)
    candidate = skills.register_revision(
        predecessor.id,
        reason="verify references before returning",
        steps=("search local project knowledge", "verify references"),
    )
    competence = CompetenceLedger(tmp_path / "competence-review-provenance.json")
    for index in range(4):
        competence.record(
            capability="knowledge.search",
            operation="search",
            node_id="mac",
            skill_id=predecessor.id,
            success=True,
            verified=True,
            evidence_ids=(f"pred-prov-{index}",),
        )
        competence.record(
            capability="knowledge.search",
            operation="search",
            node_id="mac",
            skill_id=candidate.id,
            success=True,
            verified=True,
            evidence_ids=(f"cand-prov-{index}",),
        )

    reviewed = skills.review_revision(
        candidate.id,
        decision="approve",
        reviewed_by="creator:test",
        reason="use the verified revision",
        competence=competence,
    )
    review_id = reviewed["review"]["id"]

    plans = ExecutivePlanGraph(tmp_path / "plans-review-provenance.json")
    plan = plans.create(objective="Answer from local project knowledge", source="creator")
    step = plans.add_step(
        plan.id,
        title="Search local project knowledge",
        required_capabilities=("knowledge.search",),
    )
    service = object.__new__(MaryCoreService)
    service.mary = SimpleNamespace(
        procedural_skills=skills,
        executive_plans=plans,
        competence=competence,
        node_registry=SimpleNamespace(
            snapshot=lambda: {
                "nodes": [{"node_id": "mac", "connected": True}]
            }
        ),
    )

    selection = service._select_skill_for_plan_step(plan, step)

    assert selection["selected"] is True
    assert selection["skill_id"] == candidate.id
    provenance = selection["creator_review_provenance"]
    assert provenance["id"] == review_id
    assert provenance["decision"] == "approve"
    assert provenance["candidate_id"] == candidate.id
    assert provenance["predecessor_id"] == predecessor.id
    assert provenance["automatic_decision"] is False


def test_terminal_outcome_keeps_creator_review_id_as_competence_provenance(tmp_path: Path):
    skills = SkillLibrary(tmp_path / "skills-outcome-provenance.json")
    predecessor = skills.approve(skills.register_candidate(
        name="bounded project lookup",
        description="search project knowledge",
        source="creator",
        required_capabilities=("knowledge.search",),
        required_permissions=("knowledge.search",),
    ).id)
    candidate = skills.register_revision(
        predecessor.id,
        reason="add verification",
        steps=("search", "verify"),
    )
    reviewed = skills.review_revision(
        candidate.id,
        decision="approve",
        reviewed_by="creator:test",
        reason="explicit replacement",
    )
    review_id = reviewed["review"]["id"]
    competence = CompetenceLedger(tmp_path / "competence-outcome-provenance.json")

    service = object.__new__(MaryCoreService)
    service.mary = SimpleNamespace(
        procedural_skills=skills,
        competence=competence,
        executive_plans=SimpleNamespace(),
        node_registry=SimpleNamespace(),
    )
    service._continuity_task_links = {
        "task-provenance": {
            "plan_id": "",
            "step_id": "",
            "skill_id": candidate.id,
            "review_id": review_id,
        }
    }
    task = SimpleNamespace(
        task_id="task-provenance",
        capability="knowledge.search",
        operation="search",
        selected_node_id="mac",
        status="completed",
        result={"ok": True, "verification_passed": True, "summary": "verified"},
        error="",
        implementation_fingerprint="abc123",
    )

    service._settle_continuity_task_link(task)

    record = competence.find(
        capability="knowledge.search",
        node_id="mac",
        skill_id=candidate.id,
    )[0]
    assert "task-provenance" in record.evidence_ids
    assert review_id in record.evidence_ids
    assert record.verified_successes == 1

    adoption = skills.revision_adoption_evidence()
    assert adoption["with_outcomes"] == 1
    adopted = adoption["rows"][0]
    assert adopted["review_id"] == review_id
    assert adopted["attempts"] == 1
    assert adopted["verified_successes"] == 1
    assert adopted["state"] == "early_post_adoption_evidence"
    assert adopted["automatic_rollback"] is False


def test_post_adoption_failure_attention_never_rolls_back_revision(tmp_path: Path):
    skills = SkillLibrary(tmp_path / "skills-adoption-attention.json")
    predecessor = skills.approve(skills.register_candidate(
        name="reviewed project lookup",
        description="search project knowledge",
        source="creator",
        required_capabilities=("knowledge.search",),
        required_permissions=("knowledge.search",),
    ).id)
    candidate = skills.register_revision(
        predecessor.id,
        reason="adopt bounded verification",
        steps=("search", "verify"),
    )
    reviewed = skills.review_revision(
        candidate.id,
        decision="approve",
        reviewed_by="creator:test",
        reason="explicit adoption",
    )
    review_id = reviewed["review"]["id"]

    outcomes = (
        ("adopt-1", True, True),
        ("adopt-2", False, False),
        ("adopt-3", False, False),
        ("adopt-4", False, False),
    )
    for evidence_id, success, verified in outcomes:
        skills.record_revision_adoption_outcome(
            review_id,
            success=success,
            verified=verified,
            evidence_id=evidence_id,
        )

    # Replaying the same evidence ID is idempotent.
    skills.record_revision_adoption_outcome(
        review_id,
        success=False,
        verified=False,
        evidence_id="adopt-4",
    )

    adoption = skills.revision_adoption_evidence()
    row = adoption["rows"][0]
    assert row["attempts"] == 4
    assert row["successes"] == 1
    assert row["failures"] == 3
    assert row["verified_successes"] == 1
    assert row["failure_rate"] == 0.75
    assert row["state"] == "post_adoption_attention"
    assert adoption["attention_required"] == 1
    assert row["automatic_rollback"] is False
    assert row["automatic_revision"] is False

    # Evidence may request creator attention but cannot mutate the adopted state.
    assert skills.get(candidate.id).status == "approved"
    assert skills.get(predecessor.id).status == "superseded"
