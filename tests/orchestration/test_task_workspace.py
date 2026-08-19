from __future__ import annotations

import pytest

from mary.core.mary import Mary
from mary.orchestration import (
    ProvenanceSource,
    TaskStatus,
    TaskWorkspaceManager,
)


def test_task_workspace_creates_ephemeral_current_task():
    manager = TaskWorkspaceManager()

    task = manager.create_task("Review Mary's memory architecture")

    assert task.task_id == "task_0001"
    assert task.status == TaskStatus.ACTIVE
    assert manager.current() is task
    assert manager.status()["persistence"] == "ephemeral_process_local"


def test_task_workspace_records_evidence_with_explicit_provenance():
    manager = TaskWorkspaceManager()
    task = manager.create_task("Check a routing claim")

    evidence = manager.add_evidence(
        task.task_id,
        "Groq failed with a simulated 429.",
        provenance=ProvenanceSource.TEST_RESULT,
        source_detail="tests/llm/test_router_failover.py",
        confidence=0.98,
    )

    assert evidence.evidence_id == "evidence_0001"
    assert evidence.provenance == "test_result"
    assert evidence.source_detail.endswith("test_router_failover.py")
    assert evidence.confidence == pytest.approx(0.98)


def test_task_evidence_confidence_is_bounded():
    manager = TaskWorkspaceManager()
    task = manager.create_task("Bound confidence")

    high = manager.add_evidence(
        task.task_id,
        "high",
        provenance="inference",
        confidence=8,
    )
    low = manager.add_evidence(
        task.task_id,
        "low",
        provenance="inference",
        confidence=-2,
    )

    assert high.confidence == 1.0
    assert low.confidence == 0.0


def test_hypotheses_questions_actions_consultations_and_decisions_are_task_local():
    manager = TaskWorkspaceManager()
    task = manager.create_task("Compare approaches")

    hypothesis = manager.add_hypothesis(
        task.task_id,
        "A smaller prompt may reduce latency.",
        confidence=0.7,
    )
    question = manager.add_question(
        task.task_id,
        "Does the smaller prompt preserve character grounding?",
    )
    action = manager.record_action(
        task.task_id,
        action="run_test",
        status="success",
        result="character grounding preserved",
    )
    consultation = manager.record_consultation(
        task.task_id,
        role="critic",
        source="gemini",
        request_summary="Critique the smaller prompt.",
        response_summary="Watch for lost provenance context.",
    )
    decision = manager.record_decision(
        task.task_id,
        description="Keep provenance context in the compact prompt.",
        reason="The test and critique agree on the boundary.",
    )

    assert hypothesis.hypothesis_id == "hypothesis_0001"
    assert question.startswith("Does the smaller prompt")
    assert action["status"] == "success"
    assert consultation.consultation_id == "consultation_0001"
    assert consultation.source == "gemini"
    assert decision.decision_id == "task_decision_0001"
    assert len(task.evidence) == 0


def test_consultation_is_not_automatically_promoted_to_evidence():
    manager = TaskWorkspaceManager()
    task = manager.create_task("Ask a specialist")

    manager.record_consultation(
        task.task_id,
        role="second_opinion",
        source="openai",
        request_summary="Review this hypothesis.",
        response_summary="The hypothesis seems plausible.",
    )

    assert len(task.consultations) == 1
    assert task.evidence == []


def test_terminal_task_is_immutable_and_clears_current_pointer():
    manager = TaskWorkspaceManager()
    task = manager.create_task("Finish a bounded task")

    manager.complete(task.task_id, outcome="done")

    assert task.status == TaskStatus.COMPLETED
    assert task.outcome == "done"
    assert task.completed_at is not None
    assert manager.current() is None

    with pytest.raises(RuntimeError):
        manager.add_question(task.task_id, "This should not be accepted")


def test_manager_supports_multiple_active_tasks_without_merging_state():
    manager = TaskWorkspaceManager()
    first = manager.create_task("First", make_current=False)
    second = manager.create_task("Second")

    manager.add_evidence(
        first.task_id,
        "first evidence",
        provenance="creator",
    )
    manager.add_evidence(
        second.task_id,
        "second evidence",
        provenance="local_tool",
    )

    assert manager.current() is second
    assert [item.content for item in first.evidence] == ["first evidence"]
    assert [item.content for item in second.evidence] == ["second evidence"]
    assert manager.status()["active_count"] == 2


def test_task_workspace_serialization_keeps_provenance_visible():
    manager = TaskWorkspaceManager()
    task = manager.create_task("Serialize work")
    manager.add_evidence(
        task.task_id,
        "Unbe explicitly selected the local route.",
        provenance=ProvenanceSource.CREATOR,
        source_detail="current_turn",
        confidence=1.0,
    )

    payload = task.to_dict()

    assert payload["status"] == "active"
    assert payload["evidence"][0]["provenance"] == "creator"
    assert payload["evidence"][0]["source_detail"] == "current_turn"


def test_new_workspace_manager_does_not_reload_previous_process_tasks():
    first = TaskWorkspaceManager()
    first.create_task("Temporary task")

    second = TaskWorkspaceManager()

    assert first.status()["task_count"] == 1
    assert second.status()["task_count"] == 0
    assert second.current() is None


def test_mary_exposes_task_workspace_in_runtime_status():
    mary = Mary()

    assert isinstance(mary.task_workspace, TaskWorkspaceManager)
    workspace_status = mary.status()["orchestration"]["task_workspace"]
    assert workspace_status["persistence"] == "ephemeral_process_local"
    assert workspace_status["promotion_policy"] == "explicit_existing_paths_only"


def test_task_workspace_does_not_mutate_durable_mary_state():
    mary = Mary()
    memory_before = mary.memory.status()
    creator_before = mary.user_model.current_profile()
    preferences_before = mary.preferences.to_dict()
    developed_before = mary.developed_self_state.to_dict()

    task = mary.task_workspace.create_task("Temporary architecture review")
    mary.task_workspace.add_evidence(
        task.task_id,
        "A model suggested changing Mary's favorite color.",
        provenance=ProvenanceSource.GEMINI,
        confidence=0.9,
    )
    mary.task_workspace.record_consultation(
        task.task_id,
        role="critic",
        source="openai",
        request_summary="Should Mary's preferences change?",
        response_summary="Maybe.",
    )

    assert mary.memory.status() == memory_before
    assert mary.user_model.current_profile() == creator_before
    assert mary.preferences.to_dict() == preferences_before
    assert mary.developed_self_state.to_dict() == developed_before


def test_unknown_task_id_fails_closed():
    manager = TaskWorkspaceManager()

    with pytest.raises(KeyError):
        manager.add_evidence(
            "task_9999",
            "unknown",
            provenance="inference",
        )
