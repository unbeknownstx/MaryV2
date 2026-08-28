from threading import Thread
from time import monotonic, sleep

from mary.distributed import CapabilityDescriptor, DeviceTaskBroker, NodeDescriptor, NodeRegistry


def _registry():
    registry = NodeRegistry()
    registry.register(NodeDescriptor(
        node_id="windows-pc",
        role="capability_node",
        host_type="desktop",
        platform="windows",
        capabilities={
            "llm.ollama": CapabilityDescriptor("llm.ollama", private=True, local=True),
        },
    ))
    return registry


def test_long_poll_wakes_immediately_when_task_is_enqueued():
    broker = DeviceTaskBroker()
    registry = _registry()
    observed = {}

    def waiter():
        started = monotonic()
        observed["task"] = broker.poll("windows-pc", wait_seconds=1.5)
        observed["elapsed"] = monotonic() - started

    thread = Thread(target=waiter)
    thread.start()
    sleep(0.05)
    task = broker.enqueue(
        registry,
        capability="llm.ollama",
        intent="wake the waiting Windows node",
        args={"messages": [{"role": "user", "content": "hello"}]},
        requester_device_id="mary-core",
    )
    thread.join(timeout=1.0)

    assert not thread.is_alive()
    assert observed["task"].task_id == task.task_id
    assert observed["task"].status == "claimed"
    assert observed["elapsed"] < 0.5


def test_wait_for_terminal_releases_broker_lock_for_device_completion():
    broker = DeviceTaskBroker()
    registry = _registry()
    task = broker.enqueue(
        registry,
        capability="llm.ollama",
        intent="complete concurrently",
        args={"messages": [{"role": "user", "content": "hello"}]},
        requester_device_id="mary-core",
    )

    def worker():
        claimed = broker.poll("windows-pc", wait_seconds=0.5)
        assert claimed is not None
        broker.complete(
            node_id="windows-pc",
            task_id=claimed.task_id,
            status="completed",
            result={"content": "done", "model": "local-test"},
        )

    thread = Thread(target=worker)
    thread.start()
    completed = broker.wait_for_terminal(task.task_id, timeout_seconds=1.0)
    thread.join(timeout=1.0)

    assert completed is not None
    assert completed.status == "completed"
    assert completed.result["content"] == "done"
