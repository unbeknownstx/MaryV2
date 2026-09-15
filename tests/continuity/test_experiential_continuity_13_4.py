from __future__ import annotations

from pathlib import Path

from mary.continuity import (
    ActionAffordance,
    ActionVerificationManager,
    AffordanceScorer,
    ComputeResourceGovernor,
    DurableWorkflowStore,
    ExperienceLedger,
    ExperientialContinuityRuntime,
    ProsodyObservation,
    ResourceSnapshot,
    SkillLibrary,
    TemporalKnowledgeGraph,
    TurnTakingAdvisor,
)


def test_temporal_graph_supersedes_current_without_erasing_history(tmp_path: Path):
    graph = TemporalKnowledgeGraph(tmp_path / "temporal.json")
    old = graph.record(
        subject="MaryV2",
        predicate="deployed_on",
        value="Railway",
        source="creator",
        authority="verified",
    )
    new = graph.record(
        subject="MaryV2",
        predicate="deployed_on",
        value="HomeServer",
        source="deployment_probe",
        authority="verified",
    )
    assert new.supersedes == old.id
    assert [item.value for item in graph.current(subject="MaryV2")] == ["HomeServer"]
    history = graph.history(subject="MaryV2", predicate="deployed_on")
    assert [item.value for item in history] == ["Railway", "HomeServer"]
    assert history[0].valid_to is not None


def test_experience_consolidation_only_creates_candidates(tmp_path: Path):
    ledger = ExperienceLedger(tmp_path / "experience.json")
    for index in range(3):
        ledger.record(
            kind="project",
            summary=f"Mary deployment event {index}",
            source="verified_test",
            importance=0.9 if index == 0 else 0.6,
            tags=["deployment"],
        )
    candidates = ledger.consolidate()
    assert {candidate.candidate_type for candidate in candidates} == {"reflection", "pattern"}
    assert all(candidate.status == "candidate" for candidate in candidates)
    assert ledger.status()["promotion"] == "explicit/governed only"
    assert ledger.consolidate() == []


def test_skill_library_requires_explicit_approval_and_capability_match(tmp_path: Path):
    library = SkillLibrary(tmp_path / "skills.json")
    skill = library.register_candidate(
        name="verify mary deployment",
        description="Probe health after deployment.",
        source="creator",
        required_capabilities=["http_probe"],
        required_permissions=["network_read"],
        steps=["probe /health", "confirm expected version"],
        verification=["HTTP 200", "version matches"],
    )
    assert library.eligible(capabilities=["http_probe"], permissions=["network_read"]) == []
    library.approve(skill.id, approved_by="creator")
    assert len(library.eligible(capabilities=["http_probe"], permissions=["network_read"])) == 1
    assert library.eligible(capabilities=[], permissions=["network_read"]) == []


def test_durable_workflow_can_resume_after_restart(tmp_path: Path):
    path = tmp_path / "workflows.json"
    store = DurableWorkflowStore(path)
    workflow = store.create(
        objective="Deploy Mary",
        steps=["build", "deploy", "verify"],
        source="creator",
    )
    store.start(workflow.id)
    after_step = store.complete_step(workflow.id, result="build ok")
    assert after_step.current_step == 1

    reloaded = DurableWorkflowStore(path)
    resumed = reloaded.get(workflow.id)
    assert resumed.current_step == 1
    assert resumed.completed_steps == (0,)
    assert resumed.status == "running"


def test_closed_loop_verification_does_not_equate_tool_result_with_success(tmp_path: Path):
    manager = ActionVerificationManager(tmp_path / "verification.json")
    record = manager.begin(
        intent="start ollama",
        action_type="service.start",
        expected_state={"endpoint_ok": True},
        source="creator_task",
    )
    accepted = manager.record_action_result(record.id, result="process started")
    assert accepted.verdict == "pending"
    failed = manager.verify(record.id, observation={"endpoint_ok": False})
    assert failed.verdict == "failed"


