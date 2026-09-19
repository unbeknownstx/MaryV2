from __future__ import annotations

from pathlib import Path

from mary.continuity import ExecutivePlanGraph, SkillLibrary, WorldModel


def test_world_model_keeps_contradictions_visible_until_verified(tmp_path: Path):
    world = WorldModel(tmp_path / "world.json")
    world.upsert_entity(
        label="Windows PC",
        entity_type="device",
        source="creator",
        authority="creator",
        confidence=1.0,
        aliases=("desktop",),
    )

    first = world.observe(
        subject="Windows PC",
        predicate="ollama_model",
        value="qwen3:1.7b",
        source="node_status",
        authority="runtime",
        belief_type="observation",
        confidence=0.9,
    )
    second = world.observe(
        subject="Windows PC",
        predicate="ollama_model",
        value="qwen3:4b",
        source="node_status",
        authority="runtime",
        belief_type="observation",
        confidence=0.9,
    )

    assert world.get_belief(first.id).status == "contested"
    assert world.get_belief(second.id).status == "contested"
    assert second.id in world.get_belief(first.id).contradiction_ids

    verified = world.verify(second.id, evidence_ids=("node_probe_1",), confidence=0.99)
    assert verified.verification == "verified"
    assert "node_probe_1" in verified.evidence_ids
    assert world.epistemic_summary()["known_verified"] == 1
    assert world.status()["authority"].startswith("evidence/belief")


def test_world_model_supersedes_without_erasing_history(tmp_path: Path):
    world = WorldModel(tmp_path / "world.json")
    old = world.observe(
        subject="Mary Core",
        predicate="deployment",
        value="instance-a",
        source="core",
        authority="runtime",
        verification="verified",
    )
    new = world.observe(
        subject="Mary Core",
        predicate="deployment",
        value="instance-b",
        source="core",
        authority="runtime",
        verification="verified",
        supersede_current=True,
    )

    assert world.get_belief(old.id).valid_to is not None
    assert world.get_belief(old.id).status == "retired"
    assert new.supersedes == old.id
    assert [item.value for item in world.current_beliefs(subject="Mary Core")] == ["instance-b"]


def test_skill_library_retrieves_only_approved_eligible_skills_and_learns_outcomes(tmp_path: Path):
    skills = SkillLibrary(tmp_path / "skills.json")
    candidate = skills.register_candidate(
        name="repair cross surface drift",
        description="Reconcile a shared Core status projection across PWA and Desktop.",
        source="verified_experience",
        required_capabilities=("engineering.repo.inspect",),
        required_permissions=("engineering.tests.targeted",),
        preconditions=("clean checkout",),
        inputs=("reported UI mismatch",),
        outputs=("verified patch",),
        tags=("software", "surface", "repair"),
        steps=("inspect shared owner", "patch owner first", "run convergence tests"),
        verification=("surface convergence gate passes",),
        failure_recovery=("do not publish",),
        origin_experience_ids=("exp_1", "exp_2"),
        confidence=0.7,
    )

    assert skills.retrieve(
        "repair surface",
        capabilities=("engineering.repo.inspect",),
        permissions=("engineering.tests.targeted",),
    ) == []

    approved = skills.approve(candidate.id)
    hits = skills.retrieve(
        "repair surface drift",
        capabilities=("engineering.repo.inspect",),
        permissions=("engineering.tests.targeted",),
    )
    assert [item.id for item in hits] == [approved.id]

    updated = skills.record_outcome(
        approved.id,
        success=True,
        result="convergence gate passed",
        evidence_ids=("verify_1",),
    )
    assert updated.success_count == 1
    assert updated.failure_count == 0
    assert updated.last_used_at is not None
    assert "verify_1" in updated.origin_experience_ids
    assert skills.status()["successful_uses"] == 1


def test_executive_plan_graph_survives_blockers_dependencies_and_approvals(tmp_path: Path):
    plans = ExecutivePlanGraph(tmp_path / "plans.json")
    plan = plans.create(
        objective="Ship a cohesive Mary mobile repair",
        source="creator",
        steps=("inspect", "patch"),
        priority=0.9,
        tags=("maryv2", "mobile"),
    )
    inspect, patch = plan.steps

    patch = plans._update_step(
        plan.id,
        patch.id,
        depends_on=[inspect.id],
        required_capabilities=["engineering.repo.apply"],
        required_approvals=["creator_apply"],
        verification=["tests pass"],
    )

    ready = plans.next_actions(limit=5)
    assert [item["step_id"] for item in ready] == [inspect.id]

    plans.start_step(plan.id, inspect.id, node_id="desktop")
    plans.complete_step(plan.id, inspect.id, result="evidence gathered")
    assert plans.next_actions(
        available_capabilities=("engineering.repo.apply",),
        granted_approvals=(),
    ) == []

    plans.satisfy_approval(plan.id, patch.id, "creator_apply")
    ready = plans.next_actions(
        available_capabilities=("engineering.repo.apply",),
        granted_approvals=(),
    )
    assert [item["step_id"] for item in ready] == [patch.id]

    plans.start_step(plan.id, patch.id)
    plans.complete_step(plan.id, patch.id, result="done", evidence_ids=("verify_2",))
    assert plans.get(plan.id).status == "completed"
    assert plans.status()["active_plans"] == 0


