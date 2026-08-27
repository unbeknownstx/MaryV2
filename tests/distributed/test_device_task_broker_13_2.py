import pytest

from mary.distributed import CapabilityDescriptor, DeviceTaskBroker, NodeDescriptor, NodeRegistry


def _registry():
    registry = NodeRegistry()
    cap = CapabilityDescriptor("personal_search", private=True, local=True)
    registry.register(NodeDescriptor(
        node_id="windows-pc",
        role="capability_node",
        host_type="desktop",
        platform="windows",
        capabilities={cap.name: cap},
    ))
    return registry


def test_broker_routes_typed_task_and_only_selected_node_can_complete():
    broker = DeviceTaskBroker()
    task = broker.enqueue(
        _registry(),
        capability="personal_search",
        intent="Find my manuscript",
        args={"query": "Unbeknownst", "limit": 99},
        requester_device_id="iphone",
    )
    assert task.selected_node_id == "windows-pc"
    assert task.args == {"query": "Unbeknownst", "limit": 12}

    claimed = broker.poll("windows-pc")
    assert claimed is not None
    assert claimed.task_id == task.task_id
    assert claimed.status == "claimed"

    with pytest.raises(PermissionError):
        broker.complete(
            node_id="other-pc",
            task_id=task.task_id,
            status="completed",
            result={},
        )

    completed = broker.complete(
        node_id="windows-pc",
        task_id=task.task_id,
        status="completed",
        result={"count": 1},
    )
    assert completed.status == "completed"
    assert broker.get(task.task_id).result == {"count": 1}


def test_broker_has_no_shell_execution_contract():
    broker = DeviceTaskBroker()
    with pytest.raises(ValueError):
        broker.enqueue(
            _registry(),
            capability="shell",
            intent="run a command",
            args={"command": "whoami"},
            requester_device_id="client",
        )