def test_affordance_scorer_blocks_without_permission_and_ranks_eligible():
    scorer = AffordanceScorer()
    blocked = scorer.score(
        ActionAffordance(
            action="render_video",
            available=True,
            permission_granted=False,
            readiness="ready",
            confidence=0.95,
            risk="low",
            estimated_latency_ms=1000,
            estimated_cost=0.0,
        )
    )
    assert blocked["eligible"] is False
    assert blocked["reason"] == "permission_required"

    eligible = scorer.score(
        ActionAffordance(
            action="local_inference",
            available=True,
            permission_granted=True,
            readiness="ready",
            confidence=0.95,
            risk="low",
            estimated_latency_ms=500,
            estimated_cost=0.0,
        )
    )
    assert eligible["eligible"] is True
    assert eligible["score"] > 0.8


def test_compute_governor_prefers_ready_node_with_headroom(tmp_path: Path):
    governor = ComputeResourceGovernor(tmp_path / "resources.json")
    governor.update(
        ResourceSnapshot(
            node_id="mac",
            readiness="degraded",
            captured_at="2026-09-10T00:00:00+00:00",
            vram_total_mb=8000,
            vram_used_mb=7000,
            cpu_load=0.8,
            gpu_load=0.9,
        )
    )
    governor.update(
        ResourceSnapshot(
            node_id="windows-3090",
            readiness="ready",
            captured_at="2026-09-10T00:00:00+00:00",
            vram_total_mb=24576,
            vram_used_mb=4096,
            cpu_load=0.2,
            gpu_load=0.1,
        )
    )
    assert governor.recommend_node(required_vram_mb=12000) == "windows-3090"


def test_prosody_is_acoustic_advice_not_emotion_inference():
    advisor = TurnTakingAdvisor()
    result = advisor.assess(
        ProsodyObservation(
            speech_rate_wpm=210,
            pause_ms=700,
            rms_ratio=2.0,
            terminal_pitch_slope=-0.4,
        )
    )
    assert result["likely_finished"] is True
    assert result["fast_delivery"] is True
    assert result["energetic_delivery"] is True
    assert "emotion" not in result
    assert "mental" in result["policy"]


def test_runtime_composes_all_new_owners_without_claiming_identity_authority(tmp_path: Path):
    runtime = ExperientialContinuityRuntime(tmp_path / "continuity")
    status = runtime.status()
    assert status["version"] == "13.4"
    assert all(value is False for value in status["authority"].values())
    assert runtime.maintenance()["promotion_performed"] is False


def test_reflex_lane_can_react_immediately_without_becoming_second_cognition_owner():
    from mary.continuity import CognitionLaneRouter
    router = CognitionLaneRouter()
    decision = router.decide(event_type="creator_turn", direct_address=True, complexity=0.8)
    assert decision.reflex is True
    assert decision.deliberative is True
    assert "orient_to_speaker" in decision.reflex_cues
    assert "TurnMind" in router.status()["policy"]


def test_provider_neutral_cancellation_registry_is_cooperative():
    from mary.continuity import GenerationCancellationRegistry
    registry = GenerationCancellationRegistry()
    handle = registry.create(correlation_id="turn-1")
    assert registry.cancelled(handle.id) is False
    assert registry.cancel_correlation("turn-1") is True
    assert registry.cancelled(handle.id) is True
    registry.complete(handle.id)
    assert registry.cancelled(handle.id) is False


def test_node_recovery_progresses_from_degraded_to_recovering(tmp_path: Path):
    from mary.continuity import NodeRecoveryManager
    recovery = NodeRecoveryManager(tmp_path / "recovery.json")
    first = recovery.observe("mac", healthy=False, reason="ollama timeout")
    second = recovery.observe("mac", healthy=False, reason="ollama timeout")
    assert first.state == "degraded"
    assert second.state == "recovering"
    assert "restart_capability_service" in recovery.recommended_steps("mac")
    healthy = recovery.observe("mac", healthy=True)
    assert healthy.state == "active"
    assert healthy.failure_count == 0


def test_memory_lab_detects_forbidden_evidence():
    from mary.continuity import MemoryEvaluationSuite
    suite = MemoryEvaluationSuite()
    case = next(item for item in suite.default_cases() if item.id == "privacy_public")
    failed = suite.evaluate(case, ["public_allowed", "creator_private"])
    assert failed["passed"] is False
    assert failed["violations"] == ["creator_private"]
    passed = suite.evaluate(case, ["public_allowed"])
    assert passed["passed"] is True