def test_plan_wait_and_restart_recovery_preserve_unfinished_work(tmp_path: Path):
    plans = ExecutivePlanGraph(tmp_path / "plans-recovery.json")
    plan = plans.create(
        objective="Use a home node without losing progress",
        source="creator",
    )
    step = plans.add_step(
        plan.id,
        title="Run local knowledge search",
        required_capabilities=("knowledge.search",),
        verification=("typed result returns",),
    )
    plans.start_step(plan.id, step.id, node_id="mac")

    recovered = plans.recover_running_steps()
    assert recovered == 1
    after_restart = plans.get_step(plan.id, step.id)
    assert after_restart.status == "waiting"
    assert after_restart.assigned_node_id == ""
    assert after_restart.blockers
    assert plans.get(plan.id).status == "waiting"

    blocker = after_restart.blockers[0]
    ready = plans.resolve_blocker(plan.id, step.id, blocker)
    assert ready.status == "ready"
    assert plans.get(plan.id).status == "active"

    plans.start_step(plan.id, step.id, node_id="mac")
    waiting = plans.wait_step(
        plan.id,
        step.id,
        reason="node timed out before terminal evidence",
        evidence_ids=("task-timeout",),
    )
    assert waiting.status == "waiting"
    assert "task-timeout" in waiting.evidence_ids
    assert plans.get(plan.id).status == "waiting"


def test_world_entity_aliases_converge_without_fuzzy_merging(tmp_path: Path):
    world = WorldModel(tmp_path / "world-aliases.json")
    entity = world.upsert_entity(
        label="DESKTOP-ATS5OPV",
        entity_type="compute_node",
        source="creator",
        authority="creator",
        confidence=1.0,
        aliases=("desktop", "my pc"),
    )
    belief = world.observe(
        subject="my pc",
        predicate="connected",
        value=True,
        source="runtime",
        authority="runtime",
        verification="verified",
    )

    assert world.resolve_entity("desktop").id == entity.id
    assert belief.subject == "DESKTOP-ATS5OPV"
    assert world.current_beliefs(subject="my pc")[0].id == belief.id
    assert world.neighborhood("desktop")[0].id == belief.id
    assert world.resolve_entity("unknown alias") is None


def test_skill_revision_keeps_approved_predecessor_until_creator_approves(tmp_path: Path):
    skills = SkillLibrary(tmp_path / "skills-revision.json")
    original = skills.approve(skills.register_candidate(
        name="search project references",
        description="Search the selected local knowledge collection.",
        source="creator",
        required_capabilities=("knowledge.search",),
        required_permissions=("knowledge.search",),
        steps=("search selected collection",),
    ).id)

    revision = skills.register_revision(
        original.id,
        reason="add verification after repeated ambiguous results",
        steps=("search selected collection", "verify source citation"),
        verification=("citation resolves to enabled document",),
    )

    assert revision.status == "candidate"
    assert revision.supersedes == original.id
    assert skills.get(original.id).status == "approved"

    approved = skills.approve(revision.id)
    assert approved.status == "approved"
    assert skills.get(original.id).status == "superseded"
    assert skills.get(original.id).superseded_by == approved.id

    hits = skills.retrieve(
        "search project references",
        capabilities=("knowledge.search",),
        permissions=("knowledge.search",),
    )
    assert [item.id for item in hits] == [approved.id]


def test_rejected_skill_revision_leaves_current_procedure_approved(tmp_path: Path):
    skills = SkillLibrary(tmp_path / "skills-reject-revision.json")
    original = skills.approve(skills.register_candidate(
        name="bounded lookup",
        description="Search local knowledge.",
        source="creator",
        required_capabilities=("knowledge.search",),
        required_permissions=("knowledge.search",),
    ).id)
    revision = skills.register_revision(
        original.id,
        reason="experiment with a different step order",
        steps=("alternate lookup",),
    )
    skills.reject(revision.id)
    assert skills.get(original.id).status == "approved"
    assert skills.get(revision.id).status == "rejected"


def test_world_reconciliation_retires_competitors_without_deleting_history(tmp_path: Path):
    world = WorldModel(tmp_path / "world-reconcile.json")
    first = world.observe(
        subject="Mary Core",
        predicate="active_instance",
        value="instance-a",
        source="runtime-a",
        authority="runtime",
        confidence=0.8,
    )
    second = world.observe(
        subject="Mary Core",
        predicate="active_instance",
        value="instance-b",
        source="runtime-b",
        authority="runtime",
        confidence=0.95,
    )
    winner = world.reconcile(second.id, resolved_by="creator")
    assert winner.status == "current"
    assert winner.verification == "verified"
    old = world.get_belief(first.id)
    assert old.status == "retired"
    assert old.valid_to is not None
    assert world.current_beliefs(subject="Mary Core", predicate="active_instance")[0].id == second.id


def test_skill_revision_queue_surfaces_failure_pressure_without_mutation(tmp_path: Path):
    skills = SkillLibrary(tmp_path / "skills-pressure.json")
    approved = skills.approve(skills.register_candidate(
        name="search local corpus",
        description="Search a bounded local knowledge pack.",
        source="creator",
        required_capabilities=("knowledge.search",),
        required_permissions=("knowledge.search",),
        steps=("search enabled pack",),
    ).id)

    skills.record_outcome(approved.id, success=False, result="citation missing", evidence_ids=("e1",))
    skills.record_outcome(approved.id, success=True, result="resolved", evidence_ids=("e2",))
    skills.record_outcome(approved.id, success=False, result="stale index", evidence_ids=("e3",))

    queue = skills.revision_queue(minimum_attempts=3, minimum_failure_rate=0.25)

    assert len(queue) == 1
    assert queue[0]["skill_id"] == approved.id
    assert queue[0]["failures"] == 2
    assert queue[0]["mutation_performed"] is False
    assert skills.get(approved.id).status == "approved"
    assert skills.status()["revision_attention"] == 1
