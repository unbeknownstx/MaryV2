from threading import Thread
from time import monotonic, sleep
from types import SimpleNamespace

from mary.distributed.tasks import DeviceTaskBroker


class _Registry:
    def __init__(self, node_id="node-a"):
        self.node_id = node_id

    def choose(self, capability, *, require_execution_ready=False):
        assert require_execution_ready is True
        return SimpleNamespace(node_id=self.node_id)

    def candidates(self, capability):
        return [SimpleNamespace(node_id=self.node_id)]


def _enqueue_search(broker):
    return broker.enqueue(
        _Registry(),
        capability="personal_search",
        intent="find notes",
        args={"query": "needle", "limit": 4},
        requester_device_id="creator",
    )


def _expire_active_claim(broker, task_id):
    internal = broker._tasks[task_id]
    internal.claimed_monotonic = monotonic() - 31.0


def test_claim_keeps_canonical_task_id_and_protocol_shape():
    broker = DeviceTaskBroker(claim_lease_seconds=30.0)
    task = _enqueue_search(broker)
    base_id = task.task_id

    claimed = broker.poll("node-a")
    assert claimed is task
    assert claimed.task_id == base_id
    assert claimed.to_dict()["task_id"] == base_id
    assert claimed.attempt == 1
    assert claimed.root_task_id == base_id
    assert claimed.replacement_task_id == ""


def test_expired_replay_safe_claim_rolls_over_to_new_task_id():
    broker = DeviceTaskBroker(claim_lease_seconds=30.0, max_claim_attempts=2)
    first = _enqueue_search(broker)
    root_id = first.task_id

    assert broker.poll("node-a") is first
    _expire_active_claim(broker, root_id)

    second = broker.poll("node-a")
    assert second is not None
    assert second.task_id != root_id
    assert second.attempt == 2
    assert second.root_task_id == root_id

    old = broker.get(root_id)
    assert old is not None
    assert old.status == "expired"
    assert old.replacement_task_id == second.task_id
    assert "rolled over" in old.error.lower()


def test_late_old_completion_cannot_overwrite_replacement():
    broker = DeviceTaskBroker(claim_lease_seconds=30.0, max_claim_attempts=2)
    first = _enqueue_search(broker)
    root_id = first.task_id
    broker.poll("node-a")
    _expire_active_claim(broker, root_id)

    second = broker.poll("node-a")
    assert second is not None

    stale = broker.complete(
        node_id="node-a",
        task_id=root_id,
        status="completed",
        result={"count": 99},
    )
    assert stale.status == "expired"
    assert stale.result == {}

    completed = broker.complete(
        node_id="node-a",
        task_id=second.task_id,
        status="completed",
        result={"count": 1},
    )
    assert completed.status == "completed"
    assert completed.result == {"count": 1}
    assert broker.get(root_id).result == {}


def test_waiter_on_original_task_follows_replacement_chain():
    broker = DeviceTaskBroker(claim_lease_seconds=30.0, max_claim_attempts=2)
    first = _enqueue_search(broker)
    root_id = first.task_id
    broker.poll("node-a")
    _expire_active_claim(broker, root_id)

    result_holder = []

    def waiter():
        result_holder.append(broker.wait_for_terminal(root_id, timeout_seconds=2.0))

    thread = Thread(target=waiter)
    thread.start()
    sleep(0.02)
    second = broker.poll("node-a")
    assert second is not None
    broker.complete(
        node_id="node-a",
        task_id=second.task_id,
        status="completed",
        result={"count": 1},
    )
    thread.join(timeout=1.0)

    assert not thread.is_alive()
    assert len(result_holder) == 1
    assert result_holder[0] is not None
    assert result_holder[0].task_id == second.task_id
    assert result_holder[0].status == "completed"


def test_replay_safe_task_expires_when_attempt_budget_is_exhausted():
    broker = DeviceTaskBroker(claim_lease_seconds=30.0, max_claim_attempts=2)
    first = _enqueue_search(broker)
    root_id = first.task_id
    broker.poll("node-a")
    _expire_active_claim(broker, root_id)

    second = broker.poll("node-a")
    assert second is not None
    _expire_active_claim(broker, second.task_id)

    assert broker.poll("node-a") is None
    current = broker.get(second.task_id)
    assert current is not None
    assert current.status == "expired"
    assert current.replacement_task_id == ""
    assert "unsafe or exhausted" in current.error.lower()


def test_direct_unclaimed_completion_remains_compatible():
    broker = DeviceTaskBroker(claim_lease_seconds=30.0)
    task = _enqueue_search(broker)

    completed = broker.complete(
        node_id="node-a",
        task_id=task.task_id,
        status="completed",
        result={"count": 1},
    )
    assert completed.status == "completed"
    assert completed.result == {"count": 1}
