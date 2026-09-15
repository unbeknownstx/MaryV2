import pytest

from mary.orchestration.workers import SpecialistWorkerPool, WorkerBudget


def test_worker_can_only_narrow_parent_permissions():
    pool = SpecialistWorkerPool()
    worker = pool.spawn(
        task_id="task_1",
        role="research",
        parent_capabilities={"web.search", "filesystem.read", "filesystem.write"},
        requested_capabilities={"web.search", "filesystem.read"},
        parent_mutating_capabilities={"filesystem.write"},
    )
    assert worker.authorize_capability("web.search") is True
    assert worker.authorize_capability("filesystem.write") is False

    with pytest.raises(PermissionError):
        pool.spawn(
            task_id="task_1",
            role="bad",
            parent_capabilities={"web.search"},
            requested_capabilities={"shell.execute"},
        )


def test_mutating_authority_must_be_explicitly_inherited():
    pool = SpecialistWorkerPool()
    worker = pool.spawn(
        task_id="task_1",
        role="editor",
        parent_capabilities={"filesystem.read", "filesystem.write"},
        requested_capabilities={"filesystem.read", "filesystem.write"},
        parent_mutating_capabilities={"filesystem.write"},
        requested_mutating_capabilities={"filesystem.write"},
    )
    assert worker.authorize_capability("filesystem.write", mutating=True) is True
    assert worker.authorize_capability("filesystem.read", mutating=True) is False


def test_worker_budget_and_cancellation_are_hard_boundaries():
    pool = SpecialistWorkerPool()
    worker = pool.spawn(
        task_id="task_2",
        role="analysis",
        parent_capabilities={"tool.read"},
        requested_capabilities={"tool.read"},
        budget=WorkerBudget(max_steps=1, max_tool_calls=1, max_provider_calls=1),
    )
    worker.record_step("inspect")
    with pytest.raises(RuntimeError):
        worker.record_step("again")
    assert worker.status()["status"] == "budget_exhausted"

    second = pool.spawn(
        task_id="task_2",
        role="analysis",
        parent_capabilities={"tool.read"},
        requested_capabilities={"tool.read"},
    )
    second.cancel("parent task ended")
    with pytest.raises(RuntimeError):
        second.record_tool_call("tool.read")
    assert second.status()["status"] == "cancelled"


def test_worker_never_owns_identity_or_durable_memory():
    pool = SpecialistWorkerPool()
    worker = pool.spawn(
        task_id="task_3",
        role="coding",
        parent_capabilities={"code.read"},
        requested_capabilities={"code.read"},
    )
    ownership = worker.status()["ownership"]
    assert ownership == {
        "mary_identity": False,
        "durable_memory": False,
        "creator_profile": False,
        "canonical_state": False,
    }


def test_pool_capacity_protects_active_workers():
    pool = SpecialistWorkerPool(capacity=1)
    worker = pool.spawn(
        task_id="task_4",
        role="first",
        parent_capabilities=set(),
        requested_capabilities=set(),
    )
    with pytest.raises(RuntimeError):
        pool.spawn(
            task_id="task_4",
            role="second",
            parent_capabilities=set(),
            requested_capabilities=set(),
        )
    worker.complete()
    replacement = pool.spawn(
        task_id="task_4",
        role="second",
        parent_capabilities=set(),
        requested_capabilities=set(),
    )
    assert replacement.active is True
