import pytest

from mary.distributed import (
    CapabilityDescriptor,
    DeviceTaskBroker,
    NodeDescriptor,
    NodeRegistry,
)


def _registry():
    registry = NodeRegistry()
    registry.register(
        NodeDescriptor(
            node_id="mcp-node",
            role="capability_node",
            host_type="capability_node",
            platform="linux",
            capabilities={
                "mcp.opendesign": CapabilityDescriptor(
                    name="mcp.opendesign",
                    available=True,
                    private=False,
                    local=True,
                    cost="external_policy",
                    readiness="ready",
                )
            },
        )
    )
    return registry


def test_device_broker_accepts_only_bounded_mcp_task_shape():
    registry = _registry()
    broker = DeviceTaskBroker(lifecycle_lock=registry.lifecycle_lock, live_node=registry.is_live)

    task = broker.enqueue(
        registry,
        capability="mcp.opendesign",
        intent="Find grounded design references",
        args={
            "tool": "recommend_references",
            "arguments": {"query": "clean companion iPhone UI"},
        },
        requester_device_id="creator",
    )

    assert task.capability == "mcp.opendesign"
    assert task.args == {
        "tool": "recommend_references",
        "arguments": {"query": "clean companion iPhone UI"},
    }

    with pytest.raises(ValueError, match="secret field"):
        broker.enqueue(
            registry,
            capability="mcp.opendesign",
            intent="must fail",
            args={
                "tool": "recommend_references",
                "arguments": {"api_key": "never-put-secrets-in-core-tasks"},
            },
            requester_device_id="creator",
        )


def test_device_broker_sanitizes_mcp_completion_before_core_retains_it():
    registry = _registry()
    broker = DeviceTaskBroker(lifecycle_lock=registry.lifecycle_lock, live_node=registry.is_live)
    queued = broker.enqueue(
        registry,
        capability="mcp.opendesign",
        intent="Design references",
        args={
            "tool": "recommend_references",
            "arguments": {"query": "companion UI"},
        },
        requester_device_id="creator",
    )
    claimed = broker.poll("mcp-node")
    assert claimed is not None
    assert claimed.task_id == queued.task_id

    completed = broker.complete(
        node_id="mcp-node",
        task_id=queued.task_id,
        status="completed",
        result={
            "tool": "recommend_references",
            "structured_content": {
                "references": ["one", "two"],
                "token": "DO-NOT-RETAIN",
            },
            "headers": {"Authorization": "Bearer SECRET"},
            "endpoint": "https://private.example/mcp",
        },
    )

    rendered = repr(completed.to_dict())
    assert completed.status == "completed"
    assert completed.result["server"] == "opendesign"
    assert completed.result["structured_content"]["references"] == ["one", "two"]
    assert completed.result["structured_content"]["token"] == "[REDACTED]"
    assert "DO-NOT-RETAIN" not in rendered
    assert "private.example" not in rendered
    assert "Bearer SECRET" not in rendered


def test_no_generic_mcp_or_shell_capability_is_executable():
    registry = _registry()
    broker = DeviceTaskBroker(lifecycle_lock=registry.lifecycle_lock, live_node=registry.is_live)

    for capability in ("mcp", "mcp.anything", "shell", "command", "exec"):
        with pytest.raises(ValueError, match="Capability execution is not supported"):
            broker.enqueue(
                registry,
                capability=capability,
                intent="must fail",
                args={"tool": "anything", "arguments": {}},
                requester_device_id="creator",
            )
