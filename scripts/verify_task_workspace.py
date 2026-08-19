"""Verify MaryV2 Task Workspace V1 installation."""

from __future__ import annotations

from mary.core.mary import Mary
from mary.orchestration import ProvenanceSource, TaskStatus


def _pass(message: str) -> None:
    print(f"PASS {message}")


def main() -> int:
    print("=" * 72)
    print("MARY V2 TASK WORKSPACE V1")
    print("=" * 72)

    mary = Mary()
    manager = mary.task_workspace

    before_memory = mary.memory.status()
    before_creator = mary.user_model.current_profile()
    before_preferences = mary.preferences.to_dict()
    before_developed = mary.developed_self_state.to_dict()

    task = manager.create_task(
        "Review a proposed MaryV2 architecture change",
        metadata={"verification": True},
    )
    assert manager.current() is task
    assert task.status == TaskStatus.ACTIVE
    _pass("Mary owns one connected process-local task workspace manager")

    evidence = manager.add_evidence(
        task.task_id,
        "A deterministic test passed.",
        provenance=ProvenanceSource.TEST_RESULT,
        source_detail="verification",
        confidence=1.0,
    )
    assert evidence.provenance == "test_result"
    _pass("temporary evidence keeps explicit provenance")

    manager.add_hypothesis(
        task.task_id,
        "The proposed change preserves the existing boundary.",
        confidence=0.7,
    )
    manager.add_question(
        task.task_id,
        "What evidence would falsify the hypothesis?",
    )
    _pass("hypotheses and open questions remain task-local")

    manager.record_consultation(
        task.task_id,
        role="critic",
        source="gemini",
        request_summary="Critique the proposed change.",
        response_summary="Check the persistence boundary.",
    )
    assert len(task.consultations) == 1
    assert len(task.evidence) == 1
    _pass("model consultation is recorded as a suggestion, not automatic truth")

    assert mary.memory.status() == before_memory
    assert mary.user_model.current_profile() == before_creator
    assert mary.preferences.to_dict() == before_preferences
    assert mary.developed_self_state.to_dict() == before_developed
    _pass("task work cannot directly mutate durable Mary or creator state")

    manager.complete(task.task_id, outcome="verification complete")
    assert manager.current() is None
    assert task.status == TaskStatus.COMPLETED
    _pass("task lifecycle closes cleanly and releases the current-task pointer")

    fresh = type(manager)()
    assert fresh.status()["task_count"] == 0
    _pass("task workspace is ephemeral and does not survive a fresh manager")

    status = mary.status()["orchestration"]["task_workspace"]
    assert status["persistence"] == "ephemeral_process_local"
    assert status["promotion_policy"] == "explicit_existing_paths_only"
    _pass("runtime status exposes the task persistence/promotion boundary")

    print("-" * 72)
    print("RESULT: PASS")
    print(
        "Mary now has a structured temporary place to organize work without "
        "turning model/tool output into durable identity or memory."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
