from types import SimpleNamespace
from time import monotonic

import pytest

from mary.distributed.tasks import DeviceTaskBroker


class _Registry:
    def __init__(self, node_id="node-a"):
        self.node_id = node_id

    def choose(self, capability):
        return SimpleNamespace(node_id=self.node_id)


def _enqueue_search(broker):
    return broker.enqueue(
        _Registry(),
        capability="personal_search",
        intent="find notes",
        args={"query": "needle", "limit": 4},
        requester_device_id="creator",
    )


def test_claim_delivery_id_is_attempt_scoped_and_bounded():
    broker = DeviceTaskBroker(claim_lease_seconds=30.0)
    task = _enqueue_search(broker)
    base_id = task.task_id

    claimed = broker.poll("node-a")
    assert claimed is task
    delivered = claimed.to_dict()["task_id"]

    assert delivered.startswith(base_id + ".1.")
    assert delivered != base_id
    assert len(delivered) <= 96
    assert claimed.to_dict()["claim_attempt"] == 1


def test_expired_replay_safe_claim_requeues_with_new_attempt_and_rejects_stale_completion():
    broker = DeviceTaskBroker(claim_lease_seconds=30.0, max_claim_attempts=2)
    task = _enqueue_search(broker)

    first = broker.poll("node-a")
    first_delivery = first.to_dict()["task_id"]
    first.claimed_monotonic = monotonic() - 31.0

    second = broker.poll("node-a")
    second_delivery = second.to_dict()["task_id"]
    assert second.claim_attempt == 2
    assert second_delivery != first_delivery

    with pytest.raises(PermissionError, match="stale claim attempt"):
        broker.complete(
            node_id="node-a",
            task_id=first_delivery,
            status="completed",
            result={"items": []},
        )

    completed = broker.complete(
        node_id="node-a",
        task_id=second_delivery,
        status="completed",
        result={"items": []},
    )
    assert completed.status == "completed"


def test_bare_legacy_completion_is_rejected_after_reissue():
    broker = DeviceTaskBroker(claim_lease_seconds=30.0, max_claim_attempts=2)
    task = _enqueue_search(broker)
    base_id = task.task_id

    first = broker.poll("node-a")
    first.claimed_monotonic = monotonic() - 31.0
    second = broker.poll("node-a")
    assert second.claim_attempt == 2

    with pytest.raises(PermissionError, match="missing its active claim lease"):
        broker.complete(
            node_id="node-a",
            task_id=base_id,
            status="completed",
            result={"items": []},
        )


def test_replay_safe_task_expires_when_claim_attempt_budget_is_exhausted():
    broker = DeviceTaskBroker(claim_lease_seconds=30.0, max_claim_attempts=2)
    task = _enqueue_search(broker)

    first = broker.poll("node-a")
    first.claimed_monotonic = monotonic() - 31.0
    second = broker.poll("node-a")
    second.claimed_monotonic = monotonic() - 31.0

    assert broker.poll("node-a") is None
    current = broker.get(task.task_id)
    assert current is not None
    assert current.status == "expired"
    assert "claim lease expired" in current.error.lower()


def test_first_attempt_legacy_base_id_remains_compatible():
    broker = DeviceTaskBroker(claim_lease_seconds=30.0)
    task = _enqueue_search(broker)
    broker.poll("node-a")

    completed = broker.complete(
        node_id="node-a",
        task_id=task.task_id,
        status="completed",
        result={"items": []},
    )
    assert completed.status == "completed"
