from __future__ import annotations

from mary.governance.limits import RuntimeLimits
from mary.memory.manager import MemoryManager
from mary.orchestration.workspace import TaskWorkspaceManager


def test_simulated_long_term_memory_growth_remains_bounded(tmp_path):
    limits = RuntimeLimits(
        episodic_capacity=40,
        semantic_capacity=30,
        working_memory_capacity=10,
        memory_content_characters=512,
        backup_generations=2,
    )
    path = tmp_path / "memory.json"
    manager = MemoryManager(storage_path=path, limits=limits)

    for index in range(5000):
        manager.remember_event(f"event {index} " + ("x" * 1000), importance=(index % 10) / 10)
        if index % 50 == 0:
            manager.remember_fact("stress", f"fact_{index}", str(index), confidence=0.5)
    assert manager.save()

    assert manager.episodic.count() == 40
    assert manager.semantic.count() == 30
    assert path.stat().st_size < 200_000
    assert len(list(tmp_path.glob("memory.json.bak*"))) <= 2


def test_simulated_task_growth_prunes_closed_tasks_and_each_task_is_bounded():
    limits = RuntimeLimits(task_capacity=8, task_evidence_capacity=5, task_text_characters=256)
    workspace = TaskWorkspaceManager(limits=limits)

    for index in range(50):
        task = workspace.create_task(f"task {index}")
        for evidence_index in range(20):
            workspace.add_evidence(
                task.task_id,
                "e" * 1000 + str(evidence_index),
                provenance="test_result",
            )
        assert len(task.evidence) == 5
        assert all(len(item.content) <= 256 for item in task.evidence)
        workspace.complete(task.task_id)

    assert len(workspace.list_tasks()) <= 8
    assert workspace.status()["evicted_tasks"] > 0
