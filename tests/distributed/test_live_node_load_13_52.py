from mary.distributed import CapabilityDescriptor, NodeDescriptor, NodeRegistry
from mary.distributed.tasks import DeviceTaskBroker


def _node(node_id: str, latency_ms: float) -> NodeDescriptor:
    return NodeDescriptor(
        node_id=node_id,
        role="capability_node",
        host_type="capability_node",
        platform="test",
        capabilities={
            "llm.ollama": CapabilityDescriptor(
                "llm.ollama",
                private=True,
                local=True,
                cost="local",
                metadata={
                    "benchmark_latency_ms": latency_ms,
                    "benchmark_success_rate": 1.0,
                },
            )
        },
    )


def _registry() -> NodeRegistry:
    registry = NodeRegistry()
    registry.register(_node("a-idle", 900.0))
    registry.register(_node("z-fast", 300.0))
    return registry


def _args(role: str) -> dict:
    return {
        "messages": [{"role": "user", "content": "private prompt text"}],
        "role": role,
        "temperature": 0.2,
        "max_tokens": 64,
    }


def test_busy_realtime_node_yields_background_work_to_idle_peer():
    registry = _registry()
    broker = DeviceTaskBroker()

    realtime = broker.enqueue(
        registry,
        capability="llm.ollama",
        intent="conversation",
        args=_args("conversation"),
        requester_device_id="creator",
    )
    assert realtime.selected_node_id == "z-fast"
    assert broker.poll("z-fast") is realtime

    background = broker.enqueue(
        registry,
        capability="llm.ollama",
        intent="background utility",
        args=_args("utility"),
        requester_device_id="creator",
    )

    assert background.selected_node_id == "a-idle"
    status = broker.compute_status()
    assert status["live_load"]["z-fast"] == {
        "active_realtime": 1,
        "active_background": 0,
        "stream_critical": True,
    }


def test_static_benchmark_preference_returns_after_realtime_pressure_clears():
    registry = _registry()
    broker = DeviceTaskBroker()

    realtime = broker.enqueue(
        registry,
        capability="llm.ollama",
        intent="conversation",
        args=_args("conversation"),
        requester_device_id="creator",
    )
    broker.poll("z-fast")
    broker.complete(
        node_id="z-fast",
        task_id=realtime.task_id,
        status="rejected",
        error="permission denied",
    )

    # Rejection is not benchmark evidence and no work remains claimed, so the
    # broker returns to the registry's established static benchmark preference.
    assert broker.compute_status()["sample_count"] == 0
    assert broker.compute_status()["live_load"] == {}

    next_task = broker.enqueue(
        registry,
        capability="llm.ollama",
        intent="background utility",
        args=_args("utility"),
        requester_device_id="creator",
    )
    assert next_task.selected_node_id == "z-fast"


def test_multiple_claims_are_counted_without_content_retention():
    registry = _registry()
    broker = DeviceTaskBroker()

    first = broker.enqueue(
        registry,
        capability="llm.ollama",
        intent="private realtime intent",
        args=_args("conversation"),
        requester_device_id="creator",
    )
    broker.poll(first.selected_node_id)

    # Force a second task to the currently idle peer through the live-load rule,
    # then claim it there as background work.
    second = broker.enqueue(
        registry,
        capability="llm.ollama",
        intent="private background intent",
        args=_args("utility"),
        requester_device_id="creator",
    )
    broker.poll(second.selected_node_id)

    status = broker.compute_status()
    serialized = str(status).lower()
    assert status["live_load"][first.selected_node_id]["active_realtime"] == 1
    assert status["live_load"][second.selected_node_id]["active_background"] == 1
    assert "private prompt text" not in serialized
    assert "private realtime intent" not in serialized
    assert "private background intent" not in serialized
    assert status["content_retained"] is False


def test_idle_cold_start_still_uses_existing_registry_choice():
    registry = _registry()
    broker = DeviceTaskBroker()
    task = broker.enqueue(
        registry,
        capability="llm.ollama",
        intent="ordinary work",
        args=_args("utility"),
        requester_device_id="creator",
    )
    assert task.selected_node_id == "z-fast"
    assert broker.compute_status()["sample_count"] == 0
    assert broker.compute_status()["live_load"] == {}
